"""全角色共享固定种子模板表访问。"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.material import FixedSeedTemplate

logger = logging.getLogger(__name__)


class FixedSeedTemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> List[FixedSeedTemplate]:
        return (
            self.db.query(FixedSeedTemplate)
            .order_by(FixedSeedTemplate.created_at.asc())
            .all()
        )

    def list_unused(self) -> List[FixedSeedTemplate]:
        return (
            self.db.query(FixedSeedTemplate)
            .filter(FixedSeedTemplate.used.is_(False))
            .order_by(FixedSeedTemplate.created_at.asc())
            .all()
        )

    def get_by_id(self, template_id: str) -> Optional[FixedSeedTemplate]:
        tid = (template_id or "").strip()
        if not tid:
            return None
        return self.db.query(FixedSeedTemplate).filter(FixedSeedTemplate.id == tid).first()

    def create(self, text: str) -> FixedSeedTemplate:
        row = FixedSeedTemplate(
            id=f"fxst_{uuid.uuid4().hex[:12]}",
            text=text,
            used=False,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(
        self,
        template_id: str,
        *,
        text: Optional[str] = None,
        used: Optional[bool] = None,
    ) -> Optional[FixedSeedTemplate]:
        row = self.get_by_id(template_id)
        if not row:
            return None
        if text is not None:
            row.text = text
        if used is not None:
            row.used = used
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, template_id: str) -> bool:
        row = self.get_by_id(template_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def delete_all(self) -> int:
        n = self.db.query(FixedSeedTemplate).delete()
        self.db.commit()
        return int(n or 0)

    def row_to_dict(self, row: FixedSeedTemplate) -> Dict[str, Any]:
        return {
            "id": row.id,
            "text": row.text or "",
            "used": bool(row.used),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
