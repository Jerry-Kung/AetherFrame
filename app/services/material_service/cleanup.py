"""启动期清理 material 模块的过期任务行。"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import MATERIAL_TASK_RETENTION_DAYS
from app.models.material import MaterialCreativeDirectionTask, MaterialSeedPromptTask

logger = logging.getLogger(__name__)


def cleanup_old_material_tasks(db: Session) -> int:
    """删除保留窗口外的 completed/failed 创意方向与种子任务行。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=MATERIAL_TASK_RETENTION_DAYS)

    n_dir = (
        db.query(MaterialCreativeDirectionTask)
        .filter(
            MaterialCreativeDirectionTask.status.in_(["completed", "failed"]),
            MaterialCreativeDirectionTask.created_at < cutoff,
        )
        .delete(synchronize_session=False)
    )
    n_seed = (
        db.query(MaterialSeedPromptTask)
        .filter(
            MaterialSeedPromptTask.status.in_(["completed", "failed"]),
            MaterialSeedPromptTask.created_at < cutoff,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    total = n_dir + n_seed
    if total > 0:
        logger.info(
            "cleanup: deleted %d direction tasks + %d seed tasks (cutoff=%s)",
            n_dir,
            n_seed,
            cutoff.isoformat(),
        )
    return total
