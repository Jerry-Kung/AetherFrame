"""跨 material 任务表的共享并发限流闸门。

Task 01 阶段只跟踪 MaterialCreativeDirectionTask；
Task 02 将扩展 count 函数 UNION 进 MaterialSeedPromptTask（届时通过修改本文件实现）。
"""
import asyncio
import logging

from sqlalchemy.orm import Session

from app.config import (
    MATERIAL_TASK_PER_CHARACTER_LIMIT,
    MATERIAL_LLM_GLOBAL_CONCURRENCY,
)
from app.models.material import MaterialCreativeDirectionTask

logger = logging.getLogger(__name__)

_global_llm_semaphore = asyncio.Semaphore(MATERIAL_LLM_GLOBAL_CONCURRENCY)


class CharacterConcurrencyError(Exception):
    """超出角色级并发限制。路由层翻译为 409 + code=MATERIAL_TASK_CONCURRENCY_EXCEEDED。"""


class CreativeDirectionLimitExceededError(Exception):
    """方向总数达到 MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT。"""


def count_inflight_tasks_for_character(db: Session, character_id: str) -> int:
    """统计该角色当前 in-flight 的任务总数（跨任务表）。"""
    return (
        db.query(MaterialCreativeDirectionTask)
        .filter(
            MaterialCreativeDirectionTask.character_id == character_id,
            MaterialCreativeDirectionTask.status.in_(["pending", "processing"]),
        )
        .count()
    )


def assert_can_start_task(db: Session, character_id: str) -> None:
    """提交任务前调用；超出限制时抛 CharacterConcurrencyError。"""
    n = count_inflight_tasks_for_character(db, character_id)
    if n >= MATERIAL_TASK_PER_CHARACTER_LIMIT:
        logger.info(
            "character %s reached task concurrency limit (in-flight=%d, limit=%d)",
            character_id,
            n,
            MATERIAL_TASK_PER_CHARACTER_LIMIT,
        )
        raise CharacterConcurrencyError()


def get_global_llm_semaphore() -> asyncio.Semaphore:
    """获取全局 LLM 信号量。后台任务在调用 LLM 前 async with 该信号量。"""
    return _global_llm_semaphore
