import os
import re

from app.services.repair_service import repair_file_service


def normalize_relative_path(path: str) -> str:
    rel = (path or "").strip().replace("\\", "/")
    if not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise ValueError("source_image_path 非法")
    if ".." in rel.split("/"):
        raise ValueError("source_image_path 非法")
    return rel


def beautified_basename(source_image_path: str) -> str:
    base = os.path.basename(normalize_relative_path(source_image_path))
    stem, ext = os.path.splitext(base)
    return f"{stem}_beautified{ext}"


def beautified_relative_path(source_image_path: str) -> str:
    rel = normalize_relative_path(source_image_path)
    dirpart = os.path.dirname(rel)
    name = beautified_basename(rel)
    return f"{dirpart}/{name}" if dirpart else name


def assert_path_under_work_dir(abs_path: str, work_dir: str) -> str:
    candidate = os.path.realpath(abs_path)
    root = os.path.realpath(work_dir)
    if not candidate.startswith(root + os.sep) and candidate != root:
        raise ValueError("source_image_path 非法")
    return candidate


def resolve_quick_create_source_path(work_dir: str, source_image_path: str) -> str:
    rel = normalize_relative_path(source_image_path)
    candidate = assert_path_under_work_dir(os.path.join(work_dir, rel), work_dir)
    if not os.path.isfile(candidate):
        raise FileNotFoundError("源图片文件不存在")
    return candidate


def resolve_repair_source_path(task_id: str, source_image_path: str) -> str:
    rel = normalize_relative_path(source_image_path)
    if "/" in rel or rel != os.path.basename(rel):
        raise ValueError("source_image_path 非法")
    path = repair_file_service.get_result_image_path(task_id, rel)
    if not path or not os.path.isfile(path):
        raise FileNotFoundError("源图片文件不存在")
    return path


def resolve_beautified_absolute_path(
    *,
    source_kind: str,
    source_task_id: str,
    source_image_path: str,
    work_dir: str | None = None,
) -> str:
    if source_kind == "quick_create":
        if not work_dir:
            raise ValueError("work_dir required for quick_create")
        rel = beautified_relative_path(source_image_path)
        return assert_path_under_work_dir(os.path.join(work_dir, rel), work_dir)
    if source_kind == "repair":
        name = beautified_basename(source_image_path)
        _, _, results_dir = repair_file_service.get_task_subdirs(source_task_id)
        path = os.path.join(results_dir, name)
        return assert_path_under_work_dir(path, results_dir)
    raise ValueError("source_kind 不合法")
