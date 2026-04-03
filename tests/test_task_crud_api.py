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


# ==========================================
# 第一部分：Schemas 层测试
# ==========================================

class TestSchemas:
    """测试 Pydantic Schemas"""

    def test_task_create_valid(self):
        """测试 TaskCreate 验证 - 有效数据"""
        from app.schemas.repair import TaskCreate

        task_data = TaskCreate(
            name="测试任务",
            prompt="这是测试描述",
            output_count=2
        )

        assert task_data.name == "测试任务"
        assert task_data.prompt == "这是测试描述"
        assert task_data.output_count == 2

    def test_task_create_invalid_output_count(self):
        """测试 TaskCreate 验证 - 无效的 output_count"""
        from app.schemas.repair import TaskCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TaskCreate(
                name="测试任务",
                prompt="这是测试描述",
                output_count=3  # 无效值
            )

    def test_task_create_name_too_short(self):
        """测试 TaskCreate 验证 - 名称太短"""
        from app.schemas.repair import TaskCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TaskCreate(
                name="",  # 空名称
                prompt="这是测试描述",
                output_count=2
            )

    def test_task_update_partial(self):
        """测试 TaskUpdate - 部分更新"""
        from app.schemas.repair import TaskUpdate

        update_data = TaskUpdate(name="新名称")
        assert update_data.name == "新名称"
        assert update_data.prompt is None
        assert update_data.output_count is None


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

        task_data = TaskCreate(
            name="测试任务",
            prompt="这是测试描述",
            output_count=2
        )

        task = service.create_task(task_data)

        assert task.id is not None
        assert task.name == "测试任务"
        assert task.prompt == "这是测试描述"
        assert task.output_count == 2
        assert task.status == "pending"
        logger.info(f"✓ 创建任务测试通过: task_id={task.id}")

    def test_get_task(self, db_session):
        """测试获取任务"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        created = service.create_task(TaskCreate(
            name="查询测试",
            prompt="test",
            output_count=1
        ))

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
            service.create_task(TaskCreate(
                name=f"任务{i}",
                prompt="test",
                output_count=1
            ))

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
            service.create_task(TaskCreate(
                name=f"任务{i}",
                prompt="test",
                output_count=1
            ))

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

        task = service.create_task(TaskCreate(
            name="旧名称",
            prompt="旧描述",
            output_count=1
        ))

        updated = service.update_task(task.id, TaskUpdate(
            name="新名称",
            prompt="新描述"
        ))

        assert updated is not None
        assert updated.name == "新名称"
        assert updated.prompt == "新描述"
        logger.info("✓ 更新任务测试通过")

    def test_update_task_not_pending(self, db_session):
        """测试更新非 pending 状态的任务"""
        from app.services.repair_service import RepairService
        from app.repositories.repair_repository import RepairTaskRepository
        from app.schemas.repair import TaskCreate, TaskUpdate

        service = RepairService(db_session)
        repo = RepairTaskRepository(db_session)

        task = service.create_task(TaskCreate(
            name="测试任务",
            prompt="test",
            output_count=1
        ))

        # 更新状态为 processing
        repo.update_status(task.id, "processing")

        # 尝试更新应该失败
        updated = service.update_task(task.id, TaskUpdate(name="新名称"))
        assert updated is None
        logger.info("✓ 更新非 pending 状态任务测试通过")

    def test_delete_task(self, db_session):
        """测试删除任务"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        task = service.create_task(TaskCreate(
            name="删除测试",
            prompt="test",
            output_count=1
        ))

        success = service.delete_task(task.id)
        assert success is True

        fetched = service.get_task(task.id)
        assert fetched is None
        logger.info("✓ 删除任务测试通过")

    def test_build_task_simple(self, db_session):
        """测试构建任务简要信息"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import TaskCreate

        service = RepairService(db_session)

        task = service.create_task(TaskCreate(
            name="测试任务",
            prompt="test",
            output_count=2
        ))

        task_simple = service.build_task_simple_response(task)

        assert task_simple.id == task.id
        assert task_simple.name == task.name
        assert task_simple.has_main_image is False
        assert task_simple.reference_image_count == 0
        assert task_simple.result_image_count == 0
        logger.info("✓ 构建任务简要信息测试通过")


# ==========================================
# 测试总结
# ==========================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("开始运行任务 CRUD API 测试")
    logger.info("=" * 60)
    pytest.main([__file__, "-v"])
