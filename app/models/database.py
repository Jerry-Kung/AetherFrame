import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 数据库文件路径
DATA_DIR = os.getenv("DATA_DIR", "./data")
DB_DIR = os.path.join(DATA_DIR, "db")
DB_PATH = os.path.join(DB_DIR, "aetherframe.db")

logger.info(f"数据库目录: {DB_DIR}")
logger.info(f"数据库文件: {DB_PATH}")

# 确保目录存在
os.makedirs(DB_DIR, exist_ok=True)
logger.info("数据库目录已创建/确认存在")

# SQLite 连接字符串
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
logger.info(f"数据库连接URL: {SQLALCHEMY_DATABASE_URL}")

# 创建引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # 设置为 True 可以查看 SQL 日志
)
logger.info("数据库引擎创建成功")

# Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
Base = declarative_base()


def get_db():
    """获取数据库 Session（FastAPI 依赖注入用）"""
    db = SessionLocal()
    try:
        logger.debug("获取数据库会话")
        yield db
    except Exception as e:
        logger.error(f"数据库会话异常: {e}", exc_info=True)
        raise
    finally:
        logger.debug("关闭数据库会话")
        db.close()


def migrate_prompt_templates_add_description() -> None:
    """
    轻量迁移：为已存在的 prompt_templates 表补充 description 列。
    新建库由 create_all 直接带列；老库通过 ALTER TABLE 补齐（无 Alembic）。
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='prompt_templates'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(text("PRAGMA table_info(prompt_templates)")).fetchall()
            names = {c[1] for c in cols}
            if "description" in names:
                return
            conn.execute(
                text(
                    "ALTER TABLE prompt_templates ADD COLUMN description VARCHAR(100) NOT NULL DEFAULT ''"
                )
            )
        logger.info("已迁移: prompt_templates 增加 description 列")
    except Exception as e:
        logger.error(f"迁移 prompt_templates.description 失败: {e}", exc_info=True)
        raise


def migrate_prompt_templates_add_tags() -> None:
    """
    轻量迁移：为已存在的 prompt_templates 表补充 tags 列（JSON 文本，默认 []）。
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='prompt_templates'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(text("PRAGMA table_info(prompt_templates)")).fetchall()
            names = {c[1] for c in cols}
            if "tags" in names:
                return
            conn.execute(
                text(
                    "ALTER TABLE prompt_templates ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'"
                )
            )
        logger.info("已迁移: prompt_templates 增加 tags 列")
    except Exception as e:
        logger.error(f"迁移 prompt_templates.tags 失败: {e}", exc_info=True)
        raise


def init_db():
    """初始化数据库，创建所有表"""
    logger.info("========== 开始初始化数据库 ==========")
    try:
        # 导入所有模型，确保它们被注册
        from app.models.repair import RepairTask, PromptTemplate

        Base.metadata.create_all(bind=engine)
        migrate_prompt_templates_add_description()
        migrate_prompt_templates_add_tags()
        logger.info("所有数据表创建成功")
        logger.info("========== 数据库初始化完成 ==========")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        raise


def check_db_connection() -> bool:
    """检查数据库连接是否正常"""
    logger.debug("检查数据库连接...")
    try:
        db = SessionLocal()
        # 执行一个简单的查询来验证连接
        db.execute(text("SELECT 1"))
        db.close()
        logger.debug("数据库连接正常")
        return True
    except Exception as e:
        logger.error(f"数据库连接失败: {e}", exc_info=True)
        return False


def get_db_info() -> dict:
    """获取数据库信息"""
    info = {
        "database_path": DB_PATH,
        "database_dir": DB_DIR,
        "connection_url": SQLALCHEMY_DATABASE_URL,
        "directory_exists": os.path.exists(DB_DIR),
        "database_exists": os.path.exists(DB_PATH),
    }
    
    if os.path.exists(DB_PATH):
        info["database_size_bytes"] = os.path.getsize(DB_PATH)
    
    return info
