import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.creation import CreationPromptPrecreationTask, CreationQuickCreateTask
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

    def get_latest_completed_by_character_id(
        self, character_id: str
    ) -> Optional[CreationPromptPrecreationTask]:
        return (
            self.db.query(CreationPromptPrecreationTask)
            .filter(
                CreationPromptPrecreationTask.character_id == character_id,
                CreationPromptPrecreationTask.status == "completed",
            )
            .order_by(desc(CreationPromptPrecreationTask.updated_at))
            .first()
        )


class CreationQuickCreateRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        character_id: str,
        n: int,
        aspect_ratio: str,
        selected_prompts: List[Dict[str, Any]],
        status: str = "pending",
    ) -> CreationQuickCreateTask:
        task_id = f"qcreate_{uuid.uuid4().hex[:12]}"
        work_dir = directory_service.get_quick_create_task_dir(character_id, task_id)
        task = CreationQuickCreateTask(
            id=task_id,
            character_id=character_id,
            n=n,
            aspect_ratio=aspect_ratio,
            selected_prompts_json=json.dumps(selected_prompts, ensure_ascii=False),
            status=status,
            error_message=None,
            result_json=None,
            work_dir=work_dir,
            current_step=None,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: str) -> Optional[CreationQuickCreateTask]:
        return (
            self.db.query(CreationQuickCreateTask)
            .filter(CreationQuickCreateTask.id == task_id)
            .first()
        )

    def update(self, task_id: str, updates: Dict[str, Any]) -> Optional[CreationQuickCreateTask]:
        task = self.get_by_id(task_id)
        if not task:
            return None
        for key, value in updates.items():
            if key in ("result_json", "selected_prompts_json") and value is not None and not isinstance(
                value, str
            ):
                value = json.dumps(value, ensure_ascii=False)
            if hasattr(task, key):
                setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        return task
