import logging
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 添加上级目录到路径，确保可以导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.models.database import SessionLocal, init_db
from app.models.repair import PromptTemplate


BUILTIN_TEMPLATES = [
    {
        "id": "tpl_skin_repair",
        "label": "皮肤瑕疵修补",
        "description": "适用于修复人物皮肤痘印、划痕等瑕疵，保持动漫风格与肤色自然。",
        "text": "修补人物皮肤上的瑕疵，保持原有的动漫风格和色调，使皮肤光滑自然，细节真实。",
        "sort_order": 1,
    },
    {
        "id": "tpl_watermark_remove",
        "label": "水印去除",
        "description": "去除水印、文字标记及 logo，并对背景做自然填补。",
        "text": "完整去除图片中的水印、文字标记及logo，自然填充背景，不留痕迹。",
        "sort_order": 2,
    },
    {
        "id": "tpl_background_fix",
        "label": "背景噪点修复",
        "description": "弱化背景噪点、模糊与色差，使背景更干净并与前景融合。",
        "text": "修复背景区域的噪点、模糊和色差问题，使背景干净清晰，与前景融合自然。",
        "sort_order": 3,
    },
    {
        "id": "tpl_outline_complete",
        "label": "角色轮廓补全",
        "description": "补全残缺或被遮挡的角色轮廓，线条与风格与原图一致。",
        "text": "补全残缺或被遮挡的动漫角色轮廓，风格保持一致，线条流畅自然。",
        "sort_order": 4,
    },
    {
        "id": "tpl_clothing_detail",
        "label": "服装细节修复",
        "description": "修复衣物皱褶、配饰破损等细节，保持整体造型统一。",
        "text": "修复衣物皱褶、配饰残损等细节问题，保持角色整体风格统一，细节精致。",
        "sort_order": 5,
    },
    {
        "id": "tpl_eye_highlight",
        "label": "眼睛高光补绘",
        "description": "为眼部补充或修正高光，增强神采并符合二次元绘制习惯。",
        "text": "为角色眼睛添加或修复高光点，增强眼神灵动感，符合二次元美图风格。",
        "sort_order": 6,
    },
]


def init_prompt_templates():
    """初始化 Prompt 模板（新增内置模板；已存在则按种子幂等同步 label/text/description/sort_order）"""
    logger.info("========== 开始初始化 Prompt 模板 ==========")
    db = SessionLocal()
    try:
        added_count = 0
        synced_count = 0
        for template_data in BUILTIN_TEMPLATES:
            row = {k: v for k, v in template_data.items()}
            desc = row.get("description") or ""

            existing = db.query(PromptTemplate).filter(
                PromptTemplate.id == template_data["id"]
            ).first()

            if not existing:
                template = PromptTemplate(**row, is_builtin=True)
                db.add(template)
                added_count += 1
                logger.info(f"添加模板: {template_data['label']} (ID: {template_data['id']})")
            else:
                existing.label = template_data["label"]
                existing.text = template_data["text"]
                existing.description = desc
                existing.sort_order = template_data["sort_order"]
                existing.is_builtin = True
                synced_count += 1
                logger.debug(f"同步内置模板: {template_data['label']}")

        db.commit()
        logger.info(
            f"Prompt 模板初始化完成，新增 {added_count} 个，同步 {synced_count} 个内置模板"
        )
        logger.info("========== Prompt 模板初始化完成 ==========")
    except Exception as e:
        db.rollback()
        logger.error(f"初始化模板失败: {e}", exc_info=True)
        raise
    finally:
        db.close()


def initialize_database():
    """完整初始化数据库"""
    logger.info("========================================")
    logger.info("开始完整初始化数据库")
    logger.info("========================================")
    
    # 1. 创建表
    init_db()
    
    # 2. 初始化模板数据
    init_prompt_templates()
    
    logger.info("========================================")
    logger.info("数据库完整初始化成功！")
    logger.info("========================================")


if __name__ == "__main__":
    try:
        initialize_database()
        sys.exit(0)
    except Exception as e:
        logger.error(f"初始化过程发生错误: {e}", exc_info=True)
        sys.exit(1)
