"""
修补任务生成流水线（同步）

生成图片、写入结果目录、通过回调更新任务状态；供 RepairTaskService 在后台线程中调用。
"""
import logging
from typing import Callable, List, Optional

from . import repair_file_service
from . import image_generation_service

logger = logging.getLogger(__name__)

# (task_id, status, error_message)
UpdateTaskStatusFn = Callable[[str, str, Optional[str]], None]


def run_repair_generation_pipeline(
    task_id: str,
    prompt: str,
    main_image_path: str,
    reference_image_paths: List[str],
    output_count: int,
    update_status: UpdateTaskStatusFn,
) -> None:
    """
    同步执行修补：调用模型生成、保存结果图、更新任务状态，并清理临时文件。

    Args:
        task_id: 任务 ID
        prompt: 修补 prompt 全文
        main_image_path: 主图绝对路径
        reference_image_paths: 参考图绝对路径列表
        output_count: 生成张数
        update_status: 写入任务状态（completed / failed 及错误信息）
    """
    logger.info(f"开始执行修补流水线: task_id={task_id}, output_count={output_count}")

    temp_image_paths: List[str] = []
    temp_dir: Optional[str] = None
    try:
        result_image_paths, error_message, temp_dir = image_generation_service.generate_repair_images(
            task_id=task_id,
            prompt_template=prompt,
            main_image_path=main_image_path,
            reference_image_paths=reference_image_paths,
            output_count=output_count,
        )

        temp_image_paths = result_image_paths

        if error_message:
            logger.error(f"图片生成失败: {error_message}")
            update_status(task_id, "failed", error_message)
            return

        if not result_image_paths:
            error_msg = "没有生成任何图片"
            logger.error(error_msg)
            update_status(task_id, "failed", error_msg)
            return

        saved_count = 0
        for i, temp_path in enumerate(result_image_paths):
            try:
                with open(temp_path, "rb") as f:
                    image_data = f.read()
                repair_file_service.save_result_image(task_id, image_data, index=i)
                saved_count += 1
                logger.info(f"结果图 {i} 保存成功")
            except Exception as e:
                logger.error(f"保存结果图 {i} 失败: {e}", exc_info=True)

        if saved_count > 0:
            update_status(task_id, "completed", None)
            logger.info(f"修补任务完成: task_id={task_id}, 成功生成 {saved_count} 张图片")
        else:
            update_status(task_id, "failed", "所有结果图保存失败")
            logger.error("修补任务失败: 所有结果图保存失败")

    except Exception as e:
        error_msg = f"执行任务时发生异常: {str(e)}"
        logger.error(error_msg, exc_info=True)
        update_status(task_id, "failed", error_msg)
    finally:
        image_generation_service.cleanup_temp_images(temp_image_paths, temp_dir)
