"""
素材加工模块 — 角色 API
"""
import json
import logging
import os
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.utils.cache_response import (
    build_immutable_file_response,
    build_revalidate_file_response,
    guess_media_type,
)
from fastapi.responses import FileResponse, JSONResponse
from app.schemas.material import (
    ApiResponse,
    BioPatchRequest,
    FixedSeedTemplateCreate,
    FixedSeedTemplateOut,
    FixedSeedTemplatePatch,
    CharacterCreate,
    CharacterDetail,
    CharacterListData,
    CharacterSummary,
    CharacterUpdate,
    CharaProfileStartRequest,
    CharaProfileStartResponse,
    CharaProfileStatusResponse,
    CreativeDirectionPatchRequest,
    CreativeDirectionResponse,
    CreativeDirectionStartRequest,
    CreativeDirectionTaskStatusResponse,
    CreationAdviceStartResponse,
    CreationAdviceStatusResponse,
    CreationAdviceSeedDraftData,
    Divergence,
    MaterialErrorCode,
    StandardPhotoSelectRequest,
    StandardPhotoStartRequest,
    StandardPhotoStartResponse,
    StandardPhotoStatusResponse,
    RawImageItem,
    RawImageTagsUpdate,
    RawImageUploadFail,
    RawImagesUploadData,
    SettingTextUpdate,
)
from app.repositories.material_repository import SHOT_TYPE_TO_INDEX
from app.services.material_service import MaterialService
from app.services.material_service.task_concurrency import (
    CharacterConcurrencyError,
    CreativeDirectionLimitExceededError,
)
from app.services.file_service import FileSaveError, FileValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/material", tags=["material"])


def get_material_service(db: Session = Depends(get_db)) -> MaterialService:
    return MaterialService(db)


def ensure_valid_character_id(character_id: str) -> str:
    cid = (character_id or "").strip()
    if not cid or cid in {"undefined", "null"}:
        raise HTTPException(status_code=400, detail="character_id 无效")
    return cid


def _translate_material_409(exc: Exception) -> JSONResponse:
    """把 service 层错误翻译为 409 + code 字段。"""
    if isinstance(exc, CharacterConcurrencyError):
        code = MaterialErrorCode.TASK_CONCURRENCY_EXCEEDED
        msg = "该角色已有 2 个任务在跑，请等一个完成再来"
    elif isinstance(exc, CreativeDirectionLimitExceededError):
        code = MaterialErrorCode.DIRECTION_LIMIT_EXCEEDED
        msg = "方向已达上限 20 条，请先删除部分再生成新方向"
    else:
        raise exc
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "data": None,
            "message": msg,
            "code": code.value,
        },
    )


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


@router.get("/characters/batch", response_model=ApiResponse)
async def get_characters_batch(
    ids: str = Query(..., description="逗号分隔的角色ID列表"),
    service: MaterialService = Depends(get_material_service),
):
    """批量获取角色详情，最多 20 个。"""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if not id_list:
        return ApiResponse(success=True, data=[], message="无有效ID")
    if len(id_list) > 20:
        raise HTTPException(status_code=400, detail="单次最多查询 20 个角色")
    try:
        details = service.get_characters_batch_details(id_list)
        data = [CharacterDetail(**d).model_dump(mode="json") for d in details]
        return ApiResponse(success=True, data=data, message="批量获取角色详情成功")
    except Exception as e:
        logger.error(f"API 错误 - 批量获取角色详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="批量获取角色详情失败")


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


@router.post("/characters/{character_id}/avatar", response_model=ApiResponse)
async def upload_character_avatar(
    character_id: str,
    file: UploadFile = File(...),
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    logger.info(f"API 请求 - 上传角色头像: {character_id}")
    try:
        char = service.upload_character_avatar(character_id, file)
        detail = service.character_to_detail_dict(char)
        return ApiResponse(
            success=True,
            data=CharacterDetail(**detail).model_dump(mode="json"),
            message="头像已更新",
        )
    except ValueError as e:
        if str(e) == "角色不存在":
            raise HTTPException(status_code=404, detail="角色不存在") from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileSaveError as e:
        logger.error(f"API 错误 - 保存头像文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 上传头像失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="上传头像失败")


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


@router.patch("/characters/{character_id}/bio", response_model=ApiResponse)
async def patch_character_bio(
    character_id: str,
    body: BioPatchRequest,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    logger.info(f"API 请求 - 更新角色 bio: {character_id}")
    try:
        char = service.patch_character_bio(
            character_id,
            chara_profile=body.chara_profile,
            creative_advice=body.creative_advice,
            official_seed_prompts=(
                body.official_seed_prompts.model_dump(mode="json")
                if body.official_seed_prompts is not None
                else None
            ),
        )
        detail = service.character_to_detail_dict(char)
        return ApiResponse(
            success=True,
            data=CharacterDetail(**detail).model_dump(mode="json"),
            message="角色档案已更新",
        )
    except ValueError as e:
        msg = str(e)
        if msg == "角色不存在":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error(f"API 错误 - 更新 bio 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新角色档案失败")


@router.get("/fixed-seed-templates", response_model=ApiResponse)
async def list_fixed_seed_templates(
    service: MaterialService = Depends(get_material_service),
):
    rows = service.list_fixed_seed_templates()
    data = [FixedSeedTemplateOut(**r).model_dump(mode="json") for r in rows]
    return ApiResponse(success=True, data=data, message="获取固定模板列表成功")


@router.post("/fixed-seed-templates", response_model=ApiResponse)
async def create_fixed_seed_template(
    body: FixedSeedTemplateCreate,
    service: MaterialService = Depends(get_material_service),
):
    try:
        row = service.create_fixed_seed_template(body.text)
        return ApiResponse(
            success=True,
            data=FixedSeedTemplateOut(**row).model_dump(mode="json"),
            message="已添加固定模板",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 添加固定模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="添加固定模板失败") from e


@router.patch("/fixed-seed-templates/{template_id}", response_model=ApiResponse)
async def patch_fixed_seed_template(
    template_id: str,
    body: FixedSeedTemplatePatch,
    service: MaterialService = Depends(get_material_service),
):
    tid = (template_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="template_id 无效")
    try:
        row = service.patch_fixed_seed_template(
            tid,
            text=body.text,
            used=body.used,
        )
        return ApiResponse(
            success=True,
            data=FixedSeedTemplateOut(**row).model_dump(mode="json"),
            message="已更新固定模板",
        )
    except ValueError as e:
        msg = str(e)
        if "不存在" in msg:
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error(f"API 错误 - 更新固定模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新固定模板失败") from e


@router.delete("/fixed-seed-templates/{template_id}", response_model=ApiResponse)
async def delete_fixed_seed_template(
    template_id: str,
    service: MaterialService = Depends(get_material_service),
):
    tid = (template_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="template_id 无效")
    try:
        service.delete_fixed_seed_template(tid)
        return ApiResponse(success=True, data=None, message="已删除固定模板")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 删除固定模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除固定模板失败") from e


@router.delete("/fixed-seed-templates", response_model=ApiResponse)
async def clear_fixed_seed_templates(
    service: MaterialService = Depends(get_material_service),
):
    try:
        n = service.clear_fixed_seed_templates()
        return ApiResponse(success=True, data={"deleted": n}, message="已清空全部固定模板")
    except Exception as e:
        logger.error(f"API 错误 - 清空固定模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="清空固定模板失败") from e


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
            char = service.update_setting_text(
                character_id,
                parsed.setting_text,
                clear_setting_source=parsed.clear_setting_source,
            )
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
    types: Optional[str] = Form(None),
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 上传参考图: {character_id}, count={len(files)}")
    tags_per_file: Optional[List[List[str]]] = None
    types_per_file: Optional[List[str]] = None
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

    if types:
        try:
            parsed_types = json.loads(types)
            if not isinstance(parsed_types, list):
                raise ValueError("types 须为 JSON 数组")
            if len(parsed_types) > len(files):
                raise ValueError("types 长度不能大于 files 数量")
            types_per_file = []
            for item in parsed_types:
                if not isinstance(item, str):
                    raise ValueError("types 项须为字符串")
                v = item.strip()
                if v not in ("official", "fanart"):
                    raise ValueError(f"不支持的类型: {v}")
                types_per_file.append(v)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"types 格式无效: {e}") from e

    try:
        uploaded, failed = service.upload_raw_images(character_id, files, tags_per_file, types_per_file)
    except ValueError as e:
        if str(e) == "角色不存在":
            raise HTTPException(status_code=404, detail="角色不存在") from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 上传参考图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="上传参考图失败")

    data = RawImagesUploadData(
        uploaded=[
            RawImageItem(id=x["id"], url=x["url"], type=x["type"], tags=x["tags"]) for x in uploaded
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
    return build_immutable_file_response(path=path, filename=filename)


@router.get("/characters/{character_id}/images/avatar/{filename}")
async def get_avatar_image(
    character_id: str,
    filename: str,
    request: Request,
    service: MaterialService = Depends(get_material_service),
):
    logger.debug(f"API 请求 - 读取角色头像: {character_id}/{filename}")
    path = service.get_avatar_image_path(character_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    return build_revalidate_file_response(request=request, path=path, filename=filename)


@router.post("/characters/{character_id}/standard-photo/start", response_model=ApiResponse)
async def start_standard_photo(
    character_id: str,
    body: StandardPhotoStartRequest,
    background_tasks: BackgroundTasks,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 启动标准照任务: {character_id}, shot_type={body.shot_type}")
    try:
        data = service.start_standard_photo_task(
            character_id=character_id,
            shot_type=body.shot_type,
            aspect_ratio=body.aspect_ratio,
            output_count=body.output_count,
            selected_raw_image_ids=body.selected_raw_image_ids,
            background_tasks=background_tasks,
        )
        return ApiResponse(
            success=True,
            data=StandardPhotoStartResponse(**data).model_dump(mode="json"),
            message="标准照任务已启动",
        )
    except ValueError as e:
        msg = str(e)
        if msg == "角色不存在":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error(f"API 错误 - 启动标准照任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="启动标准照任务失败")


@router.post("/characters/{character_id}/standard-photo/retry", response_model=ApiResponse)
async def retry_standard_photo(
    character_id: str,
    background_tasks: BackgroundTasks,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 重试标准照任务: {character_id}")
    task = service.get_standard_photo_task_status(character_id)
    if not task:
        raise HTTPException(status_code=404, detail="标准照任务不存在")
    try:
        data = service.start_standard_photo_task(
            character_id=character_id,
            shot_type=task["shot_type"],
            aspect_ratio=task["aspect_ratio"],
            output_count=task["output_count"],
            selected_raw_image_ids=task["selected_raw_image_ids"],
            background_tasks=background_tasks,
        )
        return ApiResponse(
            success=True,
            data=StandardPhotoStartResponse(**data).model_dump(mode="json"),
            message="标准照任务已重新提交",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"API 错误 - 重试标准照任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="重试标准照任务失败")


@router.get("/characters/{character_id}/standard-photo/status", response_model=ApiResponse)
async def get_standard_photo_status(
    character_id: str,
    service: MaterialService = Depends(get_material_service),
):
    task = service.get_standard_photo_task_status(character_id)
    if not task:
        return ApiResponse(
            success=True,
            data=None,
            message="暂无标准照任务",
        )
    return ApiResponse(
        success=True,
        data=StandardPhotoStatusResponse(**task).model_dump(mode="json"),
        message="获取标准照任务状态成功",
    )


@router.post("/characters/{character_id}/chara-profile/start", response_model=ApiResponse)
async def start_chara_profile(
    character_id: str,
    body: CharaProfileStartRequest,
    background_tasks: BackgroundTasks,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    logger.info(
        f"API 请求 - 启动角色小档案任务: {character_id}, fanart_count={len(body.selected_fanart_ids)}"
    )
    try:
        data = service.start_chara_profile_task(
            character_id=character_id,
            selected_fanart_ids=body.selected_fanart_ids,
            background_tasks=background_tasks,
        )
        return ApiResponse(
            success=True,
            data=CharaProfileStartResponse(**data).model_dump(mode="json"),
            message="角色小档案任务已启动",
        )
    except ValueError as e:
        msg = str(e)
        if msg == "角色不存在":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error(f"API 错误 - 启动角色小档案任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="启动角色小档案任务失败")


@router.get("/characters/{character_id}/chara-profile/status", response_model=ApiResponse)
async def get_chara_profile_status(
    character_id: str,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    task = service.get_chara_profile_task_status(character_id)
    if not task:
        raise HTTPException(status_code=404, detail="角色小档案任务不存在")
    return ApiResponse(
        success=True,
        data=CharaProfileStatusResponse(**task).model_dump(mode="json"),
        message="获取角色小档案任务状态成功",
    )


@router.post("/characters/{character_id}/creative-directions/start", response_model=ApiResponse)
async def start_creative_direction(
    character_id: str,
    body: CreativeDirectionStartRequest,
    background_tasks: BackgroundTasks,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    try:
        task = service.start_creative_direction_task(
            character_id=character_id,
            divergence=body.divergence.value,
            initial_input=body.initial_input,
            background_tasks=background_tasks,
        )
    except (CharacterConcurrencyError, CreativeDirectionLimitExceededError) as e:
        return _translate_material_409(e)
    except ValueError as e:
        msg = str(e)
        if msg == "character not found":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    return ApiResponse(
        success=True,
        data={"task_id": task.id, "status": task.status},
        message="任务已提交",
    )


@router.get(
    "/characters/{character_id}/creative-directions/tasks/{task_id}",
    response_model=ApiResponse,
)
async def get_creative_direction_task_status(
    character_id: str,
    task_id: str,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    try:
        task, direction = service.get_creative_direction_task_status(character_id, task_id)
    except ValueError as e:
        if str(e) == "task not found":
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    char = service.repo.get_by_id(character_id)
    if not char:
        raise HTTPException(status_code=404, detail="character not found")
    payload = CreativeDirectionTaskStatusResponse(
        task_id=task.id,
        character_id=task.character_id,
        status=task.status,
        current_step=task.current_step,
        divergence=Divergence(task.divergence),
        initial_input=task.initial_input,
        result_direction=(
            CreativeDirectionResponse.model_validate(direction) if direction else None
        ),
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
    return ApiResponse(success=True, data=payload.model_dump(mode="json"), message="ok")


@router.get("/characters/{character_id}/creative-directions", response_model=ApiResponse)
async def list_creative_directions(
    character_id: str,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    if not service.repo.get_by_id(character_id):
        raise HTTPException(status_code=404, detail="character not found")
    rows = service.list_creative_directions(character_id)
    data = [CreativeDirectionResponse.model_validate(r).model_dump(mode="json") for r in rows]
    return ApiResponse(success=True, data=data, message="ok")


@router.patch(
    "/characters/{character_id}/creative-directions/{direction_id}",
    response_model=ApiResponse,
)
async def patch_creative_direction(
    character_id: str,
    direction_id: str,
    body: CreativeDirectionPatchRequest,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    if body.title is None and body.description is None:
        raise HTTPException(status_code=400, detail="至少需要一项更新字段")
    try:
        updated = service.patch_creative_direction(
            character_id=character_id,
            direction_id=direction_id,
            title=body.title,
            description=body.description,
        )
    except ValueError as e:
        if str(e) == "direction not found":
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ApiResponse(
        success=True,
        data=CreativeDirectionResponse.model_validate(updated).model_dump(mode="json"),
        message="已保存",
    )


@router.delete(
    "/characters/{character_id}/creative-directions/{direction_id}",
    response_model=ApiResponse,
)
async def delete_creative_direction(
    character_id: str,
    direction_id: str,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    try:
        service.delete_creative_direction(character_id, direction_id)
    except ValueError as e:
        if str(e) == "direction not found":
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ApiResponse(success=True, data={"deleted": True}, message="已删除")


@router.post("/characters/{character_id}/creation-advice/start", response_model=ApiResponse)
async def start_creation_advice(
    character_id: str,
    background_tasks: BackgroundTasks,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    logger.info(f"API 请求 - 启动生成创作建议任务: {character_id}")
    try:
        data = service.start_creation_advice_task(
            character_id=character_id,
            background_tasks=background_tasks,
        )
        return ApiResponse(
            success=True,
            data=CreationAdviceStartResponse(**data).model_dump(mode="json"),
            message="生成创作建议任务已启动",
        )
    except ValueError as e:
        msg = str(e)
        if msg == "角色不存在":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error(f"API 错误 - 启动生成创作建议任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="启动生成创作建议任务失败")


@router.get("/characters/{character_id}/creation-advice/status", response_model=ApiResponse)
async def get_creation_advice_status(
    character_id: str,
    service: MaterialService = Depends(get_material_service),
):
    character_id = ensure_valid_character_id(character_id)
    task = service.get_creation_advice_task_status(character_id)
    if not task:
        raise HTTPException(status_code=404, detail="生成创作建议任务不存在")
    seed = task.get("seed_draft")
    seed_model = CreationAdviceSeedDraftData(**seed) if seed else None
    payload = {k: v for k, v in task.items() if k != "seed_draft"}
    payload["seed_draft"] = seed_model
    return ApiResponse(
        success=True,
        data=CreationAdviceStatusResponse(**payload).model_dump(mode="json"),
        message="获取生成创作建议任务状态成功",
    )


@router.get("/characters/{character_id}/standard-photo/result-images/{filename}")
async def get_standard_photo_result_image(
    character_id: str,
    filename: str,
    service: MaterialService = Depends(get_material_service),
):
    path = service.get_standard_photo_result_image_path(character_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=path,
        media_type=guess_media_type(filename),
        filename=filename,
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.get("/characters/{character_id}/standard-photo/slot-images/{shot_type}")
async def get_standard_slot_image(
    character_id: str,
    shot_type: str,
    request: Request,
    service: MaterialService = Depends(get_material_service),
):
    """已保存的正式标准参考图（按类型槽位存储，与当前生成任务目录无关）。"""
    if shot_type not in SHOT_TYPE_TO_INDEX:
        raise HTTPException(status_code=404, detail="标准照类型无效")
    path = service.get_standard_slot_image_path(character_id, shot_type)
    if not path:
        raise HTTPException(status_code=404, detail="文件不存在")
    return build_revalidate_file_response(
        request=request,
        path=path,
        filename=f"{shot_type}.png",
        media_type="image/png",
    )


@router.post("/characters/{character_id}/standard-photo/select", response_model=ApiResponse)
async def select_standard_photo_result(
    character_id: str,
    body: StandardPhotoSelectRequest,
    service: MaterialService = Depends(get_material_service),
):
    logger.info(f"API 请求 - 保存标准照结果: {character_id}")
    try:
        char = service.select_standard_photo_result(
            character_id=character_id,
            selected_result_filename=body.selected_result_filename,
            selected_result_index=body.selected_result_index,
        )
        detail = service.character_to_detail_dict(char)
        return ApiResponse(
            success=True,
            data=CharacterDetail(**detail).model_dump(mode="json"),
            message="标准照已保存",
        )
    except ValueError as e:
        msg = str(e)
        if msg == "角色不存在":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error(f"API 错误 - 保存标准照结果失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="保存标准照结果失败")


@router.delete("/characters/{character_id}/standard-photo/slot/{slot_index}", response_model=ApiResponse)
async def delete_official_photo_slot(
    character_id: str,
    slot_index: int,
    service: MaterialService = Depends(get_material_service),
):
    """清除某一槽位的正式标准参考照（数据库 URL 与槽位文件）。"""
    if slot_index < 0 or slot_index > 4:
        raise HTTPException(status_code=400, detail="标准照槽位索引无效")
    logger.info(f"API 请求 - 删除正式标准照槽位: {character_id} slot={slot_index}")
    try:
        char = service.clear_official_photo_slot(character_id, slot_index)
        detail = service.character_to_detail_dict(char)
        return ApiResponse(
            success=True,
            data=CharacterDetail(**detail).model_dump(mode="json"),
            message="标准参考照已删除",
        )
    except ValueError as e:
        msg = str(e)
        if msg == "角色不存在":
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.error(f"API 错误 - 删除正式标准照失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除正式标准照失败")
