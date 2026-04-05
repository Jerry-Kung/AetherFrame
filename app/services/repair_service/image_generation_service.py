"""
图片生成服务

负责构建修补任务的 Prompt 内容，调用 Nano Banana Pro 生成图片
"""
import os
import logging
import tempfile
import shutil
from typing import List, Dict, Tuple, Optional
from datetime import datetime

# 导入 LLM 工具
from app.tools.llm.nano_banana_pro import generate_image_with_nano_banana_pro

# 配置日志
logger = logging.getLogger(__name__)

# 修补任务默认宽高比（传给 nano_banana_pro；imageSize 等仍由该工具内建）
DEFAULT_REPAIR_ASPECT_RATIO = "16:9"


def build_repair_content(
    prompt_template: str,
    main_image_path: str,
    reference_image_paths: List[str]
) -> List[Dict]:
    """
    构建图片修补任务的 Content 列表

    格式：
    [
        {"text": "{修补prompt模版}"},
        {"picture": "待修补的图片路径"},
        {"text": "以下是角色参考图，作为你修补任务的重要参考"},
        {"picture": "角色参考图1路径"},
        {"picture": "角色参考图2路径"},
        ...
    ]

    Args:
        prompt_template: 修补 Prompt 模板
        main_image_path: 主图路径
        reference_image_paths: 参考图路径列表

    Returns:
        Content 列表，符合 Nano Banana Pro 要求的格式

    Raises:
        ValueError: 主图路径不存在
    """
    logger.info(f"构建修补任务 Content 列表")
    logger.debug(f"  Prompt 模板: {prompt_template[:100]}..." if len(prompt_template) > 100 else f"  Prompt 模板: {prompt_template}")
    logger.debug(f"  主图路径: {main_image_path}")
    logger.debug(f"  参考图数量: {len(reference_image_paths)}")

    # 验证主图存在
    if not os.path.exists(main_image_path):
        error_msg = f"主图文件不存在: {main_image_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    content = []

    # 1. 添加修补 Prompt 模板
    content.append({"text": prompt_template})
    logger.debug("  [1/4] 添加修补 Prompt 模板")

    # 2. 添加待修补的主图
    content.append({"picture": main_image_path})
    logger.debug("  [2/4] 添加主图")

    # 3. 添加引导文本
    content.append({"text": "以下是角色参考图，作为你修补任务的重要参考"})
    logger.debug("  [3/4] 添加引导文本")

    # 4. 添加参考图（如果有）
    if reference_image_paths:
        for i, ref_path in enumerate(reference_image_paths):
            if os.path.exists(ref_path):
                content.append({"picture": ref_path})
                logger.debug(f"  [4/{len(reference_image_paths)+3}] 添加参考图 {i+1}: {os.path.basename(ref_path)}")
            else:
                logger.warning(f"  参考图不存在，跳过: {ref_path}")
    else:
        logger.debug("  [4/4] 无参考图")

    logger.info(f"Content 列表构建完成，共 {len(content)} 个元素")
    return content


def generate_repair_images(
    task_id: str,
    prompt_template: str,
    main_image_path: str,
    reference_image_paths: List[str],
    output_count: int = 2,
    aspect_ratio: str = DEFAULT_REPAIR_ASPECT_RATIO
) -> Tuple[List[str], Optional[str], Optional[str]]:
    """
    生成修补图片

    Args:
        task_id: 任务 ID
        prompt_template: 修补 Prompt 模板
        main_image_path: 主图路径
        reference_image_paths: 参考图路径列表
        output_count: 输出图片数量
        aspect_ratio: 宽高比

    Returns:
        (成功生成的图片路径列表, 错误信息, 临时目录路径)
        - 成功时：错误信息为 None；临时目录须由调用方在读完文件后通过 cleanup_temp_images 删除
        - 失败时：图片路径列表为空，错误信息为失败原因；临时目录为 None 或已清理
    """
    logger.info(f"开始生成修补图片: task_id={task_id}, output_count={output_count}")

    result_image_paths: List[str] = []
    error_message: Optional[str] = None
    temp_dir: Optional[str] = None

    try:
        # 1. 构建 Content 列表
        try:
            content = build_repair_content(
                prompt_template=prompt_template,
                main_image_path=main_image_path,
                reference_image_paths=reference_image_paths
            )
        except ValueError as e:
            error_msg = f"构建 Content 失败: {str(e)}"
            logger.error(error_msg)
            return [], error_msg, None

        # 2. 临时输出目录（不可使用 TemporaryDirectory：退出 with 时会删除目录，
        #    而调用方需在返回后读取文件并拷贝到 data/repair/tasks）
        temp_dir = tempfile.mkdtemp(prefix=f"repair_{task_id}_")
        logger.debug(f"创建临时输出目录: {temp_dir}")

        try:
            # 3. 循环生成指定数量的图片
            for i in range(output_count):
                logger.info(f"生成第 {i+1}/{output_count} 张图片...")

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"repair_{task_id}_{i}_{timestamp}.png"

                success = generate_image_with_nano_banana_pro(
                    Content=content,
                    output_path=temp_dir,
                    file_name=file_name,
                    aspect_ratio=aspect_ratio
                )

                if success:
                    temp_file_path = os.path.join(temp_dir, file_name)
                    if os.path.exists(temp_file_path):
                        result_image_paths.append(temp_file_path)
                        logger.info(f"第 {i+1} 张图片生成成功: {file_name}")
                    else:
                        logger.warning(f"第 {i+1} 张图片生成返回成功，但文件不存在")
                else:
                    logger.error(f"第 {i+1} 张图片生成失败")

            # 4. 检查结果
            if len(result_image_paths) == 0:
                error_message = "所有图片生成均失败"
                logger.error(error_message)
                if temp_dir and os.path.isdir(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                return [], error_message, None

            if len(result_image_paths) < output_count:
                logger.warning(f"部分图片生成失败: 成功 {len(result_image_paths)}/{output_count}")
            else:
                logger.info(f"所有图片生成成功: {len(result_image_paths)} 张")

            return result_image_paths, error_message, temp_dir

        except Exception:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    except Exception as e:
        error_message = f"生成图片时发生异常: {str(e)}"
        logger.error(error_message, exc_info=True)
        return [], error_message, None


def cleanup_temp_images(
    image_paths: List[str],
    temp_dir: Optional[str] = None
) -> None:
    """
    清理临时图片文件及临时目录

    Args:
        image_paths: 图片路径列表
        temp_dir: generate_repair_images 返回的临时目录（若提供则整目录删除）
    """
    for path in image_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"已删除临时文件: {path}")
        except Exception as e:
            logger.warning(f"删除临时文件失败: {path}, 错误: {e}")

    if temp_dir and os.path.isdir(temp_dir):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug(f"已删除临时目录: {temp_dir}")
        except Exception as e:
            logger.warning(f"删除临时目录失败: {temp_dir}, 错误: {e}")


logger.debug("ImageGenerationService 加载完成")
