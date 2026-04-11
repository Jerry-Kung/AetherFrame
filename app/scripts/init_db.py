import logging
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 添加上级目录到路径，确保可以导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.models.database import SessionLocal, init_db
from app.models.repair import PromptTemplate


def init_prompt_templates():
    """
    Prompt 模板初始化：不再写入任何默认内置模板。
    启动时删除数据库中 is_builtin=True 的历史种子行，避免旧环境残留 6 条内置模板。
    用户模板均为自定义，通过 API 创建。
    """
    logger.info("========== Prompt 模板初始化 ==========")
    db = SessionLocal()
    try:
        q = db.query(PromptTemplate).filter(PromptTemplate.is_builtin == True)
        count = q.count()
        if count:
            q.delete(synchronize_session=False)
            db.commit()
            logger.info(f"已移除历史内置模板: {count} 条")
        else:
            logger.info("无内置模板记录需清理")
        logger.info("========== Prompt 模板初始化完成 ==========")
    except Exception as e:
        db.rollback()
        logger.error(f"初始化模板失败: {e}", exc_info=True)
        raise
    finally:
        db.close()


def initialize_database():
    """完整初始化数据库"""
    logger.info("========================================")
    logger.info("开始完整初始化数据库")
    logger.info("========================================")

    # 1. 创建表
    init_db()

    # 2. 清理历史内置模板（不注入新默认模板）
    init_prompt_templates()

    logger.info("========================================")
    logger.info("数据库完整初始化成功！")
    logger.info("========================================")


if __name__ == "__main__":
    try:
        initialize_database()
        sys.exit(0)
    except Exception as e:
        logger.error(f"初始化过程发生错误: {e}", exc_info=True)
        sys.exit(1)
