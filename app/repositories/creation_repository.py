import json
import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.creation import CreationPromptPrecreationTask
from app.services import directory_service

logger = logging.getLogger(__name__)


class CreationPromptPrecreationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        character_id: str,
        seed_prompt: str,
        n: int,
        status: str = "pending",
    ) -> CreationPromptPrecreationTask:
        task_id = f"ppcpre_{uuid.uuid4().hex[:12]}"
        work_dir = directory_service.get_prompt_precreation_task_dir(character_id, task_id)
        task = CreationPromptPrecreationTask(
            id=task_id,
            character_id=character_id,
            seed_prompt=seed_prompt,
            n=n,
            work_dir=work_dir,
            status=status,
            error_message=None,
            result_json=None,
            current_step=None,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: str) -> Optional[CreationPromptPrecreationTask]:
        return (
            self.db.query(CreationPromptPrecreationTask)
            .filter(CreationPromptPrecreationTask.id == task_id)
            .first()
        )

    def update(self, task_id: str, updates: Dict[str, Any]) -> Optional[CreationPromptPrecreationTask]:
        task = self.get_by_id(task_id)
        if not task:
            return None
        for key, value in updates.items():
            if key == "result_json" and value is not None and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            if hasattr(task, key):
                setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        return task
