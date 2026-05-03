"""
共享测试 fixtures 和配置
集中管理所有测试模块共享的 fixtures，减少代码重复
"""

import os
import tempfile
import shutil
import logging
from io import BytesIO
import pytest

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def temp_data_dir():
    """创建临时数据目录 - 所有测试共享"""
    temp_dir = tempfile.mkdtemp()
    logger.info(f"创建临时数据目录: {temp_dir}")

    original_data_dir = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = temp_dir

    yield temp_dir

    if original_data_dir:
        os.environ["DATA_DIR"] = original_data_dir
    else:
        os.environ.pop("DATA_DIR", None)

    try:
        shutil.rmtree(temp_dir)
        logger.info(f"清理临时数据目录: {temp_dir}")
    except Exception as e:
        logger.warning(f"清理临时目录失败: {e}")


@pytest.fixture(scope="function")
def db_session(temp_data_dir):
    """创建测试数据库会话 - 所有测试共享"""
    import importlib
    import sys

    for key in list(sys.modules.keys()):
        if key.startswith("app.models") or key.startswith("app.repositories"):
            del sys.modules[key]

    from app.models import database
    from app.models.repair import RepairTask, PromptTemplate
    from app.models.material import (
        MaterialCharacterRawImage,
        MaterialCharacter,
        MaterialStandardPhotoTask,
    )
    from app.models.creation import CreationPromptPrecreationTask, CreationQuickCreateTask
    from app.models.creation_batch import CreationBatchRunItem, CreationBatchRun

    database.init_db()
    db = database.SessionLocal()

    yield db

    try:
        db.query(CreationBatchRunItem).delete()
        db.query(CreationBatchRun).delete()
        db.query(CreationQuickCreateTask).delete()
        db.query(CreationPromptPrecreationTask).delete()
        db.query(MaterialCharacterRawImage).delete()
        db.query(MaterialStandardPhotoTask).delete()
        db.query(MaterialCharacter).delete()
        db.query(RepairTask).delete()
        db.query(PromptTemplate).delete()
        db.commit()
    except Exception as e:
        logger.warning(f"清理测试数据失败: {e}")
        db.rollback()
    finally:
        db.close()


@pytest.fixture(scope="function")
def sample_image():
    """创建一个简单的测试图片（使用内存中的 PNG）- 文件上传测试共享"""
    # 创建一个简单的 PNG 文件头（1x1 红色像素）
    png_data = bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x02,
            0x00,
            0x00,
            0x00,
            0x90,
            0x77,
            0x53,
            0xDE,
            0x00,
            0x00,
            0x00,
            0x0C,
            0x49,
            0x44,
            0x41,
            0x54,
            0x08,
            0xD7,
            0x63,
            0xF8,
            0xFF,
            0xFF,
            0x3F,
            0x00,
            0x05,
            0xFE,
            0x02,
            0xFE,
            0xA3,
            0x60,
            0x50,
            0xE9,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )
    return BytesIO(png_data)


@pytest.fixture(scope="function")
def test_task(db_session):
    """创建一个测试任务 - 任务和文件测试共享"""
    from app.repositories.repair_repository import RepairTaskRepository

    repo = RepairTaskRepository(db_session)
    task = repo.create(
        {"name": "测试任务", "prompt": "这是测试描述", "output_count": 2}
    )
    return task


@pytest.fixture(scope="function")
def repair_service(db_session):
    """创建 RepairService 实例 - 服务层测试共享"""
    from app.services.repair_service import RepairService

    return RepairService(db_session)


@pytest.fixture(scope="function")
def repair_task_service(db_session):
    """创建 RepairTaskService 实例 - 异步修补任务测试共享"""
    from app.services.repair_service import RepairTaskService

    return RepairTaskService(db_session)
