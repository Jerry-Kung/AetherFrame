import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.creation_batch import CreationBatchRun, CreationBatchRunItem

logger = logging.getLogger(__name__)


def _new_run_id() -> str:
    return f"bb_run_{uuid.uuid4().hex[:12]}"


def _new_item_id() -> str:
    return f"bb_item_{uuid.uuid4().hex[:12]}"


class CreationBatchRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(
        self,
        *,
        iterations_total: int,
        config_json: str,
        status: str = "pending",
    ) -> CreationBatchRun:
        run = CreationBatchRun(
            id=_new_run_id(),
            status=status,
            iterations_total=iterations_total,
            iterations_done=0,
            config_json=config_json,
            error_message=None,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_run(self, run_id: str, updates: Dict[str, Any]) -> Optional[CreationBatchRun]:
        run = self.get_run(run_id)
        if not run:
            return None
        for k, v in updates.items():
            if hasattr(run, k):
                setattr(run, k, v)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_run(self, run_id: str) -> Optional[CreationBatchRun]:
        return self.db.query(CreationBatchRun).filter(CreationBatchRun.id == run_id).first()

    def create_item(
        self,
        *,
        run_id: str,
        step_index: int,
        character_id: str,
        seed_prompt_id: str,
        seed_section: str,
        seed_prompt_text: str,
        status: str = "pending",
    ) -> CreationBatchRunItem:
        item = CreationBatchRunItem(
            id=_new_item_id(),
            run_id=run_id,
            step_index=step_index,
            character_id=character_id,
            seed_prompt_id=seed_prompt_id,
            seed_section=seed_section,
            seed_prompt_text=seed_prompt_text,
            prompt_precreation_task_id=None,
            quick_create_task_id=None,
            status=status,
            error_message=None,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> Optional[CreationBatchRunItem]:
        item = self.get_item(item_id)
        if not item:
            return None
        for k, v in updates.items():
            if hasattr(item, k):
                setattr(item, k, v)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_item(self, item_id: str) -> Optional[CreationBatchRunItem]:
        return self.db.query(CreationBatchRunItem).filter(CreationBatchRunItem.id == item_id).first()

    def list_items_for_run(self, run_id: str) -> List[CreationBatchRunItem]:
        return (
            self.db.query(CreationBatchRunItem)
            .filter(CreationBatchRunItem.run_id == run_id)
            .order_by(CreationBatchRunItem.step_index.asc())
            .all()
        )

    def delete_item_row(self, item_id: str) -> bool:
        item = self.get_item(item_id)
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def list_all_items(self, *, limit: int, offset: int) -> List[CreationBatchRunItem]:
        return (
            self.db.query(CreationBatchRunItem)
            .order_by(desc(CreationBatchRunItem.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_all_items(self) -> int:
        return self.db.query(CreationBatchRunItem).count()

    def bump_run_iterations_done(self, run_id: str, delta: int = 1) -> None:
        run = self.get_run(run_id)
        if not run:
            return
        run.iterations_done = int(run.iterations_done or 0) + delta
        self.db.commit()
