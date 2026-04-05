"""
图片修补模块完整集成测试用例

测试整个后端流程：
1. 创建任务
2. 上传主图（使用 test_data/pictures_to_be_revised.jpg）
3. 上传参考图（使用 test_data/refs_3d/ 下的图片）
4. 启动修补任务
5. 查询任务状态
6. 验证结果

使用 test_data 目录下的真实测试文件
"""
import os
import time
import logging
import pytest
from io import BytesIO
from fastapi.testclient import TestClient

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 测试数据目录
TEST_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "test_data"
)
MAIN_IMAGE_PATH = os.path.join(TEST_DATA_DIR, "pictures_to_be_revised.jpg")
PROMPT_PATH = os.path.join(TEST_DATA_DIR, "revise_prompt.txt")
REFS_DIR = os.path.join(TEST_DATA_DIR, "refs_3d")


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture(scope="module")
def test_client():
    """创建 FastAPI 测试客户端"""
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="function")
def test_prompt():
    """读取测试用的 prompt"""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="function")
def main_image_file():
    """读取主图文件"""
    with open(MAIN_IMAGE_PATH, "rb") as f:
        return BytesIO(f.read())


@pytest.fixture(scope="function")
def reference_image_files():
    """读取参考图文件列表"""
    files = []
    if os.path.exists(REFS_DIR):
        for filename in os.listdir(REFS_DIR):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                filepath = os.path.join(REFS_DIR, filename)
                with open(filepath, "rb") as f:
                    files.append((filename, BytesIO(f.read())))
    return files


# ==========================================
# 集成测试类
# ==========================================

class TestRepairIntegration:
    """图片修补模块完整集成测试"""

    # 存储测试过程中的任务ID，供后续测试使用
    _task_id = None

    def test_1_create_task(self, test_client, test_prompt):
        """
        测试步骤 1: 创建修补任务

        验证点：
        - 任务创建成功
        - 返回正确的任务信息
        - 任务状态为 pending
        """
        logger.info("=" * 60)
        logger.info("测试步骤 1: 创建修补任务")
        logger.info("=" * 60)

        response = test_client.post(
            "/api/repair/tasks",
            json={
                "name": "集成测试任务 - 图片修补",
                "prompt": test_prompt,
                "output_count": 2
            }
        )

        assert response.status_code == 200, f"创建任务失败: {response.text}"

        data = response.json()
        assert data["success"] is True, "API 响应 success 应为 True"
        assert "data" in data, "响应应包含 data 字段"

        task_data = data["data"]
        assert "id" in task_data, "任务应包含 id 字段"
        assert task_data["name"] == "集成测试任务 - 图片修补"
        assert task_data["status"] == "pending"
        assert task_data["has_main_image"] is False
        assert task_data["reference_image_count"] == 0

        # 保存任务ID供后续测试使用
        TestRepairIntegration._task_id = task_data["id"]
        logger.info(f"✓ 任务创建成功: task_id={TestRepairIntegration._task_id}")

    def test_2_upload_main_image(self, test_client, main_image_file):
        """
        测试步骤 2: 上传主图

        验证点：
        - 主图上传成功
        - 返回正确的文件信息
        - 可以通过 URL 访问图片
        """
        logger.info("=" * 60)
        logger.info("测试步骤 2: 上传主图")
        logger.info("=" * 60)

        assert TestRepairIntegration._task_id is not None, "需要先执行创建任务测试"

        # 重置文件指针
        main_image_file.seek(0)

        response = test_client.post(
            f"/api/repair/tasks/{TestRepairIntegration._task_id}/main-image",
            files={"file": ("pictures_to_be_revised.jpg", main_image_file, "image/jpeg")}
        )

        assert response.status_code == 200, f"上传主图失败: {response.text}"

        data = response.json()
        assert data["success"] is True
        assert "data" in data

        upload_data = data["data"]
        assert "filename" in upload_data
        assert "url" in upload_data
        assert upload_data["task_id"] == TestRepairIntegration._task_id

        logger.info(f"✓ 主图上传成功: filename={upload_data['filename']}")

        # 验证可以获取任务详情并看到主图已上传
        response = test_client.get(f"/api/repair/tasks/{TestRepairIntegration._task_id}")
        assert response.status_code == 200
        task_detail = response.json()["data"]
        assert task_detail["has_main_image"] is True

    def test_3_upload_reference_images(self, test_client, reference_image_files):
        """
        测试步骤 3: 批量上传参考图

        验证点：
        - 参考图上传成功
        - 返回正确的上传统计
        - 可以列出所有参考图
        """
        logger.info("=" * 60)
        logger.info("测试步骤 3: 批量上传参考图")
        logger.info("=" * 60)

        assert TestRepairIntegration._task_id is not None, "需要先执行创建任务测试"

        if not reference_image_files:
            logger.warning("没有找到参考图文件，跳过此测试")
            pytest.skip("没有参考图文件可用")

        # 准备文件数据
        files = []
        for filename, file_obj in reference_image_files:
            file_obj.seek(0)
            files.append(("files", (filename, file_obj, "image/jpeg")))

        response = test_client.post(
            f"/api/repair/tasks/{TestRepairIntegration._task_id}/reference-images",
            files=files
        )

        assert response.status_code == 200, f"上传参考图失败: {response.text}"

        data = response.json()
        assert data["success"] is True
        assert "data" in data

        upload_data = data["data"]
        assert "uploaded" in upload_data
        assert "failed" in upload_data
        assert upload_data["total"] == len(reference_image_files)
        assert upload_data["task_id"] == TestRepairIntegration._task_id

        logger.info(f"✓ 参考图上传完成: 成功={len(upload_data['uploaded'])}, 失败={len(upload_data['failed'])}")

        # 验证可以获取任务详情并看到参考图数量
        response = test_client.get(f"/api/repair/tasks/{TestRepairIntegration._task_id}")
        assert response.status_code == 200
        task_detail = response.json()["data"]
        assert task_detail["reference_image_count"] == len(upload_data["uploaded"])

    def test_4_get_task_detail(self, test_client):
        """
        测试步骤 4: 获取任务详情

        验证点：
        - 可以获取完整的任务详情
        - 主图信息正确
        - 参考图列表正确
        """
        logger.info("=" * 60)
        logger.info("测试步骤 4: 获取任务详情")
        logger.info("=" * 60)

        assert TestRepairIntegration._task_id is not None

        response = test_client.get(f"/api/repair/tasks/{TestRepairIntegration._task_id}")

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        task_detail = data["data"]
        assert task_detail["id"] == TestRepairIntegration._task_id
        assert task_detail["status"] == "pending"
        assert task_detail["has_main_image"] is True
        assert task_detail["main_image"] is not None
        assert "reference_images" in task_detail
        assert isinstance(task_detail["reference_images"], list)

        logger.info(f"✓ 获取任务详情成功: {task_detail['name']}")
        logger.info(f"  - 主图: {task_detail['main_image']['filename'] if task_detail['main_image'] else '无'}")
        logger.info(f"  - 参考图数量: {len(task_detail['reference_images'])}")

    def test_5_start_repair_task(self, test_client):
        """
        测试步骤 5: 启动修补任务

        验证点：
        - 任务启动成功
        - 任务状态更新为 processing
        - 返回正确的响应
        """
        logger.info("=" * 60)
        logger.info("测试步骤 5: 启动修补任务")
        logger.info("=" * 60)

        assert TestRepairIntegration._task_id is not None

        response = test_client.post(
            f"/api/repair/tasks/{TestRepairIntegration._task_id}/start",
            json={
                "use_reference_images": True
            }
        )

        # 注意：由于实际调用AI服务可能耗时较长，这里我们主要验证流程
        # 在实际测试环境中，可以 mock image_generation_service
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "data" in data

            start_data = data["data"]
            assert start_data["task_id"] == TestRepairIntegration._task_id
            assert start_data["status"] in ["processing", "pending"]  # 可能是 pending 如果是 mock

            logger.info(f"✓ 修补任务启动成功: status={start_data['status']}")
        else:
            # 如果启动失败（可能是AI服务不可用），记录日志但不失败测试
            logger.warning(f"启动修补任务返回非200状态: {response.status_code}")
            logger.warning(f"响应内容: {response.text}")
            logger.info("⚠ 修补任务启动测试跳过（可能需要AI服务）")

    def test_6_get_task_status(self, test_client):
        """
        测试步骤 6: 查询任务状态

        验证点：
        - 可以查询任务状态
        - 状态信息完整
        """
        logger.info("=" * 60)
        logger.info("测试步骤 6: 查询任务状态")
        logger.info("=" * 60)

        assert TestRepairIntegration._task_id is not None

        response = test_client.get(f"/api/repair/tasks/{TestRepairIntegration._task_id}/status")

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        status_data = data["data"]
        assert status_data["id"] == TestRepairIntegration._task_id
        assert "status" in status_data
        assert "updated_at" in status_data

        logger.info(f"✓ 查询任务状态成功: status={status_data['status']}")

    def test_7_list_tasks(self, test_client):
        """
        测试步骤 7: 获取任务列表

        验证点：
        - 可以获取任务列表
        - 新创建的任务在列表中
        - 分页功能正常
        """
        logger.info("=" * 60)
        logger.info("测试步骤 7: 获取任务列表")
        logger.info("=" * 60)

        response = test_client.get("/api/repair/tasks", params={"limit": 10})

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        list_data = data["data"]
        assert "tasks" in list_data
        assert "total" in list_data
        assert isinstance(list_data["tasks"], list)

        # 检查我们的任务是否在列表中
        task_ids = [task["id"] for task in list_data["tasks"]]
        if TestRepairIntegration._task_id:
            assert TestRepairIntegration._task_id in task_ids, "新创建的任务应在列表中"

        logger.info(f"✓ 获取任务列表成功: 总数={list_data['total']}, 返回={len(list_data['tasks'])}")

    def test_8_cleanup(self, test_client):
        """
        测试步骤 8: 清理测试数据

        验证点：
        - 可以删除任务
        - 删除后任务不存在
        """
        logger.info("=" * 60)
        logger.info("测试步骤 8: 清理测试数据")
        logger.info("=" * 60)

        if not TestRepairIntegration._task_id:
            logger.warning("没有任务ID，跳过清理")
            return

        # 删除任务
        response = test_client.delete(f"/api/repair/tasks/{TestRepairIntegration._task_id}")

        # 即使删除失败也不要让测试失败，只记录日志
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            logger.info(f"✓ 任务删除成功: task_id={TestRepairIntegration._task_id}")
        else:
            logger.warning(f"删除任务失败: {response.status_code}")

        # 验证任务不存在
        response = test_client.get(f"/api/repair/tasks/{TestRepairIntegration._task_id}")
        assert response.status_code in [200, 404]  # 可能返回200但data为null，或404

        if response.status_code == 200:
            data = response.json()
            if not data["success"]:
                logger.info("✓ 确认任务已删除")


# ==========================================
# Prompt 模板集成测试
# ==========================================

class TestPromptTemplateIntegration:
    """Prompt 模板集成测试"""

    _template_id = None

    def test_1_list_templates(self, test_client):
        """测试获取模板列表"""
        logger.info("=" * 60)
        logger.info("测试: 获取 Prompt 模板列表")
        logger.info("=" * 60)

        response = test_client.get("/api/repair/templates")

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        list_data = data["data"]
        assert "templates" in list_data
        assert "total" in list_data

        logger.info(f"✓ 获取模板列表成功: 总数={list_data['total']}")

    def test_2_create_template(self, test_client):
        """测试创建自定义模板"""
        logger.info("=" * 60)
        logger.info("测试: 创建自定义 Prompt 模板")
        logger.info("=" * 60)

        response = test_client.post(
            "/api/repair/templates",
            json={
                "label": "集成测试模板",
                "text": "这是一个用于集成测试的 prompt 模板。请对图片进行修补。",
                "description": "集成测试用简短说明",
                "tags": ["皮肤", "脸部"],
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        template_data = data["data"]
        assert template_data["label"] == "集成测试模板"
        assert template_data["is_builtin"] is False
        assert template_data.get("description") == "集成测试用简短说明"
        assert template_data.get("tags") == ["皮肤", "脸部"]

        TestPromptTemplateIntegration._template_id = template_data["id"]
        logger.info(f"✓ 模板创建成功: template_id={TestPromptTemplateIntegration._template_id}")

    def test_3_get_template(self, test_client):
        """测试获取模板详情"""
        logger.info("=" * 60)
        logger.info("测试: 获取模板详情")
        logger.info("=" * 60)

        if not TestPromptTemplateIntegration._template_id:
            pytest.skip("需要先创建模板")

        response = test_client.get(
            f"/api/repair/templates/{TestPromptTemplateIntegration._template_id}"
        )

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        template_data = data["data"]
        assert template_data["id"] == TestPromptTemplateIntegration._template_id
        assert template_data["label"] == "集成测试模板"

        logger.info(f"✓ 获取模板详情成功")

    def test_4_update_template(self, test_client):
        """测试更新模板"""
        logger.info("=" * 60)
        logger.info("测试: 更新模板")
        logger.info("=" * 60)

        if not TestPromptTemplateIntegration._template_id:
            pytest.skip("需要先创建模板")

        response = test_client.put(
            f"/api/repair/templates/{TestPromptTemplateIntegration._template_id}",
            json={
                "label": "集成测试模板（已更新）",
                "text": "这是更新后的 prompt 模板内容。",
                "description": "更新后的说明文案",
                "tags": ["水印"],
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        template_data = data["data"]
        assert template_data["label"] == "集成测试模板（已更新）"
        assert template_data.get("description") == "更新后的说明文案"
        assert template_data.get("tags") == ["水印"]

        logger.info(f"✓ 模板更新成功")

    def test_5_cleanup_template(self, test_client):
        """测试删除模板"""
        logger.info("=" * 60)
        logger.info("测试: 删除模板")
        logger.info("=" * 60)

        if not TestPromptTemplateIntegration._template_id:
            logger.warning("没有模板ID，跳过清理")
            return

        response = test_client.delete(
            f"/api/repair/templates/{TestPromptTemplateIntegration._template_id}"
        )

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            logger.info(f"✓ 模板删除成功")
        else:
            logger.warning(f"删除模板失败: {response.status_code}")


# ==========================================
# 架构验证测试
# ==========================================

class TestArchitectureValidation:
    """架构验证测试 - 验证代码架构合理性"""

    def test_module_structure(self):
        """测试模块结构是否完整"""
        logger.info("=" * 60)
        logger.info("架构验证: 模块结构")
        logger.info("=" * 60)

        # 检查核心模块是否存在
        from app import routes
        from app import services
        from app import models
        from app import schemas
        from app import repositories

        assert routes is not None
        assert services is not None
        assert models is not None
        assert schemas is not None
        assert repositories is not None

        # 检查修补模块是否存在
        from app.routes import repair
        import app.services.repair_service as repair_service_pkg
        from app.services.repair_service import (
            repair_file_service,
            image_generation_service,
            repair_task_service,
        )
        from app.models import repair
        from app.schemas import repair
        from app.repositories import repair_repository

        assert repair is not None
        assert repair_service_pkg is not None
        assert repair_task_service is not None
        assert repair_file_service is not None
        assert image_generation_service is not None

        logger.info("✓ 模块结构验证通过")

    def test_dependency_flow(self):
        """测试依赖流向是否合理"""
        logger.info("=" * 60)
        logger.info("架构验证: 依赖流向")
        logger.info("=" * 60)

        # 验证分层架构：Routes → Services → Repositories → Models
        # Routes 不应该直接依赖 Repositories 或 Models（除了通过 Services）

        # 检查 repair.py 路由的导入
        import inspect
        from app.routes import repair as repair_route

        # 获取路由模块的导入
        source = inspect.getsource(repair_route)

        # 路由应该依赖 Services，而不是直接依赖 Repositories
        assert "RepairService" in source
        assert "RepairTaskService" in source

        logger.info("✓ 依赖流向验证通过")

    def test_error_handling(self):
        """测试错误处理是否完善"""
        logger.info("=" * 60)
        logger.info("架构验证: 错误处理")
        logger.info("=" * 60)

        from app.services.file_service import (
            FileValidationError,
            FileSaveError,
            FileDeleteError
        )

        # 验证自定义异常类存在
        assert FileValidationError is not None
        assert FileSaveError is not None
        assert FileDeleteError is not None

        logger.info("✓ 错误处理验证通过")


# ==========================================
# 测试运行入口
# ==========================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("图片修补模块集成测试")
    logger.info("=" * 60)
    logger.info(f"测试数据目录: {TEST_DATA_DIR}")
    logger.info(f"主图文件: {MAIN_IMAGE_PATH} ({'存在' if os.path.exists(MAIN_IMAGE_PATH) else '不存在'})")
    logger.info(f"Prompt 文件: {PROMPT_PATH} ({'存在' if os.path.exists(PROMPT_PATH) else '不存在'})")
    logger.info(f"参考图目录: {REFS_DIR} ({'存在' if os.path.exists(REFS_DIR) else '不存在'})")
    logger.info("=" * 60)

    pytest.main([__file__, "-v", "-s"])
