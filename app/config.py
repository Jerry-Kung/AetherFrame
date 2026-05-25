"""
非敏感项目配置 —— 严禁与 app/tools/llm/config.py（敏感凭据，已 gitignore）混用。

本文件**入库**（不在 .gitignore 中），承载项目级非敏感配置常量。
如需按环境覆盖，在本文件内通过 os.getenv 兜底；不要新建二级配置文件。
"""
import os


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ─── 创意方向 / 种子提示词数量上限（Task 01 仅用到方向上限；其余常量本切片预留位） ───
MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT = _int_env(
    "MATERIAL_CREATIVE_DIRECTION_PER_CHARACTER_LIMIT", 20
)

# 任务并发限流
MATERIAL_TASK_PER_CHARACTER_LIMIT = _int_env("MATERIAL_TASK_PER_CHARACTER_LIMIT", 2)
MATERIAL_LLM_GLOBAL_CONCURRENCY = _int_env("MATERIAL_LLM_GLOBAL_CONCURRENCY", 4)

# 任务表保留窗口（启动期清理钩子使用，task-01c 接入）
MATERIAL_TASK_RETENTION_DAYS = _int_env("MATERIAL_TASK_RETENTION_DAYS", 30)

# initial_input 字符上限（前后端硬限）
MATERIAL_CREATIVE_DIRECTION_INITIAL_INPUT_MAX = _int_env(
    "MATERIAL_CREATIVE_DIRECTION_INITIAL_INPUT_MAX", 500
)
