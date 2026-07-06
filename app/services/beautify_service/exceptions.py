class BeautifyError(Exception):
    """美化业务错误基类。"""


class BeautifyConflictError(BeautifyError):
    """并发冲突或已有完成结果。"""


class BeautifyNotFoundError(BeautifyError):
    """美化任务或源资源不存在。"""


class BeautifyTimeoutError(BeautifyError):
    """美化轮询超时。"""
