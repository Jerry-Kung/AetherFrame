import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import BackgroundSessionLocal, SessionLocal
from app.models.material import MaterialCreativeDirection
from app.schemas.creation import SeedPayload
from app.prompts.creation.prompt_precreation import (
    prompt_review,
    prompt_review_backup,
    prompt_step1,
    prompt_step2,
)
from app.prompts.creation.prompt_template import good_template1, init_template
from app.repositories.creation_repository import CreationPromptPrecreationRepository
from app.repositories.material_repository import MaterialCharacterRepository
from app.services import directory_service
from app.services.material_service import material_file_service
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

logger = logging.getLogger(__name__)

PREVIEW_MAX_LEN = 160


import re as _re

from app.services.creation_service.composition_dimensions import (
    VALID_AUTO_ASPECT_CODES,
    get_dimension_values,
)


_COMPOSITION_BLOCK_RE = _re.compile(
    r"\*\*\[COMPOSITION_DECISION\]\*\*\s*(.*?)(?=\n\s*\*\*|\Z)",
    _re.DOTALL,
)
_COMPOSITION_LINE_RE = _re.compile(r"^\s*([a-z_]+)\s*:\s*(\S+)\s*$", _re.MULTILINE)

_ENUM_CODES: Dict[str, set] = {
    "aspect_ratio": set(VALID_AUTO_ASPECT_CODES),
    "subject_area_min": {v.code for v in get_dimension_values("subject_area_min")},
}
_ENUM_CODES.update({
    "shooting_angle": {v.code for v in get_dimension_values("shooting_angle")},
    "camera_height":  {v.code for v in get_dimension_values("camera_height")},
})

_STEP0_CAMERA_TEMPLATE = (
    "0-cam、**镜头维度决策（先于画面脑补）**：请从以下枚举中选择本次创作的机位方位与机位高度各一个：\n"
    "机位方位（shooting_angle）候选：\n"
    "{shooting_angle_enum}\n"
    "机位高度（camera_height）候选：\n"
    "{camera_height_enum}\n"
    "请把选择结果一并写入下方 [COMPOSITION_DECISION] 决策块。"
)


def _render_dimension_list(dim: str) -> str:
    return "\n".join(
        f"  - `{v.code}` ({v.display_name}): {v.description}"
        for v in get_dimension_values(dim)
    )


def _build_step1_prompt(*, chara_profile: str, seed_prompt: str) -> str:
    step_zero = (
        "0、**先做构图决策（必须在脑补画面之前完成）**：\n"
        "   - 从下面 9 个长宽比档位中选择最契合本次场景的一个：\n"
        f"{_render_dimension_list('aspect_ratio_auto_full')}\n"
        "   - 优先在主流 5 档 (`9:16`, `3:4`, `1:1`, `4:3`, `16:9`) 中选择；"
        "除非场景明显适配特殊比例（如 `5:4` 适合接近正方形的居中坐姿、`2:3` 适合竖向全身）才使用扩展 4 档。\n"
        "   - 从下面 4 档中选择角色主体在画面中的占比下限：\n"
        f"{_render_dimension_list('subject_area_min')}"
    )
    step_zero_camera = _STEP0_CAMERA_TEMPLATE.format(
        shooting_angle_enum=_render_dimension_list("shooting_angle"),
        camera_height_enum=_render_dimension_list("camera_height"),
    )
    composition_output = (
        "\n7、请在输出的模板正文**之前**，插入一段用 `**[COMPOSITION_DECISION]**` 标记的构图决策说明，"
        "格式如下（每行取上一步选定的 code 值）：\n"
        "```\n"
        "**[COMPOSITION_DECISION]**\n"
        "aspect_ratio: <code>\n"
        "subject_area_min: <code>\n"
        "shooting_angle: <code>\n"
        "camera_height: <code>\n"
        "```\n"
        "后续「任务目标」与「构图硬约束」段中，请用你选定的长宽比替换 `{{aspect_ratio}}` 占位符、"
        "用主体占比下限的百分比值（如 65%）替换 `{{subject_area_min_pct}}` 占位符。"
    )
    return prompt_step1.format(
        chara_profile=chara_profile,
        seed_prompt=seed_prompt,
        init_template=init_template,
        good_template=good_template1,
        step1_task_step_zero=step_zero,
        step1_task_step_zero_camera=step_zero_camera,
        step1_composition_output_requirement=composition_output,
        camera_combo_distribution_bias="",
        negative_prompt_risk_tags="",
    )


def _parse_step1_composition(step1_output: str) -> Dict[str, str]:
    m = _COMPOSITION_BLOCK_RE.search(step1_output)
    if not m:
        return {}
    body = m.group(1)
    result: Dict[str, str] = {}
    for key, value in _COMPOSITION_LINE_RE.findall(body):
        if key not in _ENUM_CODES:
            continue
        if value not in _ENUM_CODES[key]:
            logger.warning(
                "step1 composition %s=%s out of enum, dropped", key, value
            )
            continue
        result[key] = value
    return result


def compose_seed_prompt_with_direction(
    seed_payload: SeedPayload | str | dict,
    db: Session,
) -> str:
    """把方向折叠进 seed text，返回最终用于填入 prompt_precreation 模板 {seed_prompt} 槽的字符串。

    数据来源以 DB 为准（不接受外部传入的方向正文）。
    方向不存在时降级为无方向分支 + warn log。
    """
    payload = SeedPayload.from_raw(seed_payload)

    if not payload.creative_direction_id:
        return payload.text

    dir_row = db.get(MaterialCreativeDirection, payload.creative_direction_id)
    if dir_row is None:
        logger.warning(
            "compose: direction %s not found (deleted?), fallback to plain seed",
            payload.creative_direction_id,
        )
        return payload.text

    return (
        f"### 创作创意方向\n"
        f"{dir_row.title}\n"
        f"\n"
        f"{dir_row.description}\n"
        f"\n"
        f"### 初始创作种子\n"
        f"{payload.text}"
    )
DEFAULT_HISTORY_LIMIT = 50


def _to_iso(dt: Any) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


def resolve_chara_profile_text(
    character_id: str, bio_json: Optional[str]
) -> Optional[str]:
    md = material_file_service.read_chara_profile_markdown(
        character_id, "chara_profile_final.md"
    )
    if md and md.strip():
        return md.strip()
    try:
        bio = json.loads(bio_json or "{}")
        if isinstance(bio, dict):
            cp = bio.get("chara_profile")
            if cp is not None and str(cp).strip():
                return str(cp).strip()
    except json.JSONDecodeError:
        pass
    return None


def parse_llm_json_object(text: str) -> Dict[str, Any]:
    s = text.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("响应中未找到可解析的 JSON 对象")
    return json.loads(s[start : end + 1])


def _build_input_content(candidates: Dict[str, str]) -> str:
    keys = sorted(candidates.keys())
    items = [{k: candidates[k]} for k in keys]
    return json.dumps(items, ensure_ascii=False)


def _collect_candidates(
    *,
    chara_profile: str,
    seed_prompt: str,
    work_dir: str,
    n: int,
) -> tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
    target_success = 2 * n
    max_iters = 4 * n
    candidates: Dict[str, str] = {}
    compositions: Dict[str, Dict[str, str]] = {}
    success_count = 0

    for _ in range(max_iters):
        if success_count >= target_success:
            break
        try:
            p1 = _build_step1_prompt(
                chara_profile=chara_profile,
                seed_prompt=seed_prompt,
            )
            step1_result = yibu_gemini_infer(p1, thinking_level="high", temperature=1.0)
            comp = _parse_step1_composition(step1_result)
            p2 = prompt_step2.format(
                init_template=step1_result,
                good_template=good_template1,
                chara_profile=chara_profile,
                seed_prompt=seed_prompt,
            )
            step2_result = yibu_gemini_infer(p2, thinking_level="high", temperature=1.0)
            success_count += 1
            key = f"candidate_prompt_{success_count:03d}"
            candidates[key] = step2_result
            if comp:
                compositions[key] = comp
            path = os.path.join(work_dir, f"{key}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(step2_result)
        except Exception as e:
            logger.warning("Prompt 预生成循环跳过本次: %s", e, exc_info=True)
            continue

    if success_count < target_success:
        raise RuntimeError(
            f"备选 Prompt 仅成功生成 {success_count} 个，需要 {target_success} 个（网络或模型不稳定时可重试）"
        )
    return candidates, compositions


def _run_review(
    *,
    input_content: str,
    seed_prompt: str,
    chara_profile: str,
    n: int,
) -> str:
    def call_main() -> str:
        p = prompt_review.format(
            input_content=input_content,
            seed_prompt=seed_prompt,
            chara_profile=chara_profile,
            num_best_prompts=n,
        )
        return yibu_gemini_infer(p, thinking_level="high", temperature=0.7)

    def call_backup() -> str:
        p = prompt_review_backup.format(
            input_content=input_content,
            seed_prompt=seed_prompt,
            chara_profile=chara_profile,
            num_best_prompts=n,
        )
        return yibu_gemini_infer(p, thinking_level="high", temperature=0.7)

    for attempt in range(2):
        try:
            return call_main()
        except Exception as e:
            logger.warning(
                "审阅 LLM 调用失败 (attempt %s): %s", attempt + 1, e, exc_info=True
            )
            if attempt == 0:
                time.sleep(10)
            else:
                break
    try:
        return call_backup()
    except Exception as e2:
        logger.error("审阅备份 prompt 仍失败: %s", e2, exc_info=True)
        raise RuntimeError("审阅阶段 LLM 调用失败") from e2


def _build_cards(
    best_files: List[str],
    candidates: Dict[str, str],
    compositions: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    today = date.today().isoformat()
    cards: List[Dict[str, Any]] = []
    for i, name in enumerate(best_files):
        body = candidates[name].strip()
        line = body.split("\n", 1)[0].strip()
        if not line:
            title = f"预生成 Prompt {i + 1}"
        elif len(line) <= 40:
            title = line
        else:
            title = line[:40] + "…"
        preview = body.replace("\n", " ")
        if len(preview) > PREVIEW_MAX_LEN:
            preview = preview[:PREVIEW_MAX_LEN] + "…"
        cards.append(
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "preview": preview,
                "fullPrompt": body,
                "tags": [],
                "createdAt": today,
                "composition": compositions.get(name) or None,
            }
        )
    return cards


_VALID_CHAIN_ASPECT = frozenset({"auto", "16:9", "4:3", "1:1", "3:4", "9:16"})


def _try_chain_quick_create(precreation_task_id: str) -> None:
    """预生成已成功落库后，在同一流程中可选启动一键创作（独立 DB 会话，不占主连接池）。"""
    from app.services.creation_service.quick_create_service import QuickCreateService

    db = BackgroundSessionLocal()
    try:
        prepo = CreationPromptPrecreationRepository(db)
        task = prepo.get_by_id(precreation_task_id)
        if not task or not getattr(task, "chain_quick_create", False):
            return
        n_qc = task.chain_qc_n
        aspect = (task.chain_qc_aspect_ratio or "").strip()
        max_prompts = task.chain_qc_max_prompts
        if (
            n_qc is None
            or n_qc < 1
            or n_qc > 4
            or aspect not in _VALID_CHAIN_ASPECT
            or max_prompts is None
            or max_prompts < 1
            or max_prompts > 4
        ):
            prepo.update(
                precreation_task_id,
                {"chain_error": "链式一键创作参数无效，已跳过"},
            )
            return
        try:
            cards = json.loads(task.result_json or "[]")
        except json.JSONDecodeError:
            cards = []
        if not isinstance(cards, list) or len(cards) == 0:
            prepo.update(
                precreation_task_id,
                {"chain_error": "无可用 Prompt 卡片，已跳过链式一键创作"},
            )
            return
        cap = min(len(cards), int(max_prompts))
        selected: List[Dict[str, str]] = []
        for c in cards[:cap]:
            if not isinstance(c, dict):
                continue
            pid = str(c.get("id") or "").strip()
            fp = str(c.get("fullPrompt") or "").strip()
            if pid and fp:
                selected.append({"id": pid, "fullPrompt": fp})
        if not selected:
            prepo.update(
                precreation_task_id,
                {"chain_error": "切片后无有效 Prompt，已跳过链式一键创作"},
            )
            return
        qc = QuickCreateService(db)
        try:
            out = qc.start_quick_create(
                character_id=task.character_id,
                selected_prompts=selected,
                n=n_qc,
                aspect_ratio=aspect,
                background_tasks=None,
            )
        except Exception as e:
            logger.error(
                "链式一键创作启动失败 precreation_task_id=%s: %s",
                precreation_task_id,
                e,
                exc_info=True,
            )
            msg = str(e) if str(e) else type(e).__name__
            prepo.update(
                precreation_task_id,
                {"chain_error": msg[:2000]},
            )
            return
        tid = (out or {}).get("task_id")
        if tid:
            prepo.update(
                precreation_task_id,
                {"chained_quick_create_task_id": str(tid), "chain_error": None},
            )
    finally:
        db.close()


def run_prompt_precreation_task_sync(task_id: str) -> None:
    precreation_completed = False
    db = SessionLocal()
    try:
        crepo = CreationPromptPrecreationRepository(db)
        mrepo = MaterialCharacterRepository(db)
        task = crepo.get_by_id(task_id)
        if not task:
            return
        char = mrepo.get_by_id(task.character_id)
        if not char:
            crepo.update(
                task_id,
                {
                    "status": "failed",
                    "error_message": "角色不存在",
                    "current_step": None,
                },
            )
            return

        chara_profile = resolve_chara_profile_text(task.character_id, char.bio_json)
        if not chara_profile:
            crepo.update(
                task_id,
                {
                    "status": "failed",
                    "error_message": "请先完成角色小档案生成后再进行 Prompt 预生成",
                    "current_step": None,
                },
            )
            return

        crepo.update(
            task_id,
            {"status": "running", "current_step": "collecting", "error_message": None},
        )
        n = task.n
        seed_prompt = task.seed_prompt
        work_dir = task.work_dir
        directory_service.ensure_dir_exists(work_dir)

        candidates, compositions = _collect_candidates(
            chara_profile=chara_profile,
            seed_prompt=seed_prompt,
            work_dir=work_dir,
            n=n,
        )

        crepo.update(task_id, {"current_step": "reviewing"})
        input_content = _build_input_content(candidates)
        raw = _run_review(
            input_content=input_content,
            seed_prompt=seed_prompt,
            chara_profile=chara_profile,
            n=n,
        )
        parsed = parse_llm_json_object(raw)
        best_files = parsed.get("best_prompt_files")
        if not isinstance(best_files, list):
            raise ValueError("审阅结果缺少 best_prompt_files 数组")
        best_files = [str(x) for x in best_files]
        if len(best_files) != n:
            raise ValueError(f"审阅应返回 {n} 个文件名，实际 {len(best_files)} 个")
        for name in best_files:
            if name not in candidates:
                raise ValueError(f"审阅返回了未知候选名: {name}")

        cards = _build_cards(best_files, candidates, compositions)
        crepo.update(
            task_id,
            {
                "status": "completed",
                "current_step": None,
                "error_message": None,
                "result_json": cards,
            },
        )
        precreation_completed = True
    except Exception as e:
        logger.error("Prompt 预生成任务失败 task_id=%s: %s", task_id, e, exc_info=True)
        msg = str(e) if str(e) else type(e).__name__
        try:
            crepo = CreationPromptPrecreationRepository(db)
            if crepo.get_by_id(task_id):
                crepo.update(
                    task_id,
                    {"status": "failed", "error_message": msg, "current_step": None},
                )
        except Exception:
            logger.exception("写入任务失败状态时出错")
    finally:
        db.close()

    if precreation_completed:
        _try_chain_quick_create(task_id)


class PromptPrecreationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CreationPromptPrecreationRepository(db)
        self.material_repo = MaterialCharacterRepository(db)

    def _parse_cards(self, task: Any) -> List[Dict[str, Any]]:
        if not task or not task.result_json:
            return []
        try:
            cards = json.loads(task.result_json)
            if isinstance(cards, list):
                return cards
        except json.JSONDecodeError:
            return []
        return []

    def _build_history_detail(self, task: Any) -> Optional[Dict[str, Any]]:
        if not task:
            return None
        character = self.material_repo.get_by_id(task.character_id)
        return self._build_history_detail_from_parts(task, character)

    def _build_history_detail_from_parts(
        self, task: Any, character: Any
    ) -> Optional[Dict[str, Any]]:
        """供批量装配使用：character 已由上层一次性查询。"""
        if not task:
            return None
        chara_name = character.name if character else "未知角色"
        cards = self._parse_cards(task)
        return {
            "id": task.id,
            "task_id": task.id,
            "character_id": task.character_id,
            "chara_name": chara_name,
            "chara_avatar": "",
            "seed_prompt": task.seed_prompt,
            "prompt_count": len(cards),
            "status": task.status,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "cards": cards,
        }

    def _build_history_index_item(self, detail: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": detail["id"],
            "task_id": detail["task_id"],
            "character_id": detail["character_id"],
            "chara_name": detail["chara_name"],
            "chara_avatar": detail["chara_avatar"],
            "seed_prompt": detail["seed_prompt"],
            "prompt_count": detail["prompt_count"],
            "status": detail["status"],
            "error_message": detail.get("error_message"),
            "created_at": _to_iso(detail.get("created_at")),
            "updated_at": _to_iso(detail.get("updated_at")),
        }

    def list_history(
        self,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        lim = max(1, min(int(limit), 200))
        off = max(0, int(offset))
        st = (status or "").strip() or None
        tasks = self.repo.list_history(limit=lim, offset=off, status=st)
        items: List[Dict[str, Any]] = []
        for task in tasks:
            detail = self._build_history_detail(task)
            if not detail:
                continue
            item = self._build_history_index_item(detail)
            items.append(item)
        return {"items": items, "total": self.repo.count_history(st)}

    def get_history_detail(self, history_id: str) -> Optional[Dict[str, Any]]:
        hid = (history_id or "").strip()
        if not hid:
            return None
        task = self.repo.get_by_id(hid)
        if not task:
            return None
        return self._build_history_detail(task)

    def get_latest_history(self) -> Optional[Dict[str, Any]]:
        task = self.repo.get_latest()
        if not task:
            return None
        return self._build_history_detail(task)

    def get_latest_completed_history(self) -> Optional[Dict[str, Any]]:
        """供「一键创作」默认关联：全库最近一条已完成的任务（含 cards）。"""
        task = self.repo.get_latest_completed()
        if not task:
            return None
        return self._build_history_detail(task)

    def delete_history(self, history_id: str) -> Dict[str, Any]:
        hid = (history_id or "").strip()
        if not hid:
            raise ValueError("history_id 无效")
        task = self.repo.get_by_id(hid)
        if not task:
            raise ValueError("历史记录不存在")
        work_dir = task.work_dir
        deleted = self.repo.delete(hid)
        if not deleted:
            raise ValueError("历史记录不存在")

        if work_dir:
            try:
                if os.path.isdir(work_dir):
                    shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                logger.warning("删除历史工作目录失败: %s", work_dir, exc_info=True)

        latest = self.get_latest_history()
        return {"deleted_id": hid, "latest": latest}

    async def _run_task_async(self, task_id: str) -> None:
        await asyncio.to_thread(run_prompt_precreation_task_sync, task_id)

    def start_prompt_precreation(
        self,
        character_id: str,
        seed_prompt: str,
        count: int,
        background_tasks: Optional[BackgroundTasks] = None,
        chain_quick_create: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if count not in (1, 2, 3, 4):
            raise ValueError("生成数量必须为 1、2、3 或 4")
        sp = (seed_prompt or "").strip()
        if not sp:
            raise ValueError("种子提示词不能为空")

        char = self.material_repo.get_by_id(character_id)
        if not char:
            raise ValueError("角色不存在")

        chara_profile = resolve_chara_profile_text(character_id, char.bio_json)
        if not chara_profile:
            raise ValueError("请先完成角色小档案生成后再进行 Prompt 预生成")

        cq = bool(chain_quick_create)
        cn: Optional[int] = None
        car: Optional[str] = None
        cm: Optional[int] = None
        if chain_quick_create:
            cn = int(chain_quick_create["n"])
            car = str(chain_quick_create["aspect_ratio"]).strip()
            cm = int(chain_quick_create["max_prompts"])

        task = self.repo.create(
            character_id=character_id,
            seed_prompt=sp,
            n=count,
            status="pending",
            chain_quick_create=cq,
            chain_qc_n=cn,
            chain_qc_aspect_ratio=car,
            chain_qc_max_prompts=cm,
        )
        directory_service.ensure_dir_exists(task.work_dir)

        if background_tasks:
            background_tasks.add_task(self._run_task_async, task.id)
        else:
            run_prompt_precreation_task_sync(task.id)

        task = self.repo.get_by_id(task.id)
        return {"task_id": task.id, "status": task.status if task else "pending"}

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.repo.get_by_id(task_id)
        if not task:
            return None
        cards = None
        if task.status == "completed" and task.result_json:
            try:
                cards = json.loads(task.result_json)
                if not isinstance(cards, list):
                    cards = None
            except json.JSONDecodeError:
                cards = None
        return {
            "task_id": task.id,
            "character_id": task.character_id,
            "status": task.status,
            "error_message": task.error_message,
            "current_step": task.current_step,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "cards": cards,
            "chained_quick_create_task_id": getattr(
                task, "chained_quick_create_task_id", None
            ),
            "chain_error": getattr(task, "chain_error", None),
        }
