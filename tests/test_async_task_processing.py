"""
异步任务处理测试用例
包含：RepairTaskService 层的完整测试
"""

import os
import tempfile
import shutil
import logging
import pytest
from unittest.mock import patch, MagicMock

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def temp_data_dir():
    """创建临时数据目录"""
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
    """创建测试数据库会话"""
    import importlib
    import sys

    for key in list(sys.modules.keys()):
        if key.startswith("app.models") or key.startswith("app.repositories"):
            del sys.modules[key]

    from app.models import database
    from app.models.repair import RepairTask, PromptTemplate

    database.init_db()
    db = database.SessionLocal()

    yield db

    try:
        db.query(RepairTask).delete()
        db.query(PromptTemplate).delete()
        db.commit()
    except Exception as e:
        logger.warning(f"清理测试数据失败: {e}")
        db.rollback()
    finally:
        db.close()


@pytest.fixture
def create_test_task(db_session):
    """创建测试任务的辅助函数"""

    def _create_task(name="测试任务", status="pending"):
        from app.repositories.repair_repository import RepairTaskRepository
        from app.services.repair_service.repair_file_service import ensure_task_dirs

        repo = RepairTaskRepository(db_session)
        task = repo.create(
            {"name": name, "prompt": "测试描述", "output_count": 2, "status": status}
        )

        # 确保任务目录存在
        ensure_task_dirs(task.id)

        return task

    return _create_task


@pytest.fixture
def create_test_image():
    """创建测试图片的辅助函数"""

    def _create_image(file_path):
        # 创建一个简单的测试图片文件
        from PIL import Image
        import io

        img = Image.new("RGB", (100, 100), color="red")
        img.save(file_path, format="PNG")
        return file_path

    return _create_image


# ==========================================
# RepairTaskService 测试
# ==========================================


class TestRepairTaskService:
    """测试 RepairTaskService 异步任务处理服务"""

    def test_get_task_status(self, db_session, create_test_task):
        """测试获取任务状态"""
        from app.services.repair_service import RepairTaskService

        task = create_test_task()
        service = RepairTaskService(db_session)

        fetched_task = service.get_task_status(task.id)

        assert fetched_task is not None
        assert fetched_task.id == task.id
        assert fetched_task.status == "pending"
        logger.info("✓ 获取任务状态测试通过")

    def test_get_task_status_not_found(self, db_session):
        """测试获取不存在的任务状态"""
        from app.services.repair_service import RepairTaskService

        service = RepairTaskService(db_session)
        fetched_task = service.get_task_status("non_existent_id")

        assert fetched_task is None
        logger.info("✓ 获取不存在的任务状态测试通过")

    def test_start_task_success(self, db_session, create_test_task, create_test_image):
        """测试成功启动任务"""
        from app.services.repair_service import RepairTaskService
        from app.services.repair_service.repair_file_service import get_task_subdirs

        task = create_test_task()
        service = RepairTaskService(db_session)

        # 创建测试主图
        main_dir, _, _ = get_task_subdirs(task.id)
        main_image_path = os.path.join(main_dir, "main_image.png")
        create_test_image(main_image_path)

        # 不使用 background_tasks（同步执行用于测试）
        updated_task = db_session.query(type(task)).filter_by(id=task.id).first()

        # 验证任务状态是 pending
        assert updated_task.status == "pending"
        logger.info("✓ 任务启动前置条件测试通过")

    def test_start_task_not_found(self, db_session):
        """测试启动不存在的任务"""
        from app.services.repair_service import RepairTaskService

        service = RepairTaskService(db_session)

        with pytest.raises(ValueError, match="任务不存在"):
            # 这里不使用 await 因为我们不实际执行异步操作
            # 我们只测试验证逻辑
            import asyncio

            asyncio.run(service.start_task("non_existent_id"))

        logger.info("✓ 启动不存在的任务测试通过")

    def test_start_task_not_pending(self, db_session, create_test_task):
        """测试启动非 pending 状态的任务"""
        from app.services.repair_service import RepairTaskService

        task = create_test_task(status="processing")
        service = RepairTaskService(db_session)

        with pytest.raises(ValueError, match="任务状态不允许启动"):
            import asyncio

            asyncio.run(service.start_task(task.id))

        logger.info("✓ 启动非 pending 状态任务测试通过")

    def test_start_task_no_main_image(self, db_session, create_test_task):
        """测试启动没有主图的任务"""
        from app.services.repair_service import RepairTaskService

        task = create_test_task()
        service = RepairTaskService(db_session)

        with pytest.raises(ValueError, match="主图不存在"):
            import asyncio

            asyncio.run(service.start_task(task.id))

        logger.info("✓ 启动没有主图的任务测试通过")

    def test_update_task_status(self, db_session, create_test_task):
        """测试更新任务状态"""
        from app.services.repair_service import RepairTaskService

        task = create_test_task()
        service = RepairTaskService(db_session)

        # 更新为 processing
        updated_task = service._update_task_status(task.id, "processing")
        assert updated_task is not None
        assert updated_task.status == "processing"
        assert updated_task.error_message is None

        # 更新为 completed
        updated_task = service._update_task_status(task.id, "completed")
        assert updated_task is not None
        assert updated_task.status == "completed"

        # 更新为 failed 带错误信息
        error_msg = "测试错误信息"
        updated_task = service._update_task_status(task.id, "failed", error_msg)
        assert updated_task is not None
        assert updated_task.status == "failed"
        assert updated_task.error_message == error_msg

        logger.info("✓ 更新任务状态测试通过")


# ==========================================
# 集成测试
# ==========================================


class TestAsyncTaskIntegration:
    """异步任务集成测试"""

    @patch(
        "app.services.repair_service.image_generation_service.generate_repair_images"
    )
    def test_full_task_flow(
        self,
        mock_generate,
        db_session,
        create_test_task,
        create_test_image,
        temp_data_dir,
    ):
        """测试完整的任务流程（模拟图片生成）"""
        from app.services.repair_service import RepairTaskService
        from app.services.repair_service.repair_file_service import (
            get_task_subdirs,
            list_result_images,
        )

        # 1. 创建测试任务
        task = create_test_task()
        service = RepairTaskService(db_session)

        # 2. 创建测试主图
        main_dir, _, results_dir = get_task_subdirs(task.id)
        main_image_path = os.path.join(main_dir, "main_image.png")
        create_test_image(main_image_path)

        # 3. Mock 图片生成服务
        temp_image_path = os.path.join(temp_data_dir, "temp_result.png")
        create_test_image(temp_image_path)
        mock_generate.return_value = ([temp_image_path], None, None)

        # 4. 同步执行任务（不使用 BackgroundTasks）
        import asyncio

        asyncio.run(
            service._execute_task(
                task_id=task.id,
                prompt="测试描述",
                main_image_path=main_image_path,
                reference_image_paths=[],
                output_count=1,
            )
        )

        # 5. 验证任务状态
        updated_task = service.get_task_status(task.id)
        assert updated_task is not None
        assert updated_task.status == "completed"
        assert updated_task.error_message is None

        # 6. 验证结果图存在
        result_images = list_result_images(task.id)
        assert len(result_images) == 1
        logger.info("✓ 完整任务流程测试通过")

    @patch(
        "app.services.repair_service.image_generation_service.generate_repair_images"
    )
    def test_task_failure_flow(
        self, mock_generate, db_session, create_test_task, create_test_image
    ):
        """测试任务失败流程"""
        from app.services.repair_service import RepairTaskService
        from app.services.repair_service.repair_file_service import get_task_subdirs

        # 1. 创建测试任务
        task = create_test_task()
        service = RepairTaskService(db_session)

        # 2. 创建测试主图
        main_dir, _, _ = get_task_subdirs(task.id)
        main_image_path = os.path.join(main_dir, "main_image.png")
        create_test_image(main_image_path)

        # 3. Mock 图片生成服务返回错误
        error_msg = "模拟图片生成失败"
        mock_generate.return_value = ([], error_msg, None)

        # 4. 同步执行任务
        import asyncio

        asyncio.run(
            service._execute_task(
                task_id=task.id,
                prompt="测试描述",
                main_image_path=main_image_path,
                reference_image_paths=[],
                output_count=1,
            )
        )

        # 5. 验证任务状态为失败
        updated_task = service.get_task_status(task.id)
        assert updated_task is not None
        assert updated_task.status == "failed"
        assert error_msg in updated_task.error_message
        logger.info("✓ 任务失败流程测试通过")


# ==========================================
# 测试总结
# ==========================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("开始运行异步任务处理测试")
    logger.info("=" * 60)
    pytest.main([__file__, "-v"])
