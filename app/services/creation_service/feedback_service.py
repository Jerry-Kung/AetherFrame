"""生产出图人工 feedback：保存语义（清空即删）与全量导出聚合。

设计文档：docs/superpowers/specs/2026-07-08-production-feedback-entry-design.md §1/§2
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.creation_feedback import CreationImageFeedback
from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository
from app.repositories.creation_repository import (
    CreationPromptPrecreationRepository,
    CreationQuickCreateRepository,
)
from app.repositories.material_repository import MaterialCharacterRepository
from app.services.creation_service.quick_create_service import _parse_json_list

logger = logging.getLogger(__name__)


def serialize_feedback_row(row: CreationImageFeedback) -> Dict[str, Any]:
    return {
        "prompt_id": row.prompt_id,
        "image_index": int(row.image_index),
        "leg_foot_bad": bool(row.leg_foot_bad),
        "feedback_text": row.feedback_text or "",
    }


class ImageFeedbackService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CreationImageFeedbackRepository(db)
        self.quick_repo = CreationQuickCreateRepository(db)

    def save_feedback(
        self,
        *,
        task_id: str,
        prompt_id: str,
        image_index: int,
        feedback_text: str,
        leg_foot_bad: bool,
    ) -> Optional[Dict[str, Any]]:
        tid = (task_id or "").strip()
        pid = (prompt_id or "").strip()
        if not tid or not pid:
            raise ValueError("task_id / prompt_id 无效")
        if self.quick_repo.get_by_id(tid) is None:
            raise ValueError("一键创作任务不存在")

        text = (feedback_text or "").strip()
        bad = bool(leg_foot_bad)
        if not text and not bad:
            self.repo.delete_for_image(tid, pid, image_index)
            return None
        row = self.repo.upsert(
            quick_create_task_id=tid,
            prompt_id=pid,
            image_index=image_index,
            leg_foot_bad=bad,
            feedback_text=text,
        )
        return serialize_feedback_row(row)

    def build_export(self) -> Dict[str, Any]:
        """全量导出所有已填 feedback（spec §2.3 aetherframe_feedback_v1）。"""
        from app.models.creation_batch import CreationBatchRunItem

        rows = self.repo.list_all()
        by_task: Dict[str, List[Any]] = {}
        for r in rows:
            by_task.setdefault(r.quick_create_task_id, []).append(r)

        task_ids = list(by_task.keys())
        qc_map = self.quick_repo.get_by_ids(task_ids) if task_ids else {}

        items = (
            self.db.query(CreationBatchRunItem)
            .filter(CreationBatchRunItem.quick_create_task_id.in_(task_ids))
            .all()
            if task_ids
            else []
        )
        item_map = {it.quick_create_task_id: it for it in items}

        char_ids = list({t.character_id for t in qc_map.values() if t.character_id})
        char_map = (
            {c.id: c for c in MaterialCharacterRepository(self.db).get_by_ids(char_ids)}
            if char_ids
            else {}
        )

        title_maps = self._build_prompt_title_maps(items, char_map)

        records: List[Dict[str, Any]] = []
        for tid in sorted(by_task.keys()):
            task = qc_map.get(tid)
            if task is None:
                logger.warning("feedback 导出：一键创作任务已不存在，跳过 %s", tid)
                continue
            try:
                records.append(
                    self._build_record(
                        task, by_task[tid], item_map.get(tid), char_map,
                        title_maps.get(tid, {}),
                    )
                )
            except Exception:
                logger.exception("feedback 导出：装配记录失败，跳过 %s", tid)
        return {
            "schema": "aetherframe_feedback_v1",
            "exported_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "records": records,
        }

    def _build_prompt_title_maps(
        self, items: List[Any], char_map: Dict[str, Any]
    ) -> Dict[str, Dict[str, str]]:
        """{quick_create_task_id: {prompt_id: title}}；任何一步取不到都回落空 map。"""
        out: Dict[str, Dict[str, str]] = {}
        ppc_ids = [
            (it.prompt_precreation_task_id or "").strip()
            for it in items
            if (it.prompt_precreation_task_id or "").strip()
        ]
        if not ppc_ids:
            return out
        try:
            from app.services.creation_service.prompt_precreation_service import (
                PromptPrecreationService,
            )

            ppc_repo = CreationPromptPrecreationRepository(self.db)
            ppc_map = ppc_repo.get_by_ids(ppc_ids)
            ppc_service = PromptPrecreationService(self.db)
            for it in items:
                qc_id = (it.quick_create_task_id or "").strip()
                ppc_task = ppc_map.get((it.prompt_precreation_task_id or "").strip())
                if not qc_id or ppc_task is None:
                    continue
                detail = ppc_service._build_history_detail_from_parts(
                    ppc_task, char_map.get(ppc_task.character_id)
                )
                cards = (detail or {}).get("cards") or []
                out[qc_id] = {
                    str(c.get("id") or ""): str(c.get("title") or "").strip()
                    for c in cards
                    if isinstance(c, dict) and str(c.get("title") or "").strip()
                }
        except Exception:
            logger.warning("feedback 导出：Prompt 标题装配失败，回落 prompt_id", exc_info=True)
        return out

    @staticmethod
    def _image_path(entry: Any) -> str:
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            return str(entry.get("path") or "")
        return ""

    def _build_record(
        self,
        task: Any,
        fb_rows: List[Any],
        item: Optional[Any],
        char_map: Dict[str, Any],
        title_map: Dict[str, str],
    ) -> Dict[str, Any]:
        results = _parse_json_list(task.result_json)
        result_by_pid = {
            str(r.get("prompt_id") or ""): r for r in results if isinstance(r, dict)
        }

        fb_by_prompt: Dict[str, List[Any]] = {}
        for fb in sorted(fb_rows, key=lambda r: (r.prompt_id, r.image_index)):
            fb_by_prompt.setdefault(fb.prompt_id, []).append(fb)

        prompt_groups: List[Dict[str, Any]] = []
        for pid, fbs in fb_by_prompt.items():
            res = result_by_pid.get(pid) or {}
            gen = res.get("generated_images") or []
            images = [
                {
                    "image_index": int(fb.image_index),
                    "image_path": self._image_path(gen[fb.image_index])
                    if 0 <= fb.image_index < len(gen)
                    else "",
                    "leg_foot_bad": bool(fb.leg_foot_bad),
                    "feedback_text": fb.feedback_text or "",
                }
                for fb in fbs
            ]
            prompt_groups.append(
                {
                    "prompt_id": pid,
                    "prompt_title": title_map.get(pid) or pid,
                    "full_prompt": str(res.get("full_prompt") or ""),
                    "total_images": len(gen),
                    "images": images,
                }
            )

        ch = char_map.get(task.character_id)
        return {
            "batch_item_id": item.id if item is not None else None,
            "quick_create_task_id": task.id,
            "character_id": task.character_id,
            "character_name": ch.name if ch is not None else "未知角色",
            "seed_prompt_id": item.seed_prompt_id if item is not None else None,
            "seed_section": item.seed_section if item is not None else None,
            "seed_prompt_text": item.seed_prompt_text
            if item is not None
            else (task.seed_prompt or ""),
            "created_at": task.created_at.isoformat() if task.created_at else "",
            "prompt_groups": prompt_groups,
        }
