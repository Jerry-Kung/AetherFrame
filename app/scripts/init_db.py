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
        "text": "修补人物皮肤上的瑕疵，保持原有的动漫风格和色调，使皮肤光滑自然，细节真实。",
        "sort_order": 1,
    },
    {
        "id": "tpl_watermark_remove",
        "label": "水印去除",
        "text": "完整去除图片中的水印、文字标记及logo，自然填充背景，不留痕迹。",
        "sort_order": 2,
    },
    {
        "id": "tpl_background_fix",
        "label": "背景噪点修复",
        "text": "修复背景区域的噪点、模糊和色差问题，使背景干净清晰，与前景融合自然。",
        "sort_order": 3,
    },
    {
        "id": "tpl_outline_complete",
        "label": "角色轮廓补全",
        "text": "补全残缺或被遮挡的动漫角色轮廓，风格保持一致，线条流畅自然。",
        "sort_order": 4,
    },
    {
        "id": "tpl_clothing_detail",
        "label": "服装细节修复",
        "text": "修复衣物皱褶、配饰残损等细节问题，保持角色整体风格统一，细节精致。",
        "sort_order": 5,
    },
    {
        "id": "tpl_eye_highlight",
        "label": "眼睛高光补绘",
        "text": "为角色眼睛添加或修复高光点，增强眼神灵动感，符合二次元美图风格。",
        "sort_order": 6,
    },
]


def init_prompt_templates():
    """初始化 Prompt 模板"""
    logger.info("========== 开始初始化 Prompt 模板 ==========")
    db = SessionLocal()
    try:
        added_count = 0
        for template_data in BUILTIN_TEMPLATES:
            # 检查是否已存在
            existing = db.query(PromptTemplate).filter(
                PromptTemplate.id == template_data["id"]
            ).first()
            
            if not existing:
                template = PromptTemplate(**template_data, is_builtin=True)
                db.add(template)
                added_count += 1
                logger.info(f"添加模板: {template_data['label']} (ID: {template_data['id']})")
            else:
                logger.debug(f"模板已存在，跳过: {template_data['label']}")
        
        db.commit()
        logger.info(f"Prompt 模板初始化完成，新增 {added_count} 个模板")
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
