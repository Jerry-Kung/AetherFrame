"""
任务 CRUD API 测试用例
包含：Schemas 层、Service 层的完整测试
"""

import os
import tempfile
import shutil
import logging
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


# ==========================================
# 第一部分：Schemas 层测试
# ==========================================


class TestSchemas:
    """测试 Pydantic Schemas"""

    def test_task_create_valid(self):
        """测试 TaskCreate 验证 - 有效数据"""
        from app.schemas.repair import TaskCreate

        task_data = TaskCreate(name="测试任务", prompt="这是测试描述", output_count=2)

        assert task_data.name == "测试任务"
        assert task_data.prompt == "这是测试描述"
        assert task_data.output_count == 2
        assert task_data.aspect_ratio == "16:9"

    def test_task_create_invalid_output_count(self):
        """测试 TaskCreate 验证 - 无效的 output_count"""
        from app.schemas.repair import TaskCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TaskCreate(name="测试任务", prompt="这是测试描述", output_count=3)  # 无效值

    def test_task_create_name_too_short(self):
        """测试 TaskCreate 验证 - 名称太短"""
        from app.schemas.repair import TaskCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TaskCreate(name="", prompt="这是测试描述", output_count=2)  # 空名称

    def test_task_create_name_only_defaults(self):
        """仅传 name 时可通过校验（与前端「新建任务」一致）"""
        from app.schemas.repair import TaskCreate

        task_data = TaskCreate(name="新任务 #1")
        assert task_data.prompt == ""
        assert task_data.output_count == 2
        assert task_data.aspect_ratio == "16:9"

    def test_task_update_partial(self):
        """测试 TaskUpdate - 部分更新"""
        from app.schemas.repair import TaskUpdate

        update_data = TaskUpdate(name="新名称")
        assert update_data.name == "新名称"
        assert update_data.prompt is None
        assert update_data.output_count is None
        assert update_data.aspect_ratio is None


# ==========================================
# 第二部分：RepairService 测试
# ==========================================


class TestRepairService:
    """测试 RepairService 业务逻辑层"""

    def test_create_task(self, db_session):
        """测试创建任务"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        task_data = TaskCreate(name="测试任务", prompt="这是测试描述", output_count=2)

        task = service.create_task(task_data)

        assert task.id is not None
        assert task.name == "测试任务"
        assert task.prompt == "这是测试描述"
        assert task.output_count == 2
        assert getattr(task, "aspect_ratio", None) == "16:9"
        assert task.status == "pending"
        logger.info(f"✓ 创建任务测试通过: task_id={task.id}")

    def test_get_task(self, db_session):
        """测试获取任务"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        created = service.create_task(
            TaskCreate(name="查询测试", prompt="test", output_count=1)
        )

        fetched = service.get_task(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "查询测试"
        logger.info("✓ 获取任务测试通过")

    def test_get_task_not_found(self, db_session):
        """测试获取不存在的任务"""
        from app.services.repair_service import RepairService

        service = RepairService(db_session)
        fetched = service.get_task("non_existent_id")
        assert fetched is None
        logger.info("✓ 获取不存在的任务测试通过")

    def test_list_tasks(self, db_session):
        """测试获取任务列表"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        for i in range(5):
            service.create_task(
                TaskCreate(name=f"任务{i}", prompt="test", output_count=1)
            )

        tasks, total = service.list_tasks(limit=10)
        assert len(tasks) == 5
        assert total == 5
        logger.info("✓ 获取任务列表测试通过")

    def test_list_tasks_pagination(self, db_session):
        """测试任务列表分页"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        for i in range(5):
            service.create_task(
                TaskCreate(name=f"任务{i}", prompt="test", output_count=1)
            )

        tasks_page1, total1 = service.list_tasks(skip=0, limit=2)
        tasks_page2, total2 = service.list_tasks(skip=2, limit=2)

        assert len(tasks_page1) == 2
        assert len(tasks_page2) == 2
        assert total1 == 5
        assert total2 == 5
        logger.info("✓ 任务列表分页测试通过")

    def test_update_task(self, db_session):
        """测试更新任务"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate, TaskUpdate

        service = RepairService(db_session)

        task = service.create_task(
            TaskCreate(name="旧名称", prompt="旧描述", output_count=1)
        )

        updated = service.update_task(
            task.id, TaskUpdate(name="新名称", prompt="新描述")
        )

        assert updated is not None
        assert updated.name == "新名称"
        assert updated.prompt == "新描述"
        logger.info("✓ 更新任务测试通过")

    def test_update_task_processing_blocked(self, db_session):
        """processing 状态下禁止更新任务"""
        from app.services.repair_service import RepairService
        from app.repositories.repair_repository import RepairTaskRepository
        from app.schemas.repair import TaskCreate, TaskUpdate

        service = RepairService(db_session)
        repo = RepairTaskRepository(db_session)

        task = service.create_task(
            TaskCreate(name="测试任务", prompt="test", output_count=1)
        )

        repo.update_status(task.id, "processing")

        updated = service.update_task(task.id, TaskUpdate(name="新名称"))
        assert updated is None
        logger.info("✓ processing 状态任务不可更新测试通过")

    def test_update_task_completed_allowed(self, db_session):
        """completed 状态下允许更新 prompt 等字段"""
        from app.services.repair_service import RepairService
        from app.repositories.repair_repository import RepairTaskRepository
        from app.schemas.repair import TaskCreate, TaskUpdate

        service = RepairService(db_session)
        repo = RepairTaskRepository(db_session)

        task = service.create_task(
            TaskCreate(name="已完成任务", prompt="old", output_count=1)
        )
        repo.update_status(task.id, "completed")

        updated = service.update_task(task.id, TaskUpdate(prompt="new prompt"))
        assert updated is not None
        assert updated.prompt == "new prompt"
        logger.info("✓ completed 状态任务可更新测试通过")

    def test_delete_task(self, db_session):
        """测试删除任务"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        task = service.create_task(
            TaskCreate(name="删除测试", prompt="test", output_count=1)
        )

        success = service.delete_task(task.id)
        assert success is True

        fetched = service.get_task(task.id)
        assert fetched is None
        logger.info("✓ 删除任务测试通过")

    def test_delete_task_removes_data_directory(self, db_session):
        """删除任务时一并移除 data 下任务目录"""
        from app.services.repair_service import RepairService
        from app.services.repair_service import repair_file_service
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)
        task = service.create_task(
            TaskCreate(name="目录清理测试", prompt="x", output_count=1)
        )
        repair_file_service.ensure_task_dirs(task.id)
        task_dir = repair_file_service.get_task_dir(task.id)
        assert os.path.isdir(task_dir)

        assert service.delete_task(task.id) is True
        assert service.get_task(task.id) is None
        assert not os.path.exists(task_dir)
        logger.info("✓ 删除任务同时清理目录测试通过")

    def test_delete_task_rejects_processing(self, db_session):
        """处理中任务不可删除（避免与后台任务竞态）"""
        from app.services.repair_service import RepairService
        from app.repositories.repair_repository import RepairTaskRepository
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)
        task = service.create_task(
            TaskCreate(name="处理中删除", prompt="x", output_count=1)
        )
        RepairTaskRepository(db_session).update_status(task.id, "processing")

        with pytest.raises(ValueError, match="处理中"):
            service.delete_task(task.id)

        assert service.get_task(task.id) is not None
        logger.info("✓ 处理中任务拒绝删除测试通过")

    def test_build_task_simple(self, db_session):
        """测试构建任务简要信息"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        task = service.create_task(
            TaskCreate(name="测试任务", prompt="test", output_count=2)
        )

        task_simple = service.build_task_simple_response(task)

        assert task_simple.id == task.id
        assert task_simple.name == task.name
        assert task_simple.has_main_image is False
        assert task_simple.reference_image_count == 0
        assert task_simple.result_image_count == 0
        assert task_simple.aspect_ratio == "16:9"
        logger.info("✓ 构建任务简要信息测试通过")

    def test_update_task_aspect_ratio(self, db_session):
        """更新任务长宽比"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate, TaskUpdate

        service = RepairService(db_session)
        task = service.create_task(
            TaskCreate(name="比例测试", prompt="x", output_count=1, aspect_ratio="16:9")
        )
        updated = service.update_task(task.id, TaskUpdate(aspect_ratio="9:16"))
        assert updated is not None
        assert updated.aspect_ratio == "9:16"
        simple = service.build_task_simple_response(updated)
        assert simple.aspect_ratio == "9:16"
        logger.info("✓ 更新 aspect_ratio 测试通过")

    def test_task_create_invalid_aspect_ratio(self):
        """TaskCreate 非法 aspect_ratio 应失败"""
        from app.schemas.repair import TaskCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TaskCreate(name="x", prompt="y", output_count=2, aspect_ratio="2:1")


# ==========================================
# 测试总结
# ==========================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("开始运行任务 CRUD API 测试")
    logger.info("=" * 60)
    pytest.main([__file__, "-v"])
