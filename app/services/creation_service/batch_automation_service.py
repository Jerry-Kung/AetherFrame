"""
首页批量自动化创作：编排多轮 Prompt 预生成 + 链式一键美图创作。
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.material import MaterialCharacter
from app.repositories.creation_batch_repository import CreationBatchRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.fixed_seed_template_repository import FixedSeedTemplateRepository
from app.repositories.material_repository import MaterialCharacterRepository
from app.services.creation_service.prompt_precreation_service import (
    PromptPrecreationService,
    resolve_chara_profile_text,
)
from app.services.creation_service.quick_create_service import QuickCreateService

logger = logging.getLogger(__name__)

_VALID_ASPECT = frozenset({"16:9", "4:3", "1:1", "3:4", "9:16"})


def _parse_bio_dict(bio_json: Optional[str]) -> Dict[str, Any]:
    try:
        bio = json.loads(bio_json or "{}")
        return bio if isinstance(bio, dict) else {}
    except json.JSONDecodeError:
        return {}


def _collect_unused_seed_pairs(character_id: str, bio_json: Optional[str]) -> List[Dict[str, Any]]:
    """返回 {character_id, seed_prompt_id, seed_section, seed_prompt_text} 行。"""
    bio = _parse_bio_dict(bio_json)
    raw = bio.get("official_seed_prompts")
    if raw is None or not isinstance(raw, dict):
        return []
    out: List[Dict[str, Any]] = []

    def walk(arr: Any, section_api: str, prefix: str) -> None:
        if not isinstance(arr, list):
            return
        for i, row in enumerate(arr):
            if not isinstance(row, dict):
                continue
            sid = str(row.get("id") or "").strip() or f"seed-{prefix}-{i}"
            text = str(row.get("text") or "").strip()
            if not text or row.get("used") is True:
                continue
            out.append(
                {
                    "character_id": character_id,
                    "seed_prompt_id": sid,
                    "seed_section": section_api,
                    "seed_prompt_text": text,
                }
            )

    cs = raw.get("character_specific")
    if not isinstance(cs, list):
        cs = raw.get("characterSpecific")
    walk(cs, "character_specific", "cs")
    walk(raw.get("general"), "general", "gen")
    return out


def _normalize_section(section: str) -> str:
    s = (section or "").strip().lower()
    if s == "fixed":
        return "fixed"
    if s in ("character_specific", "general"):
        return s
    if s == "characterspecific":
        return "character_specific"
    return s


class BatchAutomationService:
    def __init__(self, db: Session):
        self.db = db
        self.batch_repo = CreationBatchRepository(db)
        self.material_repo = MaterialCharacterRepository(db)
        self.fixed_seed_repo = FixedSeedTemplateRepository(db)

    def _eligible_done_characters(
        self, filter_ids: Optional[List[str]]
    ) -> List[MaterialCharacter]:
        q = self.db.query(MaterialCharacter).filter(MaterialCharacter.status == "done")
        if filter_ids:
            ids = [str(x).strip() for x in filter_ids if str(x).strip()]
            if not ids:
                return []
            q = q.filter(MaterialCharacter.id.in_(ids))
        chars = q.all()
        eligible: List[MaterialCharacter] = []
        for c in chars:
            profile = resolve_chara_profile_text(c.id, c.bio_json)
            if profile:
                eligible.append(c)
        return eligible

    def _build_pair_pool(
        self, characters: List[MaterialCharacter]
    ) -> List[Dict[str, Any]]:
        pool: List[Dict[str, Any]] = []
        for c in characters:
            pool.extend(_collect_unused_seed_pairs(c.id, c.bio_json))
        for tmpl in self.fixed_seed_repo.list_unused():
            txt = (tmpl.text or "").strip()
            if not txt:
                continue
            for c in characters:
                pool.append(
                    {
                        "character_id": c.id,
                        "seed_prompt_id": tmpl.id,
                        "seed_section": "fixed",
                        "seed_prompt_text": txt,
                    }
                )
        return pool

    @staticmethod
    def _pair_key(p: Dict[str, Any]) -> Tuple[str, str]:
        return (str(p["character_id"]), str(p["seed_prompt_id"]))

    def plan_and_validate(
        self,
        *,
        iterations: int,
        character_ids: Optional[List[str]],
    ) -> Tuple[List[MaterialCharacter], List[Dict[str, Any]]]:
        if iterations < 2 or iterations > 10:
            raise ValueError("创作内容条数必须在 2 到 10 之间")
        requested = (
            [str(x).strip() for x in character_ids if str(x).strip()] if character_ids else None
        )
        if requested:
            for cid in requested:
                ch = self.material_repo.get_by_id(cid)
                if not ch:
                    raise ValueError(f"角色不存在: {cid}")
                if ch.status != "done":
                    raise ValueError(f"角色未处于资料已完善状态，无法加入批量创作: {cid}")
                if not resolve_chara_profile_text(ch.id, ch.bio_json):
                    raise ValueError(f"角色缺少小档案正文，无法用于批量创作: {cid}")
        chars = self._eligible_done_characters(character_ids)
        if not chars:
            raise ValueError("没有资料已完善且具备角色小档案的角色，请先在素材加工中完善资料")
        pool = self._build_pair_pool(chars)
        if not pool:
            raise ValueError("所选范围内没有可用的未使用种子提示词")
        # 按 (角色, 种子 id) 去重
        dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for p in pool:
            dedup[self._pair_key(p)] = p
        unique = list(dedup.values())
        if len(unique) < iterations:
            raise ValueError(
                f"可用「角色 × 种子」组合仅 {len(unique)} 组，少于所选创作条数 {iterations}，"
                "请减少条数或补充/释放更多未使用的种子提示词"
            )
        random.shuffle(unique)
        planned = unique[:iterations]
        return chars, planned

    def start_run(
        self,
        *,
        iterations: int,
        prompt_count: int,
        images_per_prompt: int,
        aspect_ratio: str,
        max_prompts: int,
        character_ids: Optional[List[str]],
    ) -> Dict[str, Any]:
        if prompt_count not in (1, 2, 3, 4):
            raise ValueError("Prompt 预生成数量必须为 1、2、3 或 4")
        if images_per_prompt not in (1, 2, 3, 4):
            raise ValueError("每个 Prompt 生成图片数量必须在 1 到 4 之间")
        if max_prompts not in (1, 2, 3, 4):
            raise ValueError("提交一键创作的 Prompt 条数上限无效")
        if max_prompts > prompt_count:
            raise ValueError("一键创作 Prompt 条数上限不能大于预生成数量")
        ar = (aspect_ratio or "").strip()
        if ar not in _VALID_ASPECT:
            raise ValueError("图片长宽比不合法")

        _, planned = self.plan_and_validate(iterations=iterations, character_ids=character_ids)

        config = {
            "prompt_count": prompt_count,
            "images_per_prompt": images_per_prompt,
            "aspect_ratio": ar,
            "max_prompts": max_prompts,
            "character_ids": character_ids,
            "planned_pairs": planned,
        }
        run = self.batch_repo.create_run(
            iterations_total=iterations,
            config_json=json.dumps(config, ensure_ascii=False),
            status="pending",
        )
        for i, pair in enumerate(planned):
            self.batch_repo.create_item(
                run_id=run.id,
                step_index=i,
                character_id=pair["character_id"],
                seed_prompt_id=pair["seed_prompt_id"],
                seed_section=_normalize_section(pair["seed_section"]),
                seed_prompt_text=pair["seed_prompt_text"],
                status="pending",
            )
        return {"run_id": run.id, "status": run.status}

    def execute_run(self, run_id: str) -> None:
        """后台任务入口：顺序执行每一轮（同步链式预生成 + 美图）。"""
        run = self.batch_repo.get_run(run_id)
        if not run:
            logger.warning("批量创作 run 不存在: %s", run_id)
            return
        self.batch_repo.update_run(run_id, {"status": "running", "error_message": None})
        try:
            cfg = json.loads(run.config_json or "{}")
            prompt_count = int(cfg.get("prompt_count", 2))
            images_per_prompt = int(cfg.get("images_per_prompt", 2))
            aspect_ratio = str(cfg.get("aspect_ratio", "1:1"))
            max_prompts = int(cfg.get("max_prompts", prompt_count))
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            self.batch_repo.update_run(
                run_id,
                {"status": "failed", "error_message": f"配置解析失败: {e}"},
            )
            return

        items = self.batch_repo.list_items_for_run(run_id)
        ppc = PromptPrecreationService(self.db)
        qc_repo = CreationQuickCreateRepository(self.db)
        done = 0
        try:
            for item in items:
                self.batch_repo.update_item(
                    item.id,
                    {"status": "running", "error_message": None},
                )
                chain_payload = {
                    "n": images_per_prompt,
                    "aspect_ratio": aspect_ratio,
                    "max_prompts": max_prompts,
                }
                err: Optional[str] = None
                ppc_tid: Optional[str] = None
                qc_tid: Optional[str] = None
                item_status = "failed"
                try:
                    out = ppc.start_prompt_precreation(
                        character_id=item.character_id,
                        seed_prompt=item.seed_prompt_text,
                        count=prompt_count,
                        background_tasks=None,
                        chain_quick_create=chain_payload,
                    )
                    ppc_tid = str((out or {}).get("task_id") or "")
                    if not ppc_tid:
                        err = "未返回预生成任务 ID"
                    else:
                        self.db.expire_all()
                        task_row = ppc.repo.get_by_id(ppc_tid)
                        if not task_row:
                            err = "预生成任务记录丢失"
                        elif task_row.status != "completed":
                            err = (task_row.error_message or "").strip() or "Prompt 预生成未成功完成"
                        else:
                            qc_tid = (
                                getattr(task_row, "chained_quick_create_task_id", None) or ""
                            ).strip() or None
                            ce = getattr(task_row, "chain_error", None)
                            if ce:
                                err = str(ce).strip()[:2000]
                            elif not qc_tid:
                                err = "链式一键创作未启动"
                            else:
                                qc_row = qc_repo.get_by_id(qc_tid)
                                if not qc_row:
                                    err = "一键创作任务记录丢失"
                                elif qc_row.status != "completed":
                                    err = (qc_row.error_message or "").strip() or "美图创作未成功完成"
                                else:
                                    item_status = "completed"
                                    err = None
                except ValueError as e:
                    err = str(e)
                except Exception as e:
                    logger.exception("批量创作单轮失败 item=%s", item.id)
                    err = str(e) if str(e) else type(e).__name__

                self.batch_repo.update_item(
                    item.id,
                    {
                        "status": "failed" if err else item_status,
                        "error_message": err,
                        "prompt_precreation_task_id": ppc_tid,
                        "quick_create_task_id": qc_tid,
                    },
                )
                done += 1
                self.batch_repo.update_run(run_id, {"iterations_done": done})

            self.batch_repo.update_run(run_id, {"status": "completed"})
        except Exception as e:
            logger.exception("批量创作执行中断 run_id=%s", run_id)
            msg = str(e) if str(e) else type(e).__name__
            self.batch_repo.update_run(
                run_id,
                {"status": "failed", "error_message": msg[:2000]},
            )

    def get_run_payload(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = self.batch_repo.get_run(run_id)
        if not run:
            return None
        items = self.batch_repo.list_items_for_run(run_id)
        return self._serialize_run(run, items)

    def _serialize_run(self, run: Any, items: List[Any]) -> Dict[str, Any]:
        out_items = []
        for it in items:
            ch = self.material_repo.get_by_id(it.character_id)
            out_items.append(
                {
                    "id": it.id,
                    "run_id": it.run_id,
                    "step_index": it.step_index,
                    "character_id": it.character_id,
                    "chara_name": ch.name if ch else "未知角色",
                    "chara_avatar": "",
                    "seed_prompt_id": it.seed_prompt_id,
                    "seed_section": it.seed_section,
                    "seed_prompt_text": it.seed_prompt_text,
                    "prompt_precreation_task_id": it.prompt_precreation_task_id,
                    "quick_create_task_id": it.quick_create_task_id,
                    "status": it.status,
                    "error_message": it.error_message,
                    "created_at": it.created_at,
                    "updated_at": it.updated_at,
                }
            )
        return {
            "id": run.id,
            "status": run.status,
            "iterations_total": run.iterations_total,
            "iterations_done": run.iterations_done,
            "config": json.loads(run.config_json or "{}"),
            "error_message": run.error_message,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "items": out_items,
        }

    def list_items_page(self, *, limit: int, offset: int) -> Dict[str, Any]:
        rows = self.batch_repo.list_all_items(limit=limit, offset=offset)
        total = self.batch_repo.count_all_items()
        items_payload: List[Dict[str, Any]] = []
        for it in rows:
            run = self.batch_repo.get_run(it.run_id)
            if not run:
                continue
            ch = self.material_repo.get_by_id(it.character_id)
            items_payload.append(
                {
                    "id": it.id,
                    "run_id": it.run_id,
                    "run_status": run.status,
                    "step_index": it.step_index,
                    "character_id": it.character_id,
                    "chara_name": ch.name if ch else "未知角色",
                    "chara_avatar": "",
                    "seed_prompt_id": it.seed_prompt_id,
                    "seed_section": it.seed_section,
                    "seed_prompt_text": it.seed_prompt_text,
                    "prompt_precreation_task_id": it.prompt_precreation_task_id,
                    "quick_create_task_id": it.quick_create_task_id,
                    "status": it.status,
                    "error_message": it.error_message,
                    "created_at": it.created_at,
                    "updated_at": it.updated_at,
                }
            )
        return {"items": items_payload, "total": total}

    def delete_batch_item(self, item_id: str) -> Dict[str, Any]:
        item = self.batch_repo.get_item(item_id)
        if not item:
            raise ValueError("记录不存在")
        qc_id = (item.quick_create_task_id or "").strip()
        ppc_id = (item.prompt_precreation_task_id or "").strip()
        if qc_id:
            QuickCreateService(self.db).delete_history(qc_id)
        if ppc_id:
            PromptPrecreationService(self.db).delete_history(ppc_id)
        self.batch_repo.delete_item_row(item_id)
        return {"deleted_id": item_id}


def run_batch_automation_job(run_id: str) -> None:
    """独立 DB 会话，供 FastAPI BackgroundTasks 调用。"""
    from app.models.database import BackgroundSessionLocal

    db = BackgroundSessionLocal()
    try:
        BatchAutomationService(db).execute_run(run_id)
    finally:
        db.close()
