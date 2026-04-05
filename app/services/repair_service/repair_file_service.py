import os
import logging
from typing import Optional, List, Tuple
from fastapi import UploadFile

# 导入通用服务
from app.services.directory_service import (
    get_repair_tasks_dir,
    ensure_dir_exists
)
from app.services.file_service import (
    FileValidationError,
    FileSaveError,
    FileDeleteError,
    sanitize_filename,
    get_file_extension,
    validate_file,
    save_uploaded_file,
    save_bytes_to_file,
    get_file_path,
    list_files_in_dir,
    delete_file,
    delete_directory
)

# 配置日志
logger = logging.getLogger(__name__)

# 图片修补模块配置
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_IMAGE_MIMETYPES = {"image/png", "image/jpeg", "image/webp"}


# ==========================================
# 任务目录管理
# ==========================================

def get_task_dir(task_id: str) -> str:
    """获取任务目录"""
    return os.path.join(get_repair_tasks_dir(), task_id)


def get_task_subdirs(task_id: str) -> Tuple[str, str, str]:
    """
    获取任务的子目录
    
    Returns:
        (主图目录, 参考图目录, 结果图目录)
    """
    task_dir = get_task_dir(task_id)
    main_dir = task_dir
    refs_dir = os.path.join(task_dir, "references")
    results_dir = os.path.join(task_dir, "results")
    return main_dir, refs_dir, results_dir


def ensure_task_dirs(task_id: str) -> Tuple[str, str, str]:
    """
    确保任务目录存在，不存在则创建
    
    Returns:
        (主图目录, 参考图目录, 结果图目录)
    """
    logger.info(f"确保任务目录存在: task_id={task_id}")
    
    main_dir, refs_dir, results_dir = get_task_subdirs(task_id)
    
    for dir_path in [main_dir, refs_dir, results_dir]:
        ensure_dir_exists(dir_path)
    
    return main_dir, refs_dir, results_dir


# ==========================================
# 图片验证
# ==========================================

def validate_image_file(file: UploadFile) -> Tuple[bool, str]:
    """
    验证图片文件
    
    Args:
        file: FastAPI UploadFile 对象
        
    Returns:
        (是否有效, 错误信息)
    """
    return validate_file(
        file,
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        allowed_mimetypes=ALLOWED_IMAGE_MIMETYPES
    )


# ==========================================
# 主图操作
# ==========================================

def save_main_image(task_id: str, file: UploadFile) -> str:
    """
    保存主图
    
    Args:
        task_id: 任务 ID
        file: FastAPI UploadFile 对象
        
    Returns:
        保存的文件名
        
    Raises:
        FileValidationError: 文件验证失败
        FileSaveError: 文件保存失败
    """
    logger.info(f"保存主图: task_id={task_id}, filename={file.filename}")
    
    # 验证文件
    is_valid, error_msg = validate_image_file(file)
    if not is_valid:
        logger.error(f"主图验证失败: {error_msg}")
        raise FileValidationError(error_msg)
    
    # 确保目录存在
    main_dir, _, _ = ensure_task_dirs(task_id)

    # 避免 main_image.jpg 与 main_image.png 并存导致 get_main_image_path 命中旧文件
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        old_path = os.path.join(main_dir, f"main_image{ext}")
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError as e:
                logger.error(f"删除旧主图失败: {old_path}, {e}", exc_info=True)
                raise FileDeleteError(f"删除旧主图失败: {str(e)}")
    
    # 确定文件扩展名
    ext = get_file_extension(file.filename or "image.png")
    save_filename = f"main_image{ext}"
    
    return save_uploaded_file(file, main_dir, save_filename)


def get_main_image_path(task_id: str) -> Optional[str]:
    """
    获取主图文件路径
    
    Args:
        task_id: 任务 ID
        
    Returns:
        文件绝对路径，不存在则返回 None
    """
    main_dir, _, _ = get_task_subdirs(task_id)
    
    # 尝试各种可能的扩展名
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        filepath = os.path.join(main_dir, f"main_image{ext}")
        if os.path.exists(filepath) and os.path.isfile(filepath):
            logger.debug(f"找到主图: {filepath}")
            return filepath
    
    logger.debug(f"主图不存在: task_id={task_id}")
    return None


def delete_main_image(task_id: str) -> bool:
    """
    删除主图
    
    Args:
        task_id: 任务 ID
        
    Returns:
        是否成功删除
        
    Raises:
        FileDeleteError: 文件删除失败
    """
    logger.info(f"删除主图: task_id={task_id}")
    
    filepath = get_main_image_path(task_id)
    if not filepath:
        logger.warning(f"主图不存在，无需删除: task_id={task_id}")
        return False
    
    try:
        os.remove(filepath)
        logger.info(f"主图删除成功: {filepath}")
        return True
    except Exception as e:
        logger.error(f"主图删除失败: {e}", exc_info=True)
        raise FileDeleteError(f"删除主图失败: {str(e)}")


# ==========================================
# 参考图操作
# ==========================================

def save_reference_images(task_id: str, files: List[UploadFile], start_index: Optional[int] = None) -> List[str]:
    """
    批量保存参考图
    
    Args:
        task_id: 任务 ID
        files: FastAPI UploadFile 对象列表
        start_index: 起始索引（可选，None 则自动从下一个可用索引开始）
        
    Returns:
        保存的文件名列表
    """
    logger.info(f"批量保存参考图: task_id={task_id}, count={len(files)}, start_index={start_index}")
    
    _, refs_dir, _ = ensure_task_dirs(task_id)
    
    # 确定起始索引
    if start_index is None:
        existing_files = list_reference_images(task_id)
        # 找出最大的索引
        max_index = -1
        for filename in existing_files:
            if filename.startswith("ref_"):
                try:
                    idx = int(filename.split("_")[1].split(".")[0])
                    max_index = max(max_index, idx)
                except (IndexError, ValueError):
                    continue
        start_index = max_index + 1
        logger.debug(f"自动确定起始索引: {start_index}")
    
    saved_filenames = []
    for i, file in enumerate(files):
        current_index = start_index + i
        
        # 验证文件
        is_valid, error_msg = validate_image_file(file)
        if not is_valid:
            logger.warning(f"参考图 {current_index} 验证失败，跳过: {error_msg}")
            continue
        
        # 确定文件扩展名
        ext = get_file_extension(file.filename or f"ref_{current_index}.png")
        save_filename = f"ref_{current_index}{ext}"
        
        try:
            saved_name = save_uploaded_file(file, refs_dir, save_filename)
            saved_filenames.append(saved_name)
            logger.info(f"参考图保存成功: {saved_name}")
        except Exception as e:
            logger.error(f"参考图 {current_index} 保存失败: {e}", exc_info=True)
    
    logger.info(f"批量保存参考图完成: 成功 {len(saved_filenames)}/{len(files)}")
    return saved_filenames


def get_reference_image_path(task_id: str, filename: str) -> Optional[str]:
    """
    获取参考图文件路径
    
    Args:
        task_id: 任务 ID
        filename: 文件名
        
    Returns:
        文件绝对路径，不存在则返回 None
    """
    _, refs_dir, _ = get_task_subdirs(task_id)
    return get_file_path(refs_dir, filename)


def list_reference_images(task_id: str) -> List[str]:
    """
    列出任务的所有参考图
    
    Args:
        task_id: 任务 ID
        
    Returns:
        文件名列表
    """
    _, refs_dir, _ = get_task_subdirs(task_id)
    return list_files_in_dir(refs_dir, ALLOWED_IMAGE_EXTENSIONS)


def delete_reference_image(task_id: str, filename: str) -> bool:
    """
    删除参考图
    
    Args:
        task_id: 任务 ID
        filename: 文件名
        
    Returns:
        是否成功删除
        
    Raises:
        FileDeleteError: 文件删除失败
    """
    logger.info(f"删除参考图: task_id={task_id}, filename={filename}")
    
    _, refs_dir, _ = get_task_subdirs(task_id)
    return delete_file(refs_dir, filename)


# ==========================================
# 结果图操作
# ==========================================

def save_result_image(task_id: str, image_data: bytes, index: int = 0) -> str:
    """
    保存结果图（从字节数据）
    
    Args:
        task_id: 任务 ID
        image_data: 图片字节数据
        index: 结果图索引
        
    Returns:
        保存的文件名
        
    Raises:
        FileSaveError: 文件保存失败
    """
    logger.info(f"保存结果图: task_id={task_id}, index={index}")
    
    _, _, results_dir = ensure_task_dirs(task_id)
    
    # 默认保存为 PNG
    save_filename = f"result_{index}.png"
    
    return save_bytes_to_file(image_data, results_dir, save_filename)


def get_result_image_path(task_id: str, filename: str) -> Optional[str]:
    """
    获取结果图文件路径
    
    Args:
        task_id: 任务 ID
        filename: 文件名
        
    Returns:
        文件绝对路径，不存在则返回 None
    """
    _, _, results_dir = get_task_subdirs(task_id)
    return get_file_path(results_dir, filename)


def list_result_images(task_id: str) -> List[str]:
    """
    列出任务的所有结果图
    
    Args:
        task_id: 任务 ID
        
    Returns:
        文件名列表
    """
    _, _, results_dir = get_task_subdirs(task_id)
    return list_files_in_dir(results_dir, ALLOWED_IMAGE_EXTENSIONS)


def clear_result_images(task_id: str) -> int:
    """
    删除任务 results 目录下的全部结果图文件，并确保目录存在。

    Returns:
        成功删除的文件数量
    """
    logger.info(f"清空结果图目录: task_id={task_id}")
    _, _, results_dir = get_task_subdirs(task_id)
    if not os.path.isdir(results_dir):
        ensure_task_dirs(task_id)
        return 0

    removed = 0
    for name in list_result_images(task_id):
        path = os.path.join(results_dir, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                removed += 1
            except OSError as e:
                logger.error(f"删除结果图失败: {path}, {e}", exc_info=True)
                raise FileDeleteError(f"删除结果图失败: {str(e)}")

    ensure_dir_exists(results_dir)
    logger.info(f"清空结果图完成: task_id={task_id}, removed={removed}")
    return removed


# ==========================================
# 任务文件整体操作
# ==========================================

def delete_task_files(task_id: str) -> bool:
    """
    删除任务的所有文件
    
    Args:
        task_id: 任务 ID
        
    Returns:
        是否成功删除
        
    Raises:
        FileDeleteError: 目录删除失败
    """
    logger.info(f"删除任务所有文件: task_id={task_id}")
    
    task_dir = get_task_dir(task_id)
    return delete_directory(task_dir)
