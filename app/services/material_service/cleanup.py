"""启动期清理 material 模块的过期任务行。"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import MATERIAL_TASK_RETENTION_DAYS
from app.models.material import MaterialCreativeDirectionTask

logger = logging.getLogger(__name__)


def cleanup_old_material_tasks(db: Session) -> int:
    """删除保留窗口外的 completed/failed 创意方向任务行。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=MATERIAL_TASK_RETENTION_DAYS)
    n = (
        db.query(MaterialCreativeDirectionTask)
        .filter(
            MaterialCreativeDirectionTask.status.in_(["completed", "failed"]),
            MaterialCreativeDirectionTask.created_at < cutoff,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    if n > 0:
        logger.info("cleanup: deleted %d old direction tasks (cutoff=%s)", n, cutoff.isoformat())
    return n
