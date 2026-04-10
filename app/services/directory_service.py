import os
import logging
import time
import shutil
from typing import Optional, List

# 配置日志
logger = logging.getLogger(__name__)

# 配置
DATA_DIR = os.getenv("DATA_DIR", "./data")


# ==========================================
# 目录路径配置
# ==========================================


def get_data_dir() -> str:
    """获取数据根目录的绝对路径"""
    abs_path = os.path.abspath(DATA_DIR)
    logger.debug(f"数据根目录: {abs_path}")
    return abs_path


def get_db_dir() -> str:
    """获取数据库目录"""
    return os.path.join(get_data_dir(), "db")


def get_repair_dir() -> str:
    """获取图片修补模块目录"""
    return os.path.join(get_data_dir(), "repair")


def get_repair_tasks_dir() -> str:
    """获取修补任务目录"""
    return os.path.join(get_repair_dir(), "tasks")


def get_repair_templates_dir() -> str:
    """获取修补模板目录"""
    return os.path.join(get_repair_dir(), "templates")


def get_material_dir() -> str:
    """获取素材加工模块目录"""
    return os.path.join(get_data_dir(), "material")


def get_material_characters_dir() -> str:
    """获取素材加工 — 角色根目录（data/material/characters）"""
    return os.path.join(get_material_dir(), "characters")


def get_beautify_dir() -> str:
    """获取美图创作模块目录（预留）"""
    return os.path.join(get_data_dir(), "beautify")


def get_prompt_precreation_task_dir(character_id: str, task_id: str) -> str:
    """Prompt 预生成任务工作目录：data/beautify/prompt_precreation/{character_id}/{task_id}/"""
    return os.path.join(get_beautify_dir(), "prompt_precreation", character_id, task_id)


def get_quick_create_task_dir(character_id: str, task_id: str) -> str:
    """一键创作任务工作目录：data/beautify/quick_create/{character_id}/{task_id}/"""
    return os.path.join(get_beautify_dir(), "quick_create", character_id, task_id)


def get_temp_dir() -> str:
    """获取临时文件目录"""
    return os.path.join(get_data_dir(), "temp")


# ==========================================
# 目录创建
# ==========================================


def ensure_dir_exists(dir_path: str, mode: int = 0o755) -> bool:
    """
    确保目录存在，不存在则创建

    Args:
        dir_path: 目录路径
        mode: 目录权限

    Returns:
        是否成功创建或已存在
    """
    os.makedirs(dir_path, mode=mode, exist_ok=True)
    return True


def create_data_readme() -> None:
    """创建 data/README.md 说明文档"""
    readme_path = os.path.join(get_data_dir(), "README.md")

    if os.path.exists(readme_path):
        logger.debug("data/README.md 已存在，跳过创建")
        return

    readme_content = """# AetherFrame Data Directory

本目录包含 AetherFrame 项目的所有用户数据。

## 目录结构

- `db/` - 数据库文件
- `repair/` - 图片修补模块数据
- `material/characters/` - 素材加工模块（按角色分子目录）
- `beautify/` - 美图创作模块（预留）
- `temp/` - 临时文件

## 备份建议

定期备份整个 data 目录以防止数据丢失。
"""

    try:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)
        logger.info("创建 data/README.md 成功")
    except Exception as e:
        logger.error(f"创建 data/README.md 失败: {e}", exc_info=True)


def initialize_data_directory() -> None:
    """
    初始化 data 目录结构

    创建所有必需的基础目录
    """
    logger.info("开始初始化 data 目录结构")

    # 确保数据根目录
    ensure_dir_exists(get_data_dir())

    # 创建 README.md
    create_data_readme()

    # 创建数据库目录
    ensure_dir_exists(get_db_dir())
    logger.info("数据库目录已确保")

    # 创建图片修补模块目录
    ensure_dir_exists(get_repair_dir())
    ensure_dir_exists(get_repair_tasks_dir())
    ensure_dir_exists(get_repair_templates_dir())
    logger.info("图片修补模块目录已确保")

    # 创建临时文件目录
    ensure_dir_exists(get_temp_dir())
    logger.info("临时文件目录已确保")

    # 创建预留模块目录（占位）
    ensure_dir_exists(get_material_dir())
    ensure_dir_exists(get_material_characters_dir())
    ensure_dir_exists(get_beautify_dir())
    logger.info("预留模块目录已确保")

    logger.info("data 目录结构初始化完成")


# ==========================================
# 目录健康检查
# ==========================================


def check_data_directory_health() -> dict:
    """
    检查 data 目录健康状态

    Returns:
        健康状态字典
    """
    logger.info("检查 data 目录健康状态")

    health_status = {
        "data_dir_exists": os.path.exists(get_data_dir()),
        "db_dir_exists": os.path.exists(get_db_dir()),
        "repair_dir_exists": os.path.exists(get_repair_dir()),
        "repair_tasks_dir_exists": os.path.exists(get_repair_tasks_dir()),
        "repair_templates_dir_exists": os.path.exists(get_repair_templates_dir()),
        "material_dir_exists": os.path.exists(get_material_dir()),
        "material_characters_dir_exists": os.path.exists(get_material_characters_dir()),
        "temp_dir_exists": os.path.exists(get_temp_dir()),
        "readme_exists": os.path.exists(os.path.join(get_data_dir(), "README.md")),
        "disk_usage_bytes": 0,
        "issues": [],
    }

    # 计算磁盘使用量
    try:
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(get_data_dir()):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
        health_status["disk_usage_bytes"] = total_size
    except Exception as e:
        logger.warning(f"计算磁盘使用量失败: {e}")
        health_status["issues"].append(f"磁盘使用量计算失败: {e}")

    # 检查问题
    if not health_status["data_dir_exists"]:
        health_status["issues"].append("数据根目录不存在")
    if not health_status["db_dir_exists"]:
        health_status["issues"].append("数据库目录不存在")
    if not health_status["repair_dir_exists"]:
        health_status["issues"].append("图片修补模块目录不存在")
    if not health_status["material_dir_exists"]:
        health_status["issues"].append("素材加工模块目录不存在")
    if not health_status["material_characters_dir_exists"]:
        health_status["issues"].append("素材加工角色目录不存在")

    logger.info(f"目录健康检查完成: {len(health_status['issues'])} 个问题")
    return health_status


# ==========================================
# 临时文件清理
# ==========================================


def cleanup_temp_files(max_age_hours: int = 24) -> int:
    """
    清理临时文件目录中的旧文件

    Args:
        max_age_hours: 最大文件年龄（小时）

    Returns:
        清理的文件数量
    """
    logger.info(f"开始清理临时文件（超过 {max_age_hours} 小时）")

    temp_dir = get_temp_dir()

    if not os.path.exists(temp_dir):
        logger.warning("临时文件目录不存在，跳过清理")
        return 0

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0

    for filename in os.listdir(temp_dir):
        filepath = os.path.join(temp_dir, filename)

        try:
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.debug(f"删除临时文件: {filepath}")
            elif os.path.isdir(filepath):
                # 检查空目录
                if not os.listdir(filepath):
                    os.rmdir(filepath)
                    logger.debug(f"删除空临时目录: {filepath}")
        except Exception as e:
            logger.warning(f"清理文件 {filepath} 失败: {e}")

    logger.info(f"临时文件清理完成: 删除 {deleted_count} 个文件")
    return deleted_count


# ==========================================
# 目录统计
# ==========================================


def get_directory_stats() -> dict:
    """
    获取目录统计信息

    Returns:
        统计信息字典
    """
    logger.info("获取目录统计信息")

    stats = {
        "data_dir": get_data_dir(),
        "total_size_bytes": 0,
        "file_count": 0,
        "dir_count": 0,
        "repair_tasks_count": 0,
        "repair_tasks_size": [],
    }

    try:
        for dirpath, dirnames, filenames in os.walk(get_data_dir()):
            stats["dir_count"] += len(dirnames)
            stats["file_count"] += len(filenames)

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    stats["total_size_bytes"] += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
    except Exception as e:
        logger.warning(f"统计目录信息失败: {e}")

    # 统计修补任务
    repair_tasks_dir = get_repair_tasks_dir()
    if os.path.exists(repair_tasks_dir):
        task_dirs = [
            d
            for d in os.listdir(repair_tasks_dir)
            if os.path.isdir(os.path.join(repair_tasks_dir, d))
        ]
        stats["repair_tasks_count"] = len(task_dirs)
        stats["repair_tasks"] = task_dirs[:10]  # 只返回前10个

    logger.info(
        f"目录统计完成: {stats['file_count']} 个文件, {stats['dir_count']} 个目录"
    )
    return stats


# ==========================================
# 数据备份辅助
# ==========================================


def create_backup_suggestion() -> dict:
    """
    生成备份建议

    Returns:
        备份建议字典
    """
    health = check_data_directory_health()
    stats = get_directory_stats()

    suggestion = {
        "should_backup": True,
        "reason": "",
        "estimated_backup_size": stats["total_size_bytes"],
        "suggested_backup_name": f"aetherframe-backup-{time.strftime('%Y%m%d-%H%M%S')}",
        "important_directories": ["db/", "repair/tasks/", "repair/templates/"],
    }

    if stats["total_size_bytes"] == 0:
        suggestion["should_backup"] = False
        suggestion["reason"] = "数据目录为空"
    elif health["issues"]:
        suggestion["reason"] = f"发现 {len(health['issues'])} 个问题需要关注"
    else:
        suggestion["reason"] = "定期备份建议"

    return suggestion
