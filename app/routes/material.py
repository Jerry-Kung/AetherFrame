"""
素材加工模块 — 角色 API
"""
import json
import logging
import os
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.material import (
    ApiResponse,
    CharacterCreate,
    CharacterDetail,
    CharacterListData,
    CharacterSummary,
    CharacterUpdate,
    RawImageItem,
    RawImageTagsUpdate,
    RawImageUploadFail,
    RawImagesUploadData,
    SettingTextUpdate,
)
from app.services.material_service import MaterialService
from app.services.file_service import FileValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/material", tags=["material"])


def get_material_service(db: Session = Depends(get_db)) -> MaterialService:
    return MaterialService(db)


@router.get("/characters", response_model=ApiResponse)
@router.get("/characters/", response_model=ApiResponse)
async def list_characters(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 角色列表: skip={skip}, limit={limit}")
    try:
        summaries, total = service.list_character_summaries(skip=skip, limit=limit)
        data = CharacterListData(
            characters=[CharacterSummary(**s) for s in summaries],
            total=total,
            skip=skip,
            limit=limit,
        )
        return ApiResponse(success=True, data=data.model_dump(), message="获取角色列表成功")
    except Exception as e:
        logger.error(f"API 错误 - 角色列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取角色列表失败")


@router.post("/characters", response_model=ApiResponse)
@router.post("/characters/", response_model=ApiResponse)
async def create_character(
    body: CharacterCreate,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 新建角色: name={body.name}")
    try:
        char = service.create_character(name=body.name, display_name=body.display_name)
        detail = service.character_to_detail_dict(char)
        return ApiResponse(
            success=True,
            data=CharacterDetail(**detail).model_dump(mode="json"),
            message="创建角色成功",
        )
    except Exception as e:
        logger.error(f"API 错误 - 创建角色失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建角色失败")


@router.patch("/characters/{character_id}", response_model=ApiResponse)
async def patch_character(
    character_id: str,
    body: CharacterUpdate,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 更新角色: {character_id}")
    try:
        char = service.patch_character(
            character_id,
            name=body.name,
            display_name=body.display_name,
        )
        detail = service.character_to_detail_dict(char)
        return ApiResponse(
            success=True,
            data=CharacterDetail(**detail).model_dump(mode="json"),
            message="角色信息已更新",
        )
    except ValueError as e:
        if str(e) == "角色不存在":
            raise HTTPException(status_code=404, detail="角色不存在") from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 更新角色失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新角色失败")


@router.get("/characters/{character_id}", response_model=ApiResponse)
async def get_character(
    character_id: str,
    service: MaterialService = Depends(get_material_service),
):
    logger.debug(f"API 请求 - 角色详情: {character_id}")
    char = service.get_character(character_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    detail = service.character_to_detail_dict(char)
    return ApiResponse(
        success=True,
        data=CharacterDetail(**detail).model_dump(mode="json"),
        message="获取角色成功",
    )


@router.delete("/characters/{character_id}", response_model=ApiResponse)
async def delete_character(
    character_id: str,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 删除角色: {character_id}")
    ok = service.delete_character(character_id)
    if not ok:
        raise HTTPException(status_code=404, detail="角色不存在")
    return ApiResponse(success=True, data=None, message="删除角色成功")


@router.put("/characters/{character_id}/setting", response_model=ApiResponse)
async def update_setting(
    character_id: str,
    request: Request,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 更新角色设定: {character_id}")
    ct = (request.headers.get("content-type") or "").lower()

    try:
        if "application/json" in ct:
            body = await request.json()
            parsed = SettingTextUpdate.model_validate(body)
            char = service.update_setting_text(character_id, parsed.setting_text)
        elif "multipart/form-data" in ct:
            form = await request.form()
            file = form.get("file")
            if file is None or not hasattr(file, "read"):
                raise HTTPException(status_code=400, detail="multipart 请求需提供 file 字段")
            upload = file  # Starlette UploadFile
            char = service.update_setting_from_upload(character_id, upload)
        else:
            raise HTTPException(
                status_code=415,
                detail="请使用 application/json 或 multipart/form-data",
            )
    except HTTPException:
        raise
    except ValueError as e:
        if str(e) == "角色不存在":
            raise HTTPException(status_code=404, detail="角色不存在") from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 更新设定失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新设定失败")

    detail = service.character_to_detail_dict(char)
    return ApiResponse(
        success=True,
        data=CharacterDetail(**detail).model_dump(mode="json"),
        message="设定已更新",
    )


@router.post("/characters/{character_id}/raw-images", response_model=ApiResponse)
async def upload_raw_images(
    character_id: str,
    files: List[UploadFile] = File(...),
    tags: Optional[str] = Form(None),
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 上传参考图: {character_id}, count={len(files)}")
    tags_per_file: Optional[List[List[str]]] = None
    if tags:
        try:
            parsed = json.loads(tags)
            if not isinstance(parsed, list):
                raise ValueError("tags 须为 JSON 数组")
            tags_per_file = []
            for item in parsed:
                if isinstance(item, list):
                    tags_per_file.append([str(x) for x in item])
                elif isinstance(item, str):
                    tags_per_file.append([item])
                else:
                    tags_per_file.append(["其他"])
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"tags 格式无效: {e}") from e

    try:
        uploaded, failed = service.upload_raw_images(character_id, files, tags_per_file)
    except ValueError as e:
        if str(e) == "角色不存在":
            raise HTTPException(status_code=404, detail="角色不存在") from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 上传参考图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="上传参考图失败")

    data = RawImagesUploadData(
        uploaded=[
            RawImageItem(id=x["id"], url=x["url"], tags=x["tags"]) for x in uploaded
        ],
        failed=[
            RawImageUploadFail(original_filename=x["original_filename"], error=x["error"])
            for x in failed
        ],
        total=len(files),
        character_id=character_id,
    )
    msg = f"成功上传 {len(uploaded)} 张"
    if failed:
        msg += f"，{len(failed)} 张失败"
    return ApiResponse(success=True, data=data.model_dump(), message=msg)


@router.delete(
    "/characters/{character_id}/raw-images/{image_id}", response_model=ApiResponse
)
async def delete_raw_image(
    character_id: str,
    image_id: str,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 删除参考图: {character_id}/{image_id}")
    try:
        ok = service.delete_raw_image(character_id, image_id)
    except ValueError as e:
        if str(e) == "角色不存在":
            raise HTTPException(status_code=404, detail="角色不存在") from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 删除参考图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除参考图失败")
    if not ok:
        raise HTTPException(status_code=404, detail="参考图不存在")
    return ApiResponse(success=True, data=None, message="参考图已删除")


@router.patch(
    "/characters/{character_id}/raw-images/{image_id}", response_model=ApiResponse
)
async def patch_raw_image_tags(
    character_id: str,
    image_id: str,
    body: RawImageTagsUpdate,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 更新参考图标签: {character_id}/{image_id}")
    try:
        ok = service.update_raw_image_tags(character_id, image_id, body.tags)
    except ValueError as e:
        if str(e) == "角色不存在":
            raise HTTPException(status_code=404, detail="角色不存在") from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 更新参考图标签失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新参考图标签失败")
    if not ok:
        raise HTTPException(status_code=404, detail="参考图不存在")
    char = service.get_character(character_id)
    detail = service.character_to_detail_dict(char)
    return ApiResponse(
        success=True,
        data=CharacterDetail(**detail).model_dump(mode="json"),
        message="标签已更新",
    )


@router.get("/characters/{character_id}/images/raw/{filename}")
async def get_raw_image(
    character_id: str,
    filename: str,
    service: MaterialService = Depends(get_material_service),
):
    logger.debug(f"API 请求 - 读取参考图: {character_id}/{filename}")
    path = service.get_raw_image_path(character_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(filename)[1].lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(ext, "application/octet-stream")
    return FileResponse(path=path, media_type=media_type, filename=filename)
