import os
import logging
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.datetime_display import configure_logging

configure_logging(logging.INFO)
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
# - timeout：连接级 busy 等待（秒），与 PRAGMA busy_timeout 配合缓解并发锁竞争
# - WAL：读写并发更友好，避免后台任务写库时 API 长时间阻塞事件循环
_connect_kw = {"check_same_thread": False, "timeout": 30.0}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_kw,
    pool_pre_ping=True,
    echo=False,  # 设置为 True 可以查看 SQL 日志
)
logger.info("数据库引擎创建成功")

# 长时间后台任务（如预生成后链式一键创作）专用：不占用主连接池，避免 QueuePool 耗尽
background_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_kw,
    poolclass=NullPool,
    echo=False,
)
logger.info("数据库后台引擎（NullPool）创建成功")


@event.listens_for(engine, "connect")
def _sqlite_on_connect(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
    finally:
        cursor.close()


@event.listens_for(background_engine, "connect")
def _sqlite_on_connect_background(dbapi_connection, _connection_record):
    _sqlite_on_connect(dbapi_connection, _connection_record)


# Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
BackgroundSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=background_engine)

# 基类
Base = declarative_base()


def get_db():
    """获取数据库 Session（FastAPI 依赖注入用）"""
    db = SessionLocal()
    try:
        logger.debug("获取数据库会话")
        yield db
    except Exception as e:
        # 路由层主动抛出的 HTTP 错误会经 yield 依赖传回此处，不应记为数据库异常
        if isinstance(e, StarletteHTTPException):
            raise
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


def migrate_material_raw_images_add_type() -> None:
    """
    轻量迁移：为 material_character_raw_images 表补充 type 列。
    历史数据默认回填 official。
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='material_character_raw_images'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(text("PRAGMA table_info(material_character_raw_images)")).fetchall()
            names = {c[1] for c in cols}
            if "type" not in names:
                conn.execute(
                    text(
                        "ALTER TABLE material_character_raw_images ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'official'"
                    )
                )
            conn.execute(
                text(
                    "UPDATE material_character_raw_images SET type='official' "
                    "WHERE type IS NULL OR TRIM(type)=''"
                )
            )
        logger.info("已迁移: material_character_raw_images 增加 type 列并回填历史数据")
    except Exception as e:
        logger.error(f"迁移 material_character_raw_images.type 失败: {e}", exc_info=True)
        raise


def migrate_material_characters_add_setting_source_filename() -> None:
    """
    轻量迁移：为 material_characters 表补充 setting_source_filename 列（可空）。
    历史数据为 NULL，与「无来源文件名」语义一致，不影响既有 setting_text。
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='material_characters'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(text("PRAGMA table_info(material_characters)")).fetchall()
            names = {c[1] for c in cols}
            if "setting_source_filename" in names:
                return
            conn.execute(
                text(
                    "ALTER TABLE material_characters ADD COLUMN setting_source_filename VARCHAR(255)"
                )
            )
        logger.info("已迁移: material_characters 增加 setting_source_filename 列")
    except Exception as e:
        logger.error(f"迁移 material_characters.setting_source_filename 失败: {e}", exc_info=True)
        raise


def migrate_repair_tasks_add_aspect_ratio() -> None:
    """
    轻量迁移：为 repair_tasks 表补充 aspect_ratio 列（与前端 / nano_banana_pro 一致）。
    新建库由 create_all 直接带列；老库通过 ALTER TABLE 补齐（无 Alembic）。
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='repair_tasks'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(text("PRAGMA table_info(repair_tasks)")).fetchall()
            names = {c[1] for c in cols}
            if "aspect_ratio" in names:
                return
            conn.execute(
                text(
                    "ALTER TABLE repair_tasks ADD COLUMN aspect_ratio VARCHAR(20) NOT NULL DEFAULT '16:9'"
                )
            )
        logger.info("已迁移: repair_tasks 增加 aspect_ratio 列")
    except Exception as e:
        logger.error(f"迁移 repair_tasks.aspect_ratio 失败: {e}", exc_info=True)
        raise


def migrate_creation_quick_create_tasks_add_seed_prompt() -> None:
    """
    轻量迁移：为 creation_quick_create_tasks 表补充 seed_prompt 列。
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='creation_quick_create_tasks'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(
                text("PRAGMA table_info(creation_quick_create_tasks)")
            ).fetchall()
            names = {c[1] for c in cols}
            if "seed_prompt" in names:
                return
            conn.execute(
                text(
                    "ALTER TABLE creation_quick_create_tasks ADD COLUMN seed_prompt TEXT NOT NULL DEFAULT ''"
                )
            )
        logger.info("已迁移: creation_quick_create_tasks 增加 seed_prompt 列")
    except Exception as e:
        logger.error(
            f"迁移 creation_quick_create_tasks.seed_prompt 失败: {e}", exc_info=True
        )
        raise


def migrate_creation_prompt_precreation_tasks_add_chain_fields() -> None:
    """
    为 creation_prompt_precreation_tasks 补充链式一键创作相关列。
    新建库由 create_all 直接带列；老库通过 ALTER TABLE 补齐。
    """
    if not os.path.exists(DB_PATH):
        return
    table = "creation_prompt_precreation_tasks"
    alters: list[tuple[str, str]] = [
        ("chain_quick_create", "INTEGER NOT NULL DEFAULT 0"),
        ("chain_qc_n", "INTEGER"),
        ("chain_qc_aspect_ratio", "VARCHAR(20)"),
        ("chain_qc_max_prompts", "INTEGER"),
        ("chained_quick_create_task_id", "VARCHAR(64)"),
        ("chain_error", "TEXT"),
    ]
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table}'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            names = {c[1] for c in cols}
            for col_name, col_def in alters:
                if col_name in names:
                    continue
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                )
                logger.info("已迁移: %s 增加列 %s", table, col_name)
        logger.info("已迁移: creation_prompt_precreation_tasks 链式一键创作列（如需）")
    except Exception as e:
        logger.error(
            "迁移 creation_prompt_precreation_tasks 链式列失败: %s",
            e,
            exc_info=True,
        )
        raise


def init_db():
    """初始化数据库，创建所有表"""
    logger.info("========== 开始初始化数据库 ==========")
    try:
        # 导入所有模型，确保它们被注册
        from app.models.repair import RepairTask, PromptTemplate
        from app.models.material import (
            MaterialCharacter,
            MaterialCharacterRawImage,
            MaterialCharaProfileTask,
            MaterialCreationAdviceTask,
            MaterialStandardPhotoTask,
        )
        from app.models.creation import CreationPromptPrecreationTask, CreationQuickCreateTask  # noqa: F401

        Base.metadata.create_all(bind=engine)
        migrate_prompt_templates_add_description()
        migrate_prompt_templates_add_tags()
        migrate_material_raw_images_add_type()
        migrate_material_characters_add_setting_source_filename()
        migrate_repair_tasks_add_aspect_ratio()
        migrate_creation_quick_create_tasks_add_seed_prompt()
        migrate_creation_prompt_precreation_tasks_add_chain_fields()
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
