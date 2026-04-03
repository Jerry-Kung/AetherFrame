import os
import logging
import shutil
from typing import Optional, List, Tuple, Union
from fastapi import UploadFile

# 配置日志
logger = logging.getLogger(__name__)

# 配置
DATA_DIR = os.getenv("DATA_DIR", "./data")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10MB


# ==========================================
# 自定义异常
# ==========================================

class FileServiceError(Exception):
    """文件服务基础异常"""
    pass


class FileValidationError(FileServiceError):
    """文件验证失败"""
    pass


class FileSaveError(FileServiceError):
    """文件保存失败"""
    pass


class FileDeleteError(FileServiceError):
    """文件删除失败"""
    pass


# ==========================================
# 通用文件验证
# ==========================================

def sanitize_filename(filename: str) -> str:
    """
    安全化文件名
    
    Args:
        filename: 原始文件名
        
    Returns:
        安全化后的文件名
    """
    # 将所有路径分隔符替换为下划线
    result = filename.replace('/', '_').replace('\\', '_')
    
    # 移除其他危险字符
    dangerous_chars = [':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        result = result.replace(char, '_')
    
    # 连续处理 .. 序列
    while '..' in result:
        result = result.replace('..', '_')
    
    # 取 basename 确保没有路径
    result = os.path.basename(result)
    
    # 如果结果为空，使用默认文件名
    if not result or result == '.':
        result = 'file'
    
    # 限制文件名长度
    if len(result) > 100:
        name, ext = os.path.splitext(result)
        result = name[:80] + ext
    
    logger.debug(f"文件名安全化: {filename} → {result}")
    return result


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写）"""
    return os.path.splitext(filename.lower())[1]


def validate_file(
    file: UploadFile,
    allowed_extensions: Optional[set] = None,
    allowed_mimetypes: Optional[set] = None,
    max_size: Optional[int] = None
) -> Tuple[bool, str]:
    """
    通用文件验证
    
    Args:
        file: FastAPI UploadFile 对象
        allowed_extensions: 允许的扩展名集合（如 {".png", ".jpg"}）
        allowed_mimetypes: 允许的 MIME 类型集合
        max_size: 最大文件大小（字节）
        
    Returns:
        (是否有效, 错误信息)
    """
    filename = file.filename or "unknown"
    logger.info(f"验证文件: {filename}")
    
    # 检查文件名
    if not filename or filename == "unknown":
        return False, "文件名不能为空"
    
    # 检查文件扩展名
    if allowed_extensions:
        ext = get_file_extension(filename)
        if ext not in allowed_extensions:
            return False, f"不支持的文件格式: {ext}，支持的格式: {', '.join(allowed_extensions)}"
    
    # 检查 Content-Type
    if allowed_mimetypes:
        content_type = file.content_type or ""
        if content_type and content_type not in allowed_mimetypes:
            return False, f"不支持的 MIME 类型: {content_type}"
    
    logger.info(f"文件验证通过: {filename}")
    return True, ""


# ==========================================
# 通用文件保存
# ==========================================

def save_uploaded_file(
    file: UploadFile,
    save_dir: str,
    save_filename: Optional[str] = None,
    allowed_extensions: Optional[set] = None,
    allowed_mimetypes: Optional[set] = None
) -> str:
    """
    保存上传的文件（通用函数）
    
    Args:
        file: FastAPI UploadFile 对象
        save_dir: 保存目录
        save_filename: 保存的文件名（可选，不提供则使用安全化的原始文件名）
        allowed_extensions: 允许的扩展名
        allowed_mimetypes: 允许的 MIME 类型
        
    Returns:
        保存的文件名
        
    Raises:
        FileValidationError: 文件验证失败
        FileSaveError: 文件保存失败
    """
    filename = file.filename or "unknown"
    logger.info(f"保存文件: {filename} → {save_dir}")
    
    # 验证文件
    if allowed_extensions or allowed_mimetypes:
        is_valid, error_msg = validate_file(file, allowed_extensions, allowed_mimetypes)
        if not is_valid:
            logger.error(f"文件验证失败: {error_msg}")
            raise FileValidationError(error_msg)
    
    # 确保目录存在
    os.makedirs(save_dir, mode=0o755, exist_ok=True)
    
    # 确定保存文件名
    if save_filename is None:
        save_filename = sanitize_filename(filename)
    else:
        save_filename = sanitize_filename(save_filename)
    
    save_path = os.path.join(save_dir, save_filename)
    
    # 保存文件
    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"文件保存成功: {save_path}")
        return save_filename
    except Exception as e:
        logger.error(f"文件保存失败: {e}", exc_info=True)
        raise FileSaveError(f"保存文件失败: {str(e)}")


def save_bytes_to_file(
    data: bytes,
    save_dir: str,
    save_filename: str
) -> str:
    """
    保存字节数据到文件
    
    Args:
        data: 字节数据
        save_dir: 保存目录
        save_filename: 保存的文件名
        
    Returns:
        保存的文件名
        
    Raises:
        FileSaveError: 文件保存失败
    """
    logger.info(f"保存字节数据到文件: {save_filename} → {save_dir}")
    
    # 确保目录存在
    os.makedirs(save_dir, mode=0o755, exist_ok=True)
    
    # 安全化文件名
    safe_filename = sanitize_filename(save_filename)
    save_path = os.path.join(save_dir, safe_filename)
    
    try:
        with open(save_path, "wb") as f:
            f.write(data)
        logger.info(f"字节数据保存成功: {save_path}")
        return safe_filename
    except Exception as e:
        logger.error(f"字节数据保存失败: {e}", exc_info=True)
        raise FileSaveError(f"保存字节数据失败: {str(e)}")


# ==========================================
# 通用文件读取
# ==========================================

def get_file_path(
    base_dir: str,
    filename: str,
    ensure_safe: bool = True
) -> Optional[str]:
    """
    获取文件路径（通用函数）
    
    Args:
        base_dir: 基础目录
        filename: 文件名
        ensure_safe: 是否安全化文件名
        
    Returns:
        文件绝对路径，不存在则返回 None
    """
    if ensure_safe:
        safe_filename = sanitize_filename(filename)
    else:
        safe_filename = filename
    
    filepath = os.path.join(base_dir, safe_filename)
    
    if os.path.exists(filepath) and os.path.isfile(filepath):
        logger.debug(f"找到文件: {filepath}")
        return filepath
    
    logger.debug(f"文件不存在: {safe_filename}")
    return None


def list_files_in_dir(
    dir_path: str,
    allowed_extensions: Optional[set] = None
) -> List[str]:
    """
    列出目录中的文件（通用函数）
    
    Args:
        dir_path: 目录路径
        allowed_extensions: 允许的扩展名（可选过滤）
        
    Returns:
        文件名列表
    """
    if not os.path.exists(dir_path):
        return []
    
    filenames = []
    for filename in os.listdir(dir_path):
        filepath = os.path.join(dir_path, filename)
        if os.path.isfile(filepath):
            if allowed_extensions:
                ext = get_file_extension(filename)
                if ext in allowed_extensions:
                    filenames.append(filename)
            else:
                filenames.append(filename)
    
    logger.debug(f"列出目录文件: {dir_path}, count={len(filenames)}")
    return sorted(filenames)


# ==========================================
# 通用文件删除
# ==========================================

def delete_file(
    base_dir: str,
    filename: str,
    ensure_safe: bool = True
) -> bool:
    """
    删除文件（通用函数）
    
    Args:
        base_dir: 基础目录
        filename: 文件名
        ensure_safe: 是否安全化文件名
        
    Returns:
        是否成功删除
        
    Raises:
        FileDeleteError: 文件删除失败
    """
    logger.info(f"删除文件: {filename} → {base_dir}")
    
    filepath = get_file_path(base_dir, filename, ensure_safe)
    if not filepath:
        logger.warning(f"文件不存在，无需删除: {filename}")
        return False
    
    try:
        os.remove(filepath)
        logger.info(f"文件删除成功: {filepath}")
        return True
    except Exception as e:
        logger.error(f"文件删除失败: {e}", exc_info=True)
        raise FileDeleteError(f"删除文件失败: {str(e)}")


def delete_directory(dir_path: str) -> bool:
    """
    删除整个目录及其内容
    
    Args:
        dir_path: 目录路径
        
    Returns:
        是否成功删除
        
    Raises:
        FileDeleteError: 目录删除失败
    """
    logger.info(f"删除目录: {dir_path}")
    
    if not os.path.exists(dir_path):
        logger.warning(f"目录不存在，无需删除: {dir_path}")
        return False
    
    try:
        shutil.rmtree(dir_path)
        logger.info(f"目录删除成功: {dir_path}")
        return True
    except Exception as e:
        logger.error(f"目录删除失败: {e}", exc_info=True)
        raise FileDeleteError(f"删除目录失败: {str(e)}")


# ==========================================
# 兼容旧代码
# ==========================================

def read_hello_file() -> tuple[bool, str]:
    """读取 hello.txt 文件（兼容旧代码）"""
    from app.services.directory_service import get_data_dir
    
    file_path = os.path.join(get_data_dir(), "hello.txt")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return True, content
    except Exception as e:
        return False, str(e)
