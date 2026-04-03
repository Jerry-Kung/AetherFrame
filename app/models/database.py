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


def init_db():
    """初始化数据库，创建所有表"""
    logger.info("========== 开始初始化数据库 ==========")
    try:
        # 导入所有模型，确保它们被注册
        from app.models.repair import RepairTask, PromptTemplate
        
        Base.metadata.create_all(bind=engine)
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
