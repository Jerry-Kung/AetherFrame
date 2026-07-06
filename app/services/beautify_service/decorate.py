import posixpath
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.repositories.beautify_repository import BeautifyRepository
from app.services.beautify_service.path_utils import beautified_relative_path


def decorate_quick_create_results(
    db: Session, task_id: str, results: Optional[List[Any]]
) -> Optional[List[Any]]:
    if not results:
        return results
    rows = BeautifyRepository(db).list_by_source("quick_create", task_id)
    return _apply_quick_create_rows(rows, results)


def decorate_quick_create_results_with_rows(
    rows: Optional[List[Any]], results: Optional[List[Any]]
) -> Optional[List[Any]]:
    """供批量装配使用：调用方已经一次性拉好 beautify 行，无需再 DB 查询。"""
    if not results:
        return results
    return _apply_quick_create_rows(rows or [], results)


def _apply_quick_create_rows(rows: List[Any], results: List[Any]) -> List[Any]:
    beautify_map = {row.source_image_path: row for row in rows}
    for prompt_result in results:
        if not isinstance(prompt_result, dict):
            continue
        images = prompt_result.get("generated_images") or []
        for img in images:
            if isinstance(img, str):
                path = img.strip().replace("\\", "/")
                _apply_row_to_image_dict(
                    {"path": path, "review": None}, beautify_map.get(path)
                )
            elif isinstance(img, dict):
                path = str(img.get("path") or "").strip().replace("\\", "/")
                _apply_row_to_image_dict(img, beautify_map.get(path))
    return results


def decorate_repair_result_images(
    db: Session, task_id: str, result_images: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    rows = BeautifyRepository(db).list_by_source("repair", task_id)
    beautify_map = {row.source_image_path: row for row in rows}
    for img in result_images:
        if not isinstance(img, dict):
            continue
        filename = str(img.get("filename") or "").strip()
        _apply_row_to_repair_image(img, beautify_map.get(filename))
    return result_images


def _apply_row_to_image_dict(img: Dict[str, Any], row) -> None:
    if not row:
        return
    img["beautify_task_id"] = row.id
    img["beautify_status"] = row.status
    if row.status == "completed" and row.beautified_filename:
        path = str(img.get("path") or "").replace("\\", "/")
        img["beautified_path"] = beautified_relative_path(path)


def _apply_row_to_repair_image(img: Dict[str, Any], row) -> None:
    if not row:
        return
    img["beautify_task_id"] = row.id
    img["beautify_status"] = row.status
    if row.status == "completed" and row.beautified_filename:
        img["beautified_filename"] = row.beautified_filename
