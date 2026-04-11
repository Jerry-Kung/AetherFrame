"""
数据库集成测试用例
包含：数据库连接、数据模型、Repository 层的完整测试
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

    # 清除已导入的模块，确保重新加载
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
# 第一部分：数据库连接测试
# ==========================================


class TestDatabaseConnection:
    """测试数据库连接配置"""

    def test_database_directory_created(self, temp_data_dir):
        """测试数据库目录自动创建"""
        import importlib
        import sys

        for key in list(sys.modules.keys()):
            if key.startswith("app.models"):
                del sys.modules[key]

        from app.models import database

        db_dir = os.path.join(temp_data_dir, "db")
        assert os.path.exists(db_dir)
        logger.info(f"数据库目录已创建: {db_dir}")

    def test_database_path_config(self, temp_data_dir):
        """测试数据库路径配置"""
        import importlib
        import sys

        for key in list(sys.modules.keys()):
            if key.startswith("app.models"):
                del sys.modules[key]

        from app.models import database

        assert database.DATA_DIR == temp_data_dir
        assert database.DB_DIR == os.path.join(temp_data_dir, "db")
        assert database.DB_PATH == os.path.join(temp_data_dir, "db", "aetherframe.db")
        logger.info(f"数据库路径配置正确")

    def test_engine_created(self, temp_data_dir):
        """测试数据库引擎创建"""
        import importlib
        import sys

        for key in list(sys.modules.keys()):
            if key.startswith("app.models"):
                del sys.modules[key]

        from app.models import database

        assert database.engine is not None
        logger.info("数据库引擎创建成功")

    def test_check_db_connection(self, temp_data_dir):
        """测试数据库连接检查"""
        import importlib
        import sys

        for key in list(sys.modules.keys()):
            if key.startswith("app.models"):
                del sys.modules[key]

        from app.models import database

        database.init_db()
        result = database.check_db_connection()
        assert result is True
        logger.info("数据库连接检查通过")

    def test_get_db_info(self, temp_data_dir):
        """测试获取数据库信息"""
        import importlib
        import sys

        for key in list(sys.modules.keys()):
            if key.startswith("app.models"):
                del sys.modules[key]

        from app.models import database

        database.init_db()
        info = database.get_db_info()

        assert "database_path" in info
        assert "database_dir" in info
        assert "connection_url" in info
        assert "directory_exists" in info
        assert "database_exists" in info
        assert "database_size_bytes" in info

        assert info["directory_exists"] is True
        assert info["database_exists"] is True
        assert info["database_size_bytes"] > 0

        logger.info(f"数据库信息: {info}")

    def test_get_db_yields_session(self, temp_data_dir):
        """测试 get_db 依赖注入"""
        import importlib
        import sys

        for key in list(sys.modules.keys()):
            if key.startswith("app.models"):
                del sys.modules[key]

        from app.models import database
        from app.models.repair import RepairTask

        database.init_db()

        db_gen = database.get_db()
        db = next(db_gen)

        task = RepairTask(
            id="test_conn", name="测试连接", prompt="test", output_count=1
        )
        db.add(task)
        db.commit()

        fetched = db.query(RepairTask).filter(RepairTask.id == "test_conn").first()
        assert fetched is not None
        assert fetched.name == "测试连接"

        try:
            next(db_gen)
        except StopIteration:
            pass

        logger.info("get_db 依赖注入测试通过")

    def test_init_db_creates_tables(self, temp_data_dir):
        """测试 init_db 创建表"""
        import importlib
        import sys

        for key in list(sys.modules.keys()):
            if key.startswith("app.models"):
                del sys.modules[key]

        from app.models import database
        from app.models.repair import RepairTask, PromptTemplate

        database.init_db()

        db = database.SessionLocal()
        try:
            tasks = db.query(RepairTask).all()
            templates = db.query(PromptTemplate).all()

            assert tasks == []
            assert templates == []
            logger.info("数据库表创建成功")
        finally:
            db.close()


# ==========================================
# 第二部分：RepairTaskRepository 测试
# ==========================================


class TestRepairTaskRepository:
    """测试 RepairTaskRepository"""

    def test_create_task(self, db_session):
        """测试创建任务"""
        from app.repositories.repair_repository import RepairTaskRepository

        repo = RepairTaskRepository(db_session)

        task = repo.create(
            {"name": "测试任务", "prompt": "这是测试描述", "output_count": 2}
        )

        assert task.id is not None
        assert task.name == "测试任务"
        assert task.prompt == "这是测试描述"
        assert task.output_count == 2
        assert task.status == "pending"

    def test_get_by_id(self, db_session):
        """测试根据ID获取任务"""
        from app.repositories.repair_repository import RepairTaskRepository

        repo = RepairTaskRepository(db_session)

        created = repo.create({"name": "查询测试", "prompt": "test", "output_count": 1})

        fetched = repo.get_by_id(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "查询测试"

    def test_list_tasks(self, db_session):
        """测试获取任务列表"""
        from app.repositories.repair_repository import RepairTaskRepository

        repo = RepairTaskRepository(db_session)

        for i in range(5):
            repo.create({"name": f"任务{i}", "prompt": "test", "output_count": 1})

        tasks = repo.list(limit=10)
        assert len(tasks) == 5

        tasks_page1 = repo.list(skip=0, limit=2)
        tasks_page2 = repo.list(skip=2, limit=2)
        assert len(tasks_page1) == 2
        assert len(tasks_page2) == 2

    def test_update_task(self, db_session):
        """测试更新任务"""
        from app.repositories.repair_repository import RepairTaskRepository

        repo = RepairTaskRepository(db_session)

        task = repo.create({"name": "旧名称", "prompt": "旧描述", "output_count": 1})

        updated = repo.update(task.id, {"name": "新名称", "prompt": "新描述"})

        assert updated is not None
        assert updated.name == "新名称"
        assert updated.prompt == "新描述"

    def test_update_status(self, db_session):
        """测试更新任务状态"""
        from app.repositories.repair_repository import RepairTaskRepository

        repo = RepairTaskRepository(db_session)

        task = repo.create({"name": "状态测试", "prompt": "test", "output_count": 1})

        updated = repo.update_status(task.id, "processing")
        assert updated.status == "processing"

        updated = repo.update_status(task.id, "failed", "API调用失败")
        assert updated.status == "failed"
        assert updated.error_message == "API调用失败"

    def test_delete_task(self, db_session):
        """测试删除任务"""
        from app.repositories.repair_repository import RepairTaskRepository

        repo = RepairTaskRepository(db_session)

        task = repo.create({"name": "删除测试", "prompt": "test", "output_count": 1})

        result = repo.delete(task.id)
        assert result is True

        fetched = repo.get_by_id(task.id)
        assert fetched is None

    def test_count_tasks(self, db_session):
        """测试统计任务数量"""
        from app.repositories.repair_repository import RepairTaskRepository

        repo = RepairTaskRepository(db_session)

        for i in range(3):
            repo.create({"name": f"任务{i}", "prompt": "test", "output_count": 1})

        count = repo.count()
        assert count == 3


# ==========================================
# 第三部分：PromptTemplateRepository 测试
# ==========================================


class TestPromptTemplateRepository:
    """测试 PromptTemplateRepository"""

    def test_create_template(self, db_session):
        """测试创建模板"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        template = repo.create(
            {
                "label": "测试模板",
                "text": "这是模板内容",
                "is_builtin": False,
                "sort_order": 10,
            }
        )

        assert template.id is not None
        assert template.label == "测试模板"
        assert template.text == "这是模板内容"
        assert template.is_builtin is False
        assert template.sort_order == 10
        assert getattr(template, "tags", "[]") == "[]"

    def test_get_by_id(self, db_session):
        """测试根据ID获取模板"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        created = repo.create(
            {"label": "查询测试", "text": "test", "is_builtin": False}
        )

        fetched = repo.get_by_id(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.label == "查询测试"

    def test_list_builtin(self, db_session):
        """测试获取内置模板"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        repo.create(
            {"label": "内置1", "text": "test", "is_builtin": True, "sort_order": 2}
        )
        repo.create(
            {"label": "内置2", "text": "test", "is_builtin": True, "sort_order": 1}
        )
        repo.create({"label": "自定义1", "text": "test", "is_builtin": False})

        builtin = repo.list_builtin()
        assert len(builtin) == 2
        assert builtin[0].sort_order == 1
        assert builtin[1].sort_order == 2

    def test_list_custom(self, db_session):
        """测试获取自定义模板"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        repo.create({"label": "自定义1", "text": "test", "is_builtin": False})
        repo.create({"label": "内置1", "text": "test", "is_builtin": True})

        custom = repo.list_custom()
        assert len(custom) == 1
        assert custom[0].label == "自定义1"

    def test_list_all(self, db_session):
        """测试获取所有模板"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        repo.create(
            {"label": "内置1", "text": "test", "is_builtin": True, "sort_order": 1}
        )
        repo.create({"label": "自定义1", "text": "test", "is_builtin": False})

        all_templates = repo.list_all()
        assert len(all_templates) == 2
        assert all_templates[0].is_builtin is True
        assert all_templates[1].is_builtin is False

    def test_update_template(self, db_session):
        """测试更新模板"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        template = repo.create(
            {"label": "旧标签", "text": "旧内容", "is_builtin": False}
        )

        updated = repo.update(template.id, {"label": "新标签", "text": "新内容"})

        assert updated is not None
        assert updated.label == "新标签"
        assert updated.text == "新内容"

    def test_cannot_modify_is_builtin(self, db_session):
        """测试不允许修改 is_builtin"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        template = repo.create({"label": "测试", "text": "test", "is_builtin": True})

        updated = repo.update(template.id, {"is_builtin": False})

        assert updated.is_builtin is True

    def test_delete_custom_template(self, db_session):
        """测试删除自定义模板"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        template = repo.create(
            {"label": "删除测试", "text": "test", "is_builtin": False}
        )

        result = repo.delete(template.id)
        assert result is True

        fetched = repo.get_by_id(template.id)
        assert fetched is None

    def test_cannot_delete_builtin_template(self, db_session):
        """测试不允许删除内置模板"""
        from app.repositories.repair_repository import PromptTemplateRepository

        repo = PromptTemplateRepository(db_session)

        template = repo.create(
            {"label": "内置模板", "text": "test", "is_builtin": True}
        )

        result = repo.delete(template.id)
        assert result is False

        fetched = repo.get_by_id(template.id)
        assert fetched is not None


# ==========================================
# 第四部分：BaseRepository 测试（可扩展性）
# ==========================================


class TestBaseRepository:
    """测试 BaseRepository 基类的可扩展性"""

    def test_base_repository_get_by_id(self, db_session):
        """测试 BaseRepository 的 get_by_id"""
        from app.repositories.base import BaseRepository
        from app.models.repair import RepairTask

        repo = BaseRepository(db_session, RepairTask)

        task = RepairTask(
            id="base_test", name="Base测试", prompt="test", output_count=1
        )
        db_session.add(task)
        db_session.commit()

        fetched = repo.get_by_id("base_test")
        assert fetched is not None
        assert fetched.name == "Base测试"

    def test_base_repository_count(self, db_session):
        """测试 BaseRepository 的 count"""
        from app.repositories.base import BaseRepository
        from app.models.repair import RepairTask

        repo = BaseRepository(db_session, RepairTask)

        for i in range(3):
            task = RepairTask(
                id=f"count_{i}", name=f"任务{i}", prompt="test", output_count=1
            )
            db_session.add(task)
        db_session.commit()

        count = repo.count()
        assert count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
