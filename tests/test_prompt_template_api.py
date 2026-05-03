"""
Prompt 模板 API 测试用例
包含：模板的创建、读取、更新和删除的完整测试
"""

import json
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
# 第一部分：Schemas 测试
# ==========================================


class TestPromptTemplateSchemas:
    """测试 Prompt 模板相关的 Schemas"""

    def test_prompt_template_base(self):
        """测试 PromptTemplateBase"""
        from app.schemas.repair import PromptTemplateBase

        template = PromptTemplateBase(label="测试模板", text="这是模板内容")

        assert template.label == "测试模板"
        assert template.text == "这是模板内容"
        assert template.description == ""
        assert template.tags == []

        with_desc = PromptTemplateBase(
            label="测试模板",
            text="这是模板内容",
            description="简短说明",
            tags=["皮肤", " 脸部 "],
        )
        assert with_desc.description == "简短说明"
        assert with_desc.tags == ["皮肤", "脸部"]

    def test_prompt_template_create(self):
        """测试 PromptTemplateCreate"""
        from app.schemas.repair import PromptTemplateCreate

        template = PromptTemplateCreate(label="创建测试", text="创建测试内容")

        assert template.label == "创建测试"
        assert template.text == "创建测试内容"
        assert template.description == ""
        assert template.tags == []

    def test_prompt_template_update(self):
        """测试 PromptTemplateUpdate"""
        from app.schemas.repair import PromptTemplateUpdate

        update1 = PromptTemplateUpdate(label="新标签")
        assert update1.label == "新标签"
        assert update1.text is None

        update2 = PromptTemplateUpdate(text="新内容")
        assert update2.label is None
        assert update2.text == "新内容"

        update3 = PromptTemplateUpdate(description="新描述")
        assert update3.description == "新描述"

        update4 = PromptTemplateUpdate(tags=["水印", "背景"])
        assert update4.tags == ["水印", "背景"]


# ==========================================
# 第二部分：RepairService 模板操作测试
# ==========================================


class TestRepairServiceTemplateOperations:
    """测试 RepairService 的模板操作方法"""

    def test_create_template(self, db_session):
        """测试创建模板"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import PromptTemplateCreate

        service = RepairService(db_session)

        template_data = PromptTemplateCreate(
            label="测试模板",
            text="这是测试模板内容",
            description="  描述一行  ",
        )

        template = service.create_template(template_data)

        assert template.id is not None
        assert template.label == "测试模板"
        assert template.text == "这是测试模板内容"
        assert template.description == "描述一行"
        assert template.is_builtin is False
        assert json.loads(template.tags) == []
        logger.info(f"✓ 创建模板测试通过: template_id={template.id}")

    def test_create_template_with_tags(self, db_session):
        """测试创建模板时写入 tags"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import PromptTemplateCreate

        service = RepairService(db_session)
        template = service.create_template(
            PromptTemplateCreate(
                label="带标签",
                text="内容",
                tags=["皮肤", "脸部"],
            )
        )
        assert json.loads(template.tags) == ["皮肤", "脸部"]
        resp = service.build_template_response(template)
        assert resp.tags == ["皮肤", "脸部"]

    def test_get_template(self, db_session):
        """测试获取模板"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import PromptTemplateCreate

        service = RepairService(db_session)

        created = service.create_template(
            PromptTemplateCreate(label="查询测试", text="test")
        )

        fetched = service.get_template(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.label == "查询测试"
        logger.info("✓ 获取模板测试通过")

    def test_list_templates_all(self, db_session):
        """测试获取所有模板"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import PromptTemplateCreate
        from app.repositories.repair_repository import PromptTemplateRepository

        service = RepairService(db_session)
        repo = PromptTemplateRepository(db_session)

        repo.create(
            {
                "label": "内置模板",
                "text": "内置内容",
                "is_builtin": True,
                "sort_order": 1,
            }
        )

        for i in range(2):
            service.create_template(
                PromptTemplateCreate(label=f"自定义模板{i}", text=f"自定义内容{i}")
            )

        templates = service.list_templates()

        assert len(templates) == 3
        assert templates[0].is_builtin is True
        logger.info("✓ 获取所有模板测试通过")

    def test_update_template(self, db_session):
        """测试更新自定义模板"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import PromptTemplateCreate, PromptTemplateUpdate

        service = RepairService(db_session)

        template = service.create_template(
            PromptTemplateCreate(label="旧标签", text="旧内容")
        )

        updated = service.update_template(
            template.id,
            PromptTemplateUpdate(
                label="新标签",
                text="新内容",
                description="更新后的说明",
                tags=["水印"],
            ),
        )

        assert updated is not None
        assert updated.label == "新标签"
        assert updated.text == "新内容"
        assert updated.description == "更新后的说明"
        assert json.loads(updated.tags) == ["水印"]
        logger.info("✓ 更新自定义模板测试通过")

    def test_delete_template(self, db_session):
        """测试删除自定义模板"""
        from app.services.repair_service import RepairService
        from app.schemas.repair import PromptTemplateCreate

        service = RepairService(db_session)

        template = service.create_template(
            PromptTemplateCreate(label="删除测试", text="test")
        )

        success = service.delete_template(template.id)
        assert success is True

        fetched = service.get_template(template.id)
        assert fetched is None
        logger.info("✓ 删除自定义模板测试通过")


# ==========================================
# 测试总结
# ==========================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("开始运行 Prompt 模板 API 测试")
    logger.info("=" * 60)
    pytest.main([__file__, "-v"])
