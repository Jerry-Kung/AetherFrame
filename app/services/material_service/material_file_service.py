import os
import logging
import uuid
import shutil
from typing import Optional, Tuple, List

from fastapi import UploadFile

from app.repositories.material_repository import SHOT_TYPE_TO_INDEX
from app.services.directory_service import get_material_characters_dir, ensure_dir_exists
from app.services.file_service import (
    FileValidationError,
    FileSaveError,
    FileDeleteError,
    validate_file,
    get_file_extension,
    save_uploaded_file,
    get_file_path,
    delete_directory,
    delete_file,
)

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_IMAGE_MIMETYPES = {"image/png", "image/jpeg", "image/webp"}
RAW_IMAGE_TYPES = {"official", "fanart"}


def get_character_dir(character_id: str) -> str:
    return os.path.join(get_material_characters_dir(), character_id)


def get_character_raw_dir(character_id: str) -> str:
    return os.path.join(get_character_dir(character_id), "raw")


def get_character_raw_type_dir(character_id: str, raw_image_type: str) -> str:
    return os.path.join(get_character_raw_dir(character_id), raw_image_type)


def get_character_standard_photo_dir(character_id: str) -> str:
    return os.path.join(get_character_dir(character_id), "standard_photo")


def get_standard_photo_task_dir(character_id: str, task_id: str) -> str:
    return os.path.join(get_character_standard_photo_dir(character_id), task_id)


def get_standard_photo_task_results_dir(character_id: str, task_id: str) -> str:
    return os.path.join(get_standard_photo_task_dir(character_id, task_id), "results")


def get_standard_photo_slot_dir(character_id: str) -> str:
    """已保存到「正式标准参考图」的稳定文件目录（按 shot_type 分文件，不受新拍摄任务清空影响）。"""
    return os.path.join(get_character_dir(character_id), "standard_photo_slots")


def copy_task_result_to_official_slot(
    character_id: str, task_id: str, task_result_filename: str, shot_type: str
) -> None:
    if shot_type not in SHOT_TYPE_TO_INDEX:
        raise ValueError(f"不支持的标准照类型: {shot_type}")
    src = get_standard_photo_result_image_path(character_id, task_id, task_result_filename)
    if not src:
        raise FileNotFoundError("所选结果图文件不存在")
    slot_dir = get_standard_photo_slot_dir(character_id)
    ensure_dir_exists(slot_dir)
    dst = os.path.join(slot_dir, f"{shot_type}.png")
    shutil.copy2(src, dst)


def get_standard_slot_image_path(character_id: str, shot_type: str) -> Optional[str]:
    if shot_type not in SHOT_TYPE_TO_INDEX:
        return None
    path = os.path.join(get_standard_photo_slot_dir(character_id), f"{shot_type}.png")
    if os.path.isfile(path):
        return path
    return None


def delete_standard_slot_image_file(character_id: str, shot_type: str) -> bool:
    """删除已保存的正式标准参考图槽位文件。若文件不存在则返回 False。"""
    if shot_type not in SHOT_TYPE_TO_INDEX:
        return False
    path = os.path.join(get_standard_photo_slot_dir(character_id), f"{shot_type}.png")
    if not os.path.isfile(path):
        return False
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def ensure_character_dirs(character_id: str) -> Tuple[str, str]:
    char_dir = get_character_dir(character_id)
    raw_dir = get_character_raw_dir(character_id)
    ensure_dir_exists(char_dir)
    ensure_dir_exists(raw_dir)
    ensure_dir_exists(get_character_raw_type_dir(character_id, "official"))
    ensure_dir_exists(get_character_raw_type_dir(character_id, "fanart"))
    ensure_dir_exists(get_character_standard_photo_dir(character_id))
    return char_dir, raw_dir


def validate_image_file(file: UploadFile) -> Tuple[bool, str]:
    return validate_file(
        file,
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        allowed_mimetypes=ALLOWED_IMAGE_MIMETYPES,
    )


def save_raw_image(character_id: str, image_id: str, file: UploadFile, raw_image_type: str) -> str:
    """
    将参考图保存为 raw/{type}/{image_id}.{ext}。

    Returns:
        stored_filename
    """
    ensure_character_dirs(character_id)
    image_type = raw_image_type if raw_image_type in RAW_IMAGE_TYPES else "official"
    raw_dir = get_character_raw_type_dir(character_id, image_type)

    is_valid, err = validate_image_file(file)
    if not is_valid:
        raise FileValidationError(err)

    ext = get_file_extension(file.filename or "")
    if not ext or ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = ".png"

    stored_filename = f"{image_id}{ext}"
    return save_uploaded_file(
        file,
        save_dir=raw_dir,
        save_filename=stored_filename,
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        allowed_mimetypes=ALLOWED_IMAGE_MIMETYPES,
    )


def get_raw_image_path(character_id: str, filename: str, raw_image_type: str = "official") -> Optional[str]:
    """
    解析 raw 目录下的文件路径；若文件名非法或路径越界则返回 None。
    """
    search_dirs = []
    image_type = raw_image_type if raw_image_type in RAW_IMAGE_TYPES else "official"
    search_dirs.append(get_character_raw_type_dir(character_id, image_type))
    # 兼容旧数据：历史文件在 raw 根目录
    search_dirs.append(get_character_raw_dir(character_id))
    # 兼容类型误配
    if image_type != "official":
        search_dirs.append(get_character_raw_type_dir(character_id, "official"))
    if image_type != "fanart":
        search_dirs.append(get_character_raw_type_dir(character_id, "fanart"))

    for raw_dir in search_dirs:
        path = get_file_path(raw_dir, filename)
        if not path or not os.path.isfile(path):
            continue
        real_raw = os.path.realpath(raw_dir)
        real_file = os.path.realpath(path)
        if not real_file.startswith(real_raw + os.sep) and real_file != real_raw:
            logger.warning(f"路径越界拒绝: {path}")
            continue
        return path
    return None


def delete_raw_image_file(character_id: str, stored_filename: str, raw_image_type: str = "official") -> bool:
    """删除 raw 目录下单张参考图文件。"""
    image_type = raw_image_type if raw_image_type in RAW_IMAGE_TYPES else "official"
    typed_dir = get_character_raw_type_dir(character_id, image_type)
    try:
        if delete_file(typed_dir, stored_filename):
            return True
        # 兼容旧目录
        return delete_file(get_character_raw_dir(character_id), stored_filename)
    except FileDeleteError as e:
        logger.warning(f"删除参考图文件失败: {e}")
        return False


def delete_character_files(character_id: str) -> bool:
    """删除角色整目录。"""
    char_dir = get_character_dir(character_id)
    if not os.path.isdir(char_dir):
        return True
    try:
        delete_directory(char_dir)
        logger.info(f"已删除角色目录: {char_dir}")
        return True
    except FileDeleteError as e:
        logger.error(f"删除角色目录失败: {e}", exc_info=True)
        return False


def new_image_id() -> str:
    return str(uuid.uuid4())


def ensure_standard_photo_task_dirs(character_id: str, task_id: str) -> str:
    ensure_character_dirs(character_id)
    task_dir = get_standard_photo_task_dir(character_id, task_id)
    results_dir = get_standard_photo_task_results_dir(character_id, task_id)
    ensure_dir_exists(task_dir)
    ensure_dir_exists(results_dir)
    return results_dir


def save_standard_photo_result_bytes(
    character_id: str, task_id: str, image_data: bytes, index: int
) -> str:
    results_dir = ensure_standard_photo_task_dirs(character_id, task_id)
    filename = f"result_{index}.png"
    target_path = os.path.join(results_dir, filename)
    with open(target_path, "wb") as f:
        f.write(image_data)
    return filename


def list_standard_photo_result_images(character_id: str, task_id: str) -> List[str]:
    results_dir = get_standard_photo_task_results_dir(character_id, task_id)
    if not os.path.isdir(results_dir):
        return []
    files = []
    for name in sorted(os.listdir(results_dir)):
        ext = os.path.splitext(name)[1].lower()
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            files.append(name)
    return files


def get_standard_photo_result_image_path(
    character_id: str, task_id: str, filename: str
) -> Optional[str]:
    results_dir = get_standard_photo_task_results_dir(character_id, task_id)
    path = get_file_path(results_dir, filename)
    if path and os.path.isfile(path):
        return path
    return None


def clear_standard_photo_task_results(character_id: str, task_id: str) -> int:
    results_dir = get_standard_photo_task_results_dir(character_id, task_id)
    if not os.path.isdir(results_dir):
        ensure_standard_photo_task_dirs(character_id, task_id)
        return 0
    removed = 0
    for name in os.listdir(results_dir):
        path = os.path.join(results_dir, name)
        if os.path.isfile(path):
            os.remove(path)
            removed += 1
    return removed


def delete_standard_photo_task_dirs(character_id: str, task_id: str) -> bool:
    task_dir = get_standard_photo_task_dir(character_id, task_id)
    if not os.path.isdir(task_dir):
        return True
    try:
        shutil.rmtree(task_dir, ignore_errors=False)
        return True
    except Exception as e:
        logger.error(f"删除标准照任务目录失败: {e}", exc_info=True)
        return False
