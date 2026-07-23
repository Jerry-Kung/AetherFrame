class VideoError(Exception):
    """视频创作模块通用异常"""


class VideoConflictError(VideoError):
    """存在冲突（如已有任务进行中）"""


class VideoNotFoundError(VideoError):
    """任务或资源不存在"""
