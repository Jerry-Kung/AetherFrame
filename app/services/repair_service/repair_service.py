"""
修补任务业务逻辑层
"""
import logging
import os
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from fastapi import UploadFile

from app.models.repair import RepairTask, PromptTemplate
from app.repositories.repair_repository import RepairTaskRepository, PromptTemplateRepository
from app.schemas.repair import (
    TaskCreate,
    TaskUpdate,
    TaskSimple,
    TaskDetail,
    ImageInfo,
    TaskListResponse,
    UploadedImageInfo,
    FailedUploadInfo,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplateListResponse
)
from . import repair_file_service
from app.services.file_service import FileValidationError, FileSaveError, FileDeleteError

logger = logging.getLogger(__name__)


class RepairService:
    """修补任务业务逻辑服务"""

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = RepairTaskRepository(db)
        self.template_repo = PromptTemplateRepository(db)

    # ==========================================
    # 任务 CRUD 操作
    # ==========================================

    def create_task(self, task_data: TaskCreate) -> RepairTask:
        """
        创建新任务

        Args:
            task_data: 任务创建数据

        Returns:
            创建的 RepairTask 对象
        """
        logger.info(f"创建任务: name={task_data.name}, output_count={task_data.output_count}")

        # 转换为字典
        task_dict = {
            "name": task_data.name,
            "prompt": task_data.prompt,
            "output_count": task_data.output_count
        }

        # 创建任务
        task = self.task_repo.create(task_dict)
        logger.info(f"任务创建成功: {task.id}")

        # 确保任务目录存在
        repair_file_service.ensure_task_dirs(task.id)

        return task

    def get_task(self, task_id: str) -> Optional[RepairTask]:
        """
        根据 ID 获取任务

        Args:
            task_id: 任务 ID

        Returns:
            RepairTask 对象，不存在则返回 None
        """
        logger.debug(f"获取任务: task_id={task_id}")
        return self.task_repo.get_by_id(task_id)

    def list_tasks(
        self,
        skip: int = 0,
        limit: int = 50,
        order_by: str = "created_at",
        order_dir: str = "desc",
        status: Optional[str] = None
    ) -> Tuple[List[RepairTask], int]:
        """
        获取任务列表

        Args:
            skip: 跳过数量
            limit: 返回数量
            order_by: 排序字段
            order_dir: 排序方向 (asc/desc)
            status: 按状态过滤

        Returns:
            (任务列表, 总数)
        """
        logger.debug(
            f"查询任务列表: skip={skip}, limit={limit}, "
            f"order_by={order_by}, order_dir={order_dir}, status={status}"
        )

        # 限制 limit 最大值
        limit = min(limit, 100)

        # 构建查询
        query = self.db.query(RepairTask)

        # 状态过滤
        if status:
            query = query.filter(RepairTask.status == status)

        # 获取总数
        total = query.count()

        # 排序
        order_column = getattr(RepairTask, order_by, RepairTask.created_at)
        if order_dir == "asc":
            query = query.order_by(asc(order_column))
        else:
            query = query.order_by(desc(order_column))

        # 分页
        tasks = query.offset(skip).limit(limit).all()

        logger.debug(f"查询到 {len(tasks)} 个任务，总计 {total} 个")
        return tasks, total

    def update_task(self, task_id: str, task_data: TaskUpdate) -> Optional[RepairTask]:
        """
        更新任务信息

        Args:
            task_id: 任务 ID
            task_data: 更新数据

        Returns:
            更新后的 RepairTask 对象，不存在或不能更新则返回 None
        """
        logger.info(f"更新任务: task_id={task_id}")

        # 获取任务
        task = self.task_repo.get_by_id(task_id)
        if not task:
            logger.warning(f"更新失败，任务不存在: {task_id}")
            return None

        # 检查是否可以更新
        if not self._can_update_task(task):
            logger.warning(f"更新失败，任务状态不允许: {task_id}, status={task.status}")
            return None

        # 构建更新数据
        updates = {}
        if task_data.name is not None:
            updates["name"] = task_data.name
        if task_data.prompt is not None:
            updates["prompt"] = task_data.prompt
        if task_data.output_count is not None:
            updates["output_count"] = task_data.output_count

        if not updates:
            logger.warning(f"更新失败，没有提供更新字段: {task_id}")
            return task

        # 更新任务
        updated_task = self.task_repo.update(task_id, updates)
        logger.info(f"任务更新成功: {task_id}")

        return updated_task

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务及其所有文件

        Args:
            task_id: 任务 ID

        Returns:
            是否删除成功

        Raises:
            ValueError: 任务处于 processing 状态（后台仍在执行，禁止删除以免残留目录）
        """
        logger.info(f"删除任务: task_id={task_id}")

        # 获取任务
        task = self.task_repo.get_by_id(task_id)
        if not task:
            logger.warning(f"删除失败，任务不存在: {task_id}")
            return False

        if task.status == "processing":
            logger.warning(f"删除失败，任务处理中: {task_id}")
            raise ValueError("任务处理中，无法删除。请等待完成或失败后再试。")

        # 先删本地 data 目录，失败则不删数据库，避免「库无记录但磁盘仍有文件」
        try:
            repair_file_service.delete_task_files(task_id)
            logger.info(f"任务目录已清理: {task_id}")
        except FileDeleteError as e:
            logger.error(f"任务文件删除失败: {task_id}, error={e}", exc_info=True)
            return False

        # 删除数据库记录
        success = self.task_repo.delete(task_id)
        if success:
            logger.info(f"任务删除成功: {task_id}")
        else:
            logger.error(f"任务删除失败: {task_id}")

        return success

    # ==========================================
    # 辅助方法
    # ==========================================

    def _can_update_task(self, task: RepairTask) -> bool:
        """
        检查任务是否可以更新

        Args:
            task: 任务对象

        Returns:
            是否可以更新
        """
        # 只有 pending 状态的任务可以更新
        return task.status == "pending"

    def _build_task_simple(self, task: RepairTask) -> TaskSimple:
        """
        构建任务简要信息

        Args:
            task: 任务对象

        Returns:
            TaskSimple 对象
        """
        # 检查主图是否存在
        has_main_image = repair_file_service.get_main_image_path(task.id) is not None

        # 统计参考图和结果图数量
        reference_image_count = len(repair_file_service.list_reference_images(task.id))
        result_image_count = len(repair_file_service.list_result_images(task.id))

        return TaskSimple(
            id=task.id,
            name=task.name,
            status=task.status,
            prompt=task.prompt,
            output_count=task.output_count,
            created_at=task.created_at,
            updated_at=task.updated_at,
            has_main_image=has_main_image,
            reference_image_count=reference_image_count,
            result_image_count=result_image_count
        )

    def _build_task_detail(self, task: RepairTask) -> TaskDetail:
        """
        构建任务详细信息

        Args:
            task: 任务对象

        Returns:
            TaskDetail 对象
        """
        # 获取简要信息
        simple = self._build_task_simple(task)

        # 构建主图信息
        main_image = None
        main_image_path = repair_file_service.get_main_image_path(task.id)
        if main_image_path:
            import os
            filename = os.path.basename(main_image_path)
            main_image = ImageInfo(
                filename=filename,
                url=f"/api/repair/tasks/{task.id}/images/main/{filename}"
            )

        # 构建参考图信息
        reference_images = []
        ref_filenames = repair_file_service.list_reference_images(task.id)
        for filename in ref_filenames:
            reference_images.append(ImageInfo(
                filename=filename,
                url=f"/api/repair/tasks/{task.id}/images/reference/{filename}"
            ))

        # 构建结果图信息
        result_images = []
        res_filenames = repair_file_service.list_result_images(task.id)
        for filename in res_filenames:
            result_images.append(ImageInfo(
                filename=filename,
                url=f"/api/repair/tasks/{task.id}/images/result/{filename}"
            ))

        return TaskDetail(
            **simple.model_dump(),
            error_message=task.error_message,
            main_image=main_image,
            reference_images=reference_images,
            result_images=result_images
        )

    def build_task_simple_response(self, task: RepairTask) -> TaskSimple:
        """构建任务简要响应"""
        return self._build_task_simple(task)

    def build_task_detail_response(self, task: RepairTask) -> TaskDetail:
        """构建任务详细响应"""
        return self._build_task_detail(task)

    def build_task_list_response(
        self,
        tasks: List[RepairTask],
        total: int,
        skip: int,
        limit: int
    ) -> TaskListResponse:
        """构建任务列表响应"""
        task_simple_list = [self._build_task_simple(task) for task in tasks]
        return TaskListResponse(
            tasks=task_simple_list,
            total=total,
            skip=skip,
            limit=limit
        )


    # ==========================================
    # 文件操作方法
    # ==========================================

    def upload_main_image(
        self, 
        task_id: str, 
        file: UploadFile
    ) -> Tuple[str, str]:
        """
        上传主图
        
        Args:
            task_id: 任务 ID
            file: FastAPI UploadFile 对象
            
        Returns:
            (文件名, 文件URL)
            
        Raises:
            HTTPException: 任务不存在或文件验证失败
        """
        logger.info(f"上传主图: task_id={task_id}, filename={file.filename}")

        # 检查任务是否存在
        task = self.task_repo.get_by_id(task_id)
        if not task:
            logger.warning(f"上传主图失败，任务不存在: {task_id}")
            raise ValueError("任务不存在")

        try:
            # 保存主图
            filename = repair_file_service.save_main_image(task_id, file)
            url = f"/api/repair/tasks/{task_id}/images/main/{filename}"
            
            logger.info(f"主图上传成功: task_id={task_id}, filename={filename}")
            return filename, url

        except FileValidationError as e:
            logger.error(f"主图验证失败: task_id={task_id}, error={e}")
            raise
        except FileSaveError as e:
            logger.error(f"主图保存失败: task_id={task_id}, error={e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"主图上传失败: task_id={task_id}, error={e}", exc_info=True)
            raise

    def upload_reference_images(
        self, 
        task_id: str, 
        files: List[UploadFile]
    ) -> Tuple[List[UploadedImageInfo], List[FailedUploadInfo]]:
        """
        批量上传参考图
        
        Args:
            task_id: 任务 ID
            files: FastAPI UploadFile 对象列表
            
        Returns:
            (成功列表, 失败列表)
        """
        logger.info(f"批量上传参考图: task_id={task_id}, count={len(files)}")

        # 检查任务是否存在
        task = self.task_repo.get_by_id(task_id)
        if not task:
            logger.warning(f"上传参考图失败，任务不存在: {task_id}")
            raise ValueError("任务不存在")

        uploaded = []
        failed = []

        # 逐个处理文件，这样可以准确追踪每个文件的状态
        for file in files:
            try:
                # 单个文件保存
                saved_filenames = repair_file_service.save_reference_images(task_id, [file])
                
                if saved_filenames:
                    filename = saved_filenames[0]
                    url = f"/api/repair/tasks/{task_id}/images/reference/{filename}"
                    uploaded.append(UploadedImageInfo(filename=filename, url=url))
                    logger.info(f"参考图上传成功: task_id={task_id}, filename={filename}")
                else:
                    failed.append(FailedUploadInfo(
                        original_filename=file.filename or "unknown",
                        error="文件保存失败"
                    ))
                    logger.warning(f"参考图上传失败: task_id={task_id}, filename={file.filename}")

            except FileValidationError as e:
                failed.append(FailedUploadInfo(
                    original_filename=file.filename or "unknown",
                    error=str(e)
                ))
                logger.warning(f"参考图验证失败: task_id={task_id}, filename={file.filename}, error={e}")
            except Exception as e:
                failed.append(FailedUploadInfo(
                    original_filename=file.filename or "unknown",
                    error="上传失败"
                ))
                logger.error(f"参考图上传异常: task_id={task_id}, filename={file.filename}, error={e}", exc_info=True)

        logger.info(f"批量上传参考图完成: task_id={task_id}, 成功={len(uploaded)}, 失败={len(failed)}")
        return uploaded, failed

    def delete_main_image(self, task_id: str) -> bool:
        """
        删除主图
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功删除
        """
        logger.info(f"删除主图: task_id={task_id}")

        # 检查任务是否存在
        task = self.task_repo.get_by_id(task_id)
        if not task:
            logger.warning(f"删除主图失败，任务不存在: {task_id}")
            return False

        try:
            success = repair_file_service.delete_main_image(task_id)
            if success:
                logger.info(f"主图删除成功: task_id={task_id}")
            else:
                logger.warning(f"主图不存在，无需删除: task_id={task_id}")
            return success
        except FileDeleteError as e:
            logger.error(f"主图删除失败: task_id={task_id}, error={e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"主图删除异常: task_id={task_id}, error={e}", exc_info=True)
            raise

    def delete_reference_image(self, task_id: str, filename: str) -> bool:
        """
        删除参考图
        
        Args:
            task_id: 任务 ID
            filename: 文件名
            
        Returns:
            是否成功删除
        """
        logger.info(f"删除参考图: task_id={task_id}, filename={filename}")

        # 检查任务是否存在
        task = self.task_repo.get_by_id(task_id)
        if not task:
            logger.warning(f"删除参考图失败，任务不存在: {task_id}")
            return False

        try:
            success = repair_file_service.delete_reference_image(task_id, filename)
            if success:
                logger.info(f"参考图删除成功: task_id={task_id}, filename={filename}")
            else:
                logger.warning(f"参考图不存在，无需删除: task_id={task_id}, filename={filename}")
            return success
        except FileDeleteError as e:
            logger.error(f"参考图删除失败: task_id={task_id}, filename={filename}, error={e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"参考图删除异常: task_id={task_id}, filename={filename}, error={e}", exc_info=True)
            raise

    def get_image_path(
        self, 
        task_id: str, 
        image_type: str, 
        filename: str
    ) -> Optional[str]:
        """
        获取图片文件路径
        
        Args:
            task_id: 任务 ID
            image_type: 图片类型 (main/reference/result)
            filename: 文件名
            
        Returns:
            文件绝对路径，不存在则返回 None
        """
        logger.debug(f"获取图片路径: task_id={task_id}, image_type={image_type}, filename={filename}")

        # 检查任务是否存在
        task = self.task_repo.get_by_id(task_id)
        if not task:
            logger.warning(f"获取图片路径失败，任务不存在: {task_id}")
            return None

        # 验证 image_type
        valid_image_types = {"main", "reference", "result"}
        if image_type not in valid_image_types:
            logger.warning(f"获取图片路径失败，无效的 image_type: {image_type}")
            return None

        # 安全化文件名
        from app.services.file_service import sanitize_filename
        safe_filename = sanitize_filename(filename)
        if safe_filename != filename:
            logger.warning(f"文件名被安全化: {filename} -> {safe_filename}")

        # 获取文件路径
        if image_type == "main":
            # 主图需要检查扩展名
            path = repair_file_service.get_main_image_path(task_id)
            if path and os.path.basename(path) == safe_filename:
                return path
            return None
        elif image_type == "reference":
            path = repair_file_service.get_reference_image_path(task_id, safe_filename)
        else:  # result
            path = repair_file_service.get_result_image_path(task_id, safe_filename)

        if path and os.path.exists(path) and os.path.isfile(path):
            logger.debug(f"找到图片: {path}")
            return path
        
        logger.debug(f"图片不存在: task_id={task_id}, image_type={image_type}, filename={safe_filename}")
        return None

    # ==========================================
    # Prompt 模板操作方法
    # ==========================================

    def list_templates(self, template_type: Optional[str] = None) -> List[PromptTemplate]:
        """
        获取模板列表
        
        Args:
            template_type: 模板类型过滤 (builtin/custom/None)
            
        Returns:
            模板列表
        """
        logger.debug(f"获取模板列表: template_type={template_type}")

        if template_type == "builtin":
            templates = self.template_repo.list_builtin()
        elif template_type == "custom":
            templates = self.template_repo.list_custom()
        else:
            templates = self.template_repo.list_all()

        logger.debug(f"查询到 {len(templates)} 个模板")
        return templates

    def create_template(self, template_data: PromptTemplateCreate) -> PromptTemplate:
        """
        创建自定义模板
        
        Args:
            template_data: 模板创建数据
            
        Returns:
            创建的 PromptTemplate 对象
        """
        logger.info(f"创建模板: label={template_data.label}")

        template_dict = {
            "label": template_data.label,
            "text": template_data.text,
            "description": (template_data.description or "").strip(),
            "is_builtin": False,
        }

        template = self.template_repo.create(template_dict)
        logger.info(f"模板创建成功: {template.id}")

        return template

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """
        根据 ID 获取模板
        
        Args:
            template_id: 模板 ID
            
        Returns:
            PromptTemplate 对象，不存在则返回 None
        """
        logger.debug(f"获取模板: template_id={template_id}")
        return self.template_repo.get_by_id(template_id)

    def update_template(
        self, 
        template_id: str, 
        template_data: PromptTemplateUpdate
    ) -> Optional[PromptTemplate]:
        """
        更新模板（仅允许更新自定义模板）
        
        Args:
            template_id: 模板 ID
            template_data: 更新数据
            
        Returns:
            更新后的 PromptTemplate 对象，不存在或不能更新则返回 None
        """
        logger.info(f"更新模板: template_id={template_id}")

        # 获取模板
        template = self.template_repo.get_by_id(template_id)
        if not template:
            logger.warning(f"更新失败，模板不存在: {template_id}")
            return None

        # 检查是否是内置模板
        if template.is_builtin:
            logger.warning(f"更新失败，内置模板不可修改: {template_id}")
            return None

        # 构建更新数据
        updates = {}
        if template_data.label is not None:
            updates["label"] = template_data.label
        if template_data.text is not None:
            updates["text"] = template_data.text
        if template_data.description is not None:
            updates["description"] = template_data.description.strip()

        if not updates:
            logger.warning(f"更新失败，没有提供更新字段: {template_id}")
            return template

        # 更新模板
        updated_template = self.template_repo.update(template_id, updates)
        logger.info(f"模板更新成功: {template_id}")

        return updated_template

    def delete_template(self, template_id: str) -> bool:
        """
        删除模板（仅允许删除自定义模板）
        
        Args:
            template_id: 模板 ID
            
        Returns:
            是否删除成功
        """
        logger.info(f"删除模板: template_id={template_id}")

        # 获取模板
        template = self.template_repo.get_by_id(template_id)
        if not template:
            logger.warning(f"删除失败，模板不存在: {template_id}")
            return False

        # 检查是否是内置模板
        if template.is_builtin:
            logger.warning(f"删除失败，内置模板不可删除: {template_id}")
            return False

        # 删除模板
        success = self.template_repo.delete(template_id)
        if success:
            logger.info(f"模板删除成功: {template_id}")
        else:
            logger.error(f"模板删除失败: {template_id}")

        return success

    # ==========================================
    # 模板辅助方法
    # ==========================================

    def _build_template_response(self, template: PromptTemplate) -> PromptTemplateResponse:
        """
        构建模板响应
        
        Args:
            template: 模板对象
            
        Returns:
            PromptTemplateResponse 对象
        """
        desc = getattr(template, "description", None)
        if desc is None:
            desc = ""
        return PromptTemplateResponse(
            id=template.id,
            label=template.label,
            description=desc,
            text=template.text,
            is_builtin=template.is_builtin,
            sort_order=template.sort_order,
            created_at=template.created_at
        )

    def _build_template_list_response(
        self, 
        templates: List[PromptTemplate]
    ) -> PromptTemplateListResponse:
        """
        构建模板列表响应
        
        Args:
            templates: 模板列表
            
        Returns:
            PromptTemplateListResponse 对象
        """
        template_responses = [self._build_template_response(t) for t in templates]
        return PromptTemplateListResponse(
            templates=template_responses,
            total=len(templates)
        )

    def build_template_response(self, template: PromptTemplate) -> PromptTemplateResponse:
        """构建模板响应（公开方法）"""
        return self._build_template_response(template)

    def build_template_list_response(
        self, 
        templates: List[PromptTemplate]
    ) -> PromptTemplateListResponse:
        """构建模板列表响应（公开方法）"""
        return self._build_template_list_response(templates)


logger.debug("RepairService 加载完成")
