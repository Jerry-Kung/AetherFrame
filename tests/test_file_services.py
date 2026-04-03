"""
文件服务整合测试用例
包含：通用文件服务、目录服务、修补模块文件服务的完整测试
"""
import os
import tempfile
import shutil
import logging
import time
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


@pytest.fixture
def sample_image_bytes():
    """创建简单的 PNG 图片字节数据（1x1 透明像素）"""
    return (
        b'\x89PNG\r\n\x1a\n'
        b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
        b'\x00\x00\x00\x00IEND\xaeB`\x82'
    )


class MockUploadFile:
    """模拟 FastAPI UploadFile 对象"""
    def __init__(self, filename: str, content: bytes, content_type: str = "image/png"):
        self.filename = filename
        self.content_type = content_type
        self.file = BytesIO(content)


# ==========================================
# 第一部分：通用文件服务测试
# ==========================================

class TestFileService:
    """测试通用文件服务"""
    
    def test_sanitize_filename(self, temp_data_dir):
        """测试文件名安全化"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import file_service
        
        test_cases = [
            ("../etc/passwd", "__etc_passwd"),
            ("file/name.png", "file_name.png"),
            ('file"name.png', "file_name.png"),
            ("file*name?.png", "file_name_.png"),
        ]
        
        for input_name, expected in test_cases:
            result = file_service.sanitize_filename(input_name)
            assert result == expected, f"{input_name} → {result} (期望: {expected})"
        
        logger.info("文件名安全化测试通过")
    
    def test_save_and_get_file(self, temp_data_dir, sample_image_bytes):
        """测试保存和获取文件"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import file_service
        
        test_dir = os.path.join(temp_data_dir, "test")
        file = MockUploadFile("test.png", sample_image_bytes, "image/png")
        
        # 保存文件
        saved_name = file_service.save_uploaded_file(
            file, 
            test_dir, 
            "saved.png",
            allowed_extensions={".png"},
            allowed_mimetypes={"image/png"}
        )
        
        assert saved_name == "saved.png"
        
        # 获取文件
        filepath = file_service.get_file_path(test_dir, "saved.png")
        assert filepath is not None
        assert os.path.exists(filepath)
        
        logger.info("文件保存和获取测试通过")
    
    def test_list_and_delete_file(self, temp_data_dir, sample_image_bytes):
        """测试列出和删除文件"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import file_service
        
        test_dir = os.path.join(temp_data_dir, "test_list")
        
        # 保存多个文件
        for i in range(3):
            file = MockUploadFile(f"file{i}.png", sample_image_bytes, "image/png")
            file_service.save_uploaded_file(file, test_dir, f"file{i}.png")
        
        # 列出文件
        files = file_service.list_files_in_dir(test_dir, {".png"})
        assert len(files) == 3
        
        # 删除文件
        result = file_service.delete_file(test_dir, "file1.png")
        assert result is True
        
        # 验证删除
        files = file_service.list_files_in_dir(test_dir, {".png"})
        assert len(files) == 2
        
        logger.info("文件列出和删除测试通过")


# ==========================================
# 第二部分：目录服务测试
# ==========================================

class TestDirectoryService:
    """测试目录服务"""
    
    def test_initialize_data_directory(self, temp_data_dir):
        """测试初始化 data 目录结构"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import directory_service
        
        # 初始化目录
        directory_service.initialize_data_directory()
        
        # 验证所有必需目录都存在
        assert os.path.exists(directory_service.get_db_dir())
        assert os.path.exists(directory_service.get_repair_dir())
        assert os.path.exists(directory_service.get_repair_tasks_dir())
        assert os.path.exists(directory_service.get_repair_templates_dir())
        assert os.path.exists(directory_service.get_temp_dir())
        
        # 验证 README.md 存在
        readme_path = os.path.join(directory_service.get_data_dir(), "README.md")
        assert os.path.exists(readme_path)
        
        logger.info("data 目录结构初始化测试通过")
    
    def test_check_data_directory_health(self, temp_data_dir):
        """测试目录健康检查"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import directory_service
        
        # 初始化目录
        directory_service.initialize_data_directory()
        
        # 检查健康状态
        health = directory_service.check_data_directory_health()
        
        assert health["data_dir_exists"] is True
        assert health["db_dir_exists"] is True
        assert health["repair_dir_exists"] is True
        assert len(health["issues"]) == 0
        
        logger.info("目录健康检查测试通过")
    
    def test_cleanup_temp_files(self, temp_data_dir):
        """测试临时文件清理"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import directory_service
        
        # 初始化目录
        directory_service.initialize_data_directory()
        
        temp_dir = directory_service.get_temp_dir()
        
        # 创建临时文件
        old_time = time.time() - (25 * 3600)  # 25小时前
        
        old_file = os.path.join(temp_dir, "old.txt")
        with open(old_file, "w") as f:
            f.write("old")
        os.utime(old_file, (old_time, old_time))
        
        new_file = os.path.join(temp_dir, "new.txt")
        with open(new_file, "w") as f:
            f.write("new")
        
        # 清理
        deleted = directory_service.cleanup_temp_files(max_age_hours=24)
        
        assert deleted == 1
        assert not os.path.exists(old_file)
        assert os.path.exists(new_file)
        
        logger.info("临时文件清理测试通过")


# ==========================================
# 第三部分：修补模块文件服务测试
# ==========================================

class TestRepairFileService:
    """测试修补模块文件服务"""
    
    def test_save_and_get_main_image(self, temp_data_dir, sample_image_bytes):
        """测试保存和获取主图"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import repair_file_service
        
        task_id = "test-task-001"
        file = MockUploadFile("test.png", sample_image_bytes, "image/png")
        
        # 保存主图
        saved_name = repair_file_service.save_main_image(task_id, file)
        assert saved_name == "main_image.png"
        
        # 获取主图
        filepath = repair_file_service.get_main_image_path(task_id)
        assert filepath is not None
        assert os.path.exists(filepath)
        
        logger.info("主图保存和获取测试通过")
    
    def test_save_and_list_reference_images(self, temp_data_dir, sample_image_bytes):
        """测试保存和列出参考图"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import repair_file_service
        
        task_id = "test-task-002"
        
        # 保存参考图
        files = [
            MockUploadFile("ref1.png", sample_image_bytes, "image/png"),
            MockUploadFile("ref2.jpg", sample_image_bytes, "image/jpeg"),
        ]
        saved_names = repair_file_service.save_reference_images(task_id, files)
        
        assert len(saved_names) == 2
        
        # 列出参考图
        ref_list = repair_file_service.list_reference_images(task_id)
        assert len(ref_list) == 2
        
        logger.info("参考图保存和列出测试通过")
    
    def test_save_and_get_result_image(self, temp_data_dir, sample_image_bytes):
        """测试保存和获取结果图"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import repair_file_service
        
        task_id = "test-task-003"
        
        # 保存结果图
        saved_name = repair_file_service.save_result_image(task_id, sample_image_bytes, index=0)
        assert saved_name == "result_0.png"
        
        # 获取结果图
        filepath = repair_file_service.get_result_image_path(task_id, "result_0.png")
        assert filepath is not None
        assert os.path.exists(filepath)
        
        # 列出结果图
        result_list = repair_file_service.list_result_images(task_id)
        assert len(result_list) == 1
        
        logger.info("结果图保存和获取测试通过")
    
    def test_delete_task_files(self, temp_data_dir, sample_image_bytes):
        """测试删除任务文件"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import repair_file_service, directory_service
        
        task_id = "test-task-004"
        
        # 保存一些文件
        file = MockUploadFile("test.png", sample_image_bytes, "image/png")
        repair_file_service.save_main_image(task_id, file)
        repair_file_service.save_result_image(task_id, sample_image_bytes, index=0)
        
        # 验证目录存在
        task_dir = repair_file_service.get_task_dir(task_id)
        assert os.path.exists(task_dir)
        
        # 删除任务文件
        result = repair_file_service.delete_task_files(task_id)
        assert result is True
        
        # 验证目录不存在
        assert not os.path.exists(task_dir)
        
        logger.info("任务文件删除测试通过")


# ==========================================
# 第四部分：集成测试
# ==========================================

class TestFileServicesIntegration:
    """文件服务集成测试"""
    
    def test_full_repair_workflow(self, temp_data_dir, sample_image_bytes):
        """测试完整的修补模块文件工作流"""
        import importlib
        import sys
        
        for key in list(sys.modules.keys()):
            if key.startswith('app.services'):
                del sys.modules[key]
        
        from app.services import directory_service, repair_file_service
        
        logger.info("开始文件服务集成测试")
        
        task_id = "integration-test-001"
        
        # 1. 初始化 data 目录
        directory_service.initialize_data_directory()
        logger.info("步骤 1 完成: 初始化 data 目录")
        
        # 2. 检查健康状态
        health = directory_service.check_data_directory_health()
        assert len(health["issues"]) == 0
        logger.info("步骤 2 完成: 健康检查通过")
        
        # 3. 保存主图
        main_file = MockUploadFile("main.png", sample_image_bytes, "image/png")
        repair_file_service.save_main_image(task_id, main_file)
        logger.info("步骤 3 完成: 保存主图")
        
        # 4. 保存参考图
        ref_files = [
            MockUploadFile("ref1.png", sample_image_bytes, "image/png"),
            MockUploadFile("ref2.png", sample_image_bytes, "image/png"),
        ]
        repair_file_service.save_reference_images(task_id, ref_files)
        logger.info("步骤 4 完成: 保存参考图")
        
        # 5. 保存结果图
        repair_file_service.save_result_image(task_id, sample_image_bytes, index=0)
        logger.info("步骤 5 完成: 保存结果图")
        
        # 6. 验证文件列表
        ref_list = repair_file_service.list_reference_images(task_id)
        result_list = repair_file_service.list_result_images(task_id)
        assert len(ref_list) == 2
        assert len(result_list) == 1
        logger.info("步骤 6 完成: 验证文件列表")
        
        # 7. 删除任务文件
        repair_file_service.delete_task_files(task_id)
        logger.info("步骤 7 完成: 删除任务文件")
        
        # 8. 清理临时文件
        directory_service.cleanup_temp_files()
        logger.info("步骤 8 完成: 清理临时文件")
        
        logger.info("文件服务集成测试完整工作流通过!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
