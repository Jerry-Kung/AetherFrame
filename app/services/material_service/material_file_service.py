import os
import logging
import uuid
from typing import Optional, Tuple

from fastapi import UploadFile

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


def get_character_dir(character_id: str) -> str:
    return os.path.join(get_material_characters_dir(), character_id)


def get_character_raw_dir(character_id: str) -> str:
    return os.path.join(get_character_dir(character_id), "raw")


def ensure_character_dirs(character_id: str) -> Tuple[str, str]:
    char_dir = get_character_dir(character_id)
    raw_dir = get_character_raw_dir(character_id)
    ensure_dir_exists(char_dir)
    ensure_dir_exists(raw_dir)
    return char_dir, raw_dir


def validate_image_file(file: UploadFile) -> Tuple[bool, str]:
    return validate_file(
        file,
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        allowed_mimetypes=ALLOWED_IMAGE_MIMETYPES,
    )


def save_raw_image(character_id: str, image_id: str, file: UploadFile) -> str:
    """
    将参考图保存为 raw/{image_id}.{ext}。

    Returns:
        stored_filename
    """
    ensure_character_dirs(character_id)
    raw_dir = get_character_raw_dir(character_id)

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


def get_raw_image_path(character_id: str, filename: str) -> Optional[str]:
    """
    解析 raw 目录下的文件路径；若文件名非法或路径越界则返回 None。
    """
    raw_dir = get_character_raw_dir(character_id)
    path = get_file_path(raw_dir, filename)
    if not path or not os.path.isfile(path):
        return None
    real_raw = os.path.realpath(raw_dir)
    real_file = os.path.realpath(path)
    if not real_file.startswith(real_raw + os.sep) and real_file != real_raw:
        logger.warning(f"路径越界拒绝: {path}")
        return None
    return path


def delete_raw_image_file(character_id: str, stored_filename: str) -> bool:
    """删除 raw 目录下单张参考图文件。"""
    raw_dir = get_character_raw_dir(character_id)
    try:
        return delete_file(raw_dir, stored_filename)
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
