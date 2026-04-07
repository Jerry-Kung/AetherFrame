import logging
import os
import shutil
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.tools.llm.nano_banana_pro import generate_image_with_nano_banana_pro

logger = logging.getLogger(__name__)


def build_standard_photo_content(
    task_prompt: str,
    official_image_paths: List[str],
    fanart_image_paths: List[str],
) -> List[Dict]:
    content: List[Dict] = [{"text": task_prompt}]
    content.append({"text": "1. 角色的官方形象图片："})
    for path in official_image_paths:
        if os.path.isfile(path):
            content.append({"picture": path})
    content.append({"text": "2. 角色的2D同人立绘图片（供你参考设计细节，不要生成该风格的图片）："})
    for path in fanart_image_paths:
        if os.path.isfile(path):
            content.append({"picture": path})
    return content


def generate_standard_photo_images(
    task_id: str,
    content: List[Dict],
    output_count: int,
    aspect_ratio: str,
) -> Tuple[List[str], Optional[str], Optional[str]]:
    result_image_paths: List[str] = []
    error_message: Optional[str] = None
    temp_dir: Optional[str] = None
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"std_photo_{task_id}_")
        for i in range(output_count):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"standard_photo_{task_id}_{i}_{timestamp}.png"
            success = generate_image_with_nano_banana_pro(
                Content=content,
                output_path=temp_dir,
                file_name=file_name,
                aspect_ratio=aspect_ratio,
            )
            if not success:
                logger.error(f"标准照生成失败: task={task_id}, index={i}")
                continue
            file_path = os.path.join(temp_dir, file_name)
            if os.path.isfile(file_path):
                result_image_paths.append(file_path)
        if not result_image_paths:
            error_message = "所有标准照生成失败"
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            return [], error_message, None
        return result_image_paths, None, temp_dir
    except Exception as e:
        logger.error(f"标准照生成异常: {e}", exc_info=True)
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return [], f"生成图片时发生异常: {e}", None


def cleanup_temp_images(image_paths: List[str], temp_dir: Optional[str] = None) -> None:
    for path in image_paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass
    if temp_dir and os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
