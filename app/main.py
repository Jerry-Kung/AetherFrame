import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import pages, api, repair, material, creation

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class _SuppressPollAccessLog(logging.Filter):
    """轮询类 GET 请求频率高，默认不写入 uvicorn access 日志，避免刷屏"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        if "GET " not in msg:
            return True
        # 修补任务状态轮询
        if "/api/repair/tasks/" in msg and "/status HTTP" in msg:
            return False
        # 素材加工 · 拍摄标准照任务状态轮询
        if "/standard-photo/status HTTP" in msg:
            return False
        # 素材加工 · 角色小档案任务状态轮询
        if "/chara-profile/status HTTP" in msg:
            return False
        # 创作 · Prompt 预生成任务状态轮询
        if "/prompt-precreation/tasks/" in msg and "/status HTTP" in msg:
            return False
        return True


logging.getLogger("uvicorn.access").addFilter(_SuppressPollAccessLog())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("========== AetherFrame 应用启动 ==========")

    # 初始化 data 目录结构
    try:
        from app.services import directory_service

        logger.info("开始初始化 data 目录结构...")
        directory_service.initialize_data_directory()
        logger.info("data 目录结构初始化完成")

        # 清理临时文件
        logger.info("开始清理临时文件...")
        temp_cleaned = directory_service.cleanup_temp_files()
        logger.info(f"临时文件清理完成: 删除 {temp_cleaned} 个文件")

        # 检查目录健康状态
        health = directory_service.check_data_directory_health()
        if health["issues"]:
            logger.warning(f"目录健康检查发现问题: {health['issues']}")
        else:
            logger.info("目录健康检查通过")

    except Exception as e:
        logger.error(f"目录初始化失败: {e}", exc_info=True)
        raise

    # 初始化数据库
    try:
        from app.models.database import init_db
        from app.scripts.init_db import init_prompt_templates

        logger.info("开始初始化数据库...")
        init_db()
        logger.info("数据库表结构初始化完成")

        logger.info("开始初始化 Prompt 模板...")
        init_prompt_templates()
        logger.info("Prompt 模板初始化完成")

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        raise

    try:
        from app.services.startup_image_tasks import run_fail_inflight_image_generation_tasks

        run_fail_inflight_image_generation_tasks()
    except Exception as e:
        logger.exception(
            "启动时将未完成图片生成任务标记为失败时出错（不阻断服务启动）: %s", e
        )

    logger.info("========== 应用初始化完成 ==========")
    yield
    logger.info("========== 应用关闭 ==========")


app = FastAPI(lifespan=lifespan)

# 使用绝对路径，避免路径问题
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# API 路由应在 SPA catch-all 之前；/health 也必须在 catch-all 之前，否则会被 GET /{path:path} 抢走
@app.get("/health")
async def health_check():
    """健康检查端点"""
    from app.models.database import check_db_connection, get_db_info
    from app.services import directory_service

    db_ok = check_db_connection()
    db_info = get_db_info()
    dir_health = directory_service.check_data_directory_health()

    overall_status = "ok"
    if not db_ok or dir_health["issues"]:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "service": "AetherFrame",
        "database": {"connected": db_ok, "info": db_info},
        "directories": dir_health,
    }


app.include_router(api.router)
app.include_router(repair.router)
app.include_router(material.router)
app.include_router(creation.router)
app.include_router(pages.router)
