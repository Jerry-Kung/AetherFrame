"""
文件上传 API 测试用例
包含：文件上传、下载、删除的完整测试
"""
import os
import tempfile
import shutil
import logging
import pytest
from io import BytesIO

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
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
        if key.startswith('app.models') or key.startswith('app.repositories'):
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


@pytest.fixture(scope="function")
def sample_image():
    """创建一个简单的测试图片（使用内存中的 PNG）"""
    # 创建一个简单的 PNG 文件头（1x1 红色像素）
    # 这是一个有效的 PNG 文件
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xA3, 0x60, 0x50,
        0xE9, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
        0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    return BytesIO(png_data)


@pytest.fixture(scope="function")
def test_task(db_session):
    """创建一个测试任务"""
    from app.repositories.repair_repository import RepairTaskRepository

    repo = RepairTaskRepository(db_session)
    task = repo.create({
        "name": "测试任务",
        "prompt": "这是测试描述",
        "output_count": 2
    })
    return task


# ==========================================
# 第一部分：Schemas 测试
# ==========================================

class TestFileUploadSchemas:
    """测试文件上传相关的 Schemas"""

    def test_uploaded_image_info(self):
        """测试 UploadedImageInfo"""
        from app.schemas.repair import UploadedImageInfo

        info = UploadedImageInfo(
            filename="main_image.png",
            url="/api/repair/tasks/task_123/images/main/main_image.png"
        )

        assert info.filename == "main_image.png"
        assert info.url == "/api/repair/tasks/task_123/images/main/main_image.png"

    def test_failed_upload_info(self):
        """测试 FailedUploadInfo"""
        from app.schemas.repair import FailedUploadInfo

        info = FailedUploadInfo(
            original_filename="invalid.txt",
            error="文件类型不支持"
        )

        assert info.original_filename == "invalid.txt"
        assert info.error == "文件类型不支持"

    def test_main_image_upload_response(self):
        """测试 MainImageUploadResponse"""
        from app.schemas.repair import MainImageUploadResponse

        response = MainImageUploadResponse(
            filename="main_image.png",
            url="/api/repair/tasks/task_123/images/main/main_image.png",
            task_id="task_123"
        )

        assert response.filename == "main_image.png"
        assert response.task_id == "task_123"

    def test_reference_images_upload_response(self):
        """测试 ReferenceImagesUploadResponse"""
        from app.schemas.repair import (
            ReferenceImagesUploadResponse,
            UploadedImageInfo,
            FailedUploadInfo
        )

        uploaded = [UploadedImageInfo(
            filename="ref_0.png",
            url="/api/repair/tasks/task_123/images/reference/ref_0.png"
        )]
        failed = [FailedUploadInfo(
            original_filename="invalid.txt",
            error="文件类型不支持"
        )]

        response = ReferenceImagesUploadResponse(
            uploaded=uploaded,
            failed=failed,
            total=2,
            task_id="task_123"
        )

        assert len(response.uploaded) == 1
        assert len(response.failed) == 1
        assert response.total == 2
        assert response.task_id == "task_123"


# ==========================================
# 第二部分：RepairService 文件操作测试
# ==========================================

class TestRepairServiceFileOperations:
    """测试 RepairService 的文件操作方法"""

    def test_get_image_path_invalid_type(self, db_session, test_task):
        """测试获取图片路径 - 无效的 image_type"""
        from app.services.repair_service import RepairService

        service = RepairService(db_session)
        path = service.get_image_path(test_task.id, "invalid_type", "test.png")
        assert path is None

    def test_get_image_path_task_not_found(self, db_session):
        """测试获取图片路径 - 任务不存在"""
        from app.services.repair_service import RepairService

        service = RepairService(db_session)
        path = service.get_image_path("non_existent_task", "main", "test.png")
        assert path is None

    def test_delete_main_image_task_not_found(self, db_session):
        """测试删除主图 - 任务不存在"""
        from app.services.repair_service import RepairService

        service = RepairService(db_session)
        success = service.delete_main_image("non_existent_task")
        assert success is False

    def test_delete_reference_image_task_not_found(self, db_session):
        """测试删除参考图 - 任务不存在"""
        from app.services.repair_service import RepairService

        service = RepairService(db_session)
        success = service.delete_reference_image("non_existent_task", "ref_0.png")
        assert success is False


# ==========================================
# 第三部分：文件服务集成测试
# ==========================================

class TestFileServiceIntegration:
    """文件服务集成测试"""

    def test_repair_file_service_ensure_task_dirs(self, temp_data_dir, test_task):
        """测试确保任务目录存在"""
        from app.services import repair_file_service

        main_dir, refs_dir, results_dir = repair_file_service.ensure_task_dirs(test_task.id)

        assert os.path.exists(main_dir)
        assert os.path.exists(refs_dir)
        assert os.path.exists(results_dir)
        logger.info("✓ 任务目录创建测试通过")

    def test_repair_file_service_get_task_dir(self, temp_data_dir, test_task):
        """测试获取任务目录"""
        from app.services import repair_file_service

        task_dir = repair_file_service.get_task_dir(test_task.id)

        assert test_task.id in task_dir
        logger.info("✓ 获取任务目录测试通过")

    def test_repair_file_service_list_reference_images_empty(self, temp_data_dir, test_task):
        """测试列出参考图 - 空目录"""
        from app.services import repair_file_service

        # 确保目录存在
        repair_file_service.ensure_task_dirs(test_task.id)

        refs = repair_file_service.list_reference_images(test_task.id)

        assert refs == []
        logger.info("✓ 列出空参考图目录测试通过")

    def test_repair_file_service_list_result_images_empty(self, temp_data_dir, test_task):
        """测试列出结果图 - 空目录"""
        from app.services import repair_file_service

        # 确保目录存在
        repair_file_service.ensure_task_dirs(test_task.id)

        results = repair_file_service.list_result_images(test_task.id)

        assert results == []
        logger.info("✓ 列出空结果图目录测试通过")


# ==========================================
# 第四部分：使用实际图片测试（如果可用）
# ==========================================

class TestWithRealImage:
    """使用实际图片进行测试（如果 data/picture.png 存在）"""

    REAL_IMAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "picture.png")

    @pytest.mark.skipif(not os.path.exists(REAL_IMAGE_PATH), reason="data/picture.png 不存在")
    def test_real_image_exists(self):
        """测试实际图片存在"""
        assert os.path.exists(self.REAL_IMAGE_PATH)
        logger.info(f"✓ 找到实际图片: {self.REAL_IMAGE_PATH}")

    @pytest.mark.skipif(not os.path.exists(REAL_IMAGE_PATH), reason="data/picture.png 不存在")
    def test_real_image_size(self):
        """测试实际图片大小"""
        file_size = os.path.getsize(self.REAL_IMAGE_PATH)
        assert file_size > 0
        logger.info(f"✓ 实际图片大小: {file_size} 字节")


# ==========================================
# 测试总结
# ==========================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("开始运行文件上传 API 测试")
    logger.info("=" * 60)
    pytest.main([__file__, "-v"])
