"""
修补任务异步处理服务

负责使用 FastAPI BackgroundTasks 处理异步任务
"""
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from app.models.repair import RepairTask
from app.repositories.repair_repository import RepairTaskRepository
from app.services import repair_file_service
from app.services import image_generation_service

logger = logging.getLogger(__name__)


class RepairTaskService:
    """修补任务异步处理服务"""

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = RepairTaskRepository(db)

    # ==========================================
    # 任务启动
    # ==========================================

    async def start_task(
        self,
        task_id: str,
        use_reference_images: bool = True,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> RepairTask:
        """
        启动修补任务

        Args:
            task_id: 任务 ID
            use_reference_images: 是否使用参考图
            background_tasks: FastAPI BackgroundTasks 对象

        Returns:
            更新后的 RepairTask 对象

        Raises:
            ValueError: 任务不存在、状态不允许或主图不存在
        """
        logger.info(f"启动修补任务: task_id={task_id}, use_reference_images={use_reference_images}")

        # 1. 获取任务
        task = self.task_repo.get_by_id(task_id)
        if not task:
            error_msg = f"任务不存在: {task_id}"
            logger.warning(error_msg)
            raise ValueError(error_msg)

        # 2. 检查任务状态
        if task.status != "pending":
            error_msg = f"任务状态不允许启动，当前状态: {task.status}"
            logger.warning(error_msg)
            raise ValueError(error_msg)

        # 3. 检查主图是否存在
        main_image_path = repair_file_service.get_main_image_path(task_id)
        if not main_image_path:
            error_msg = "主图不存在，请先上传主图"
            logger.warning(error_msg)
            raise ValueError(error_msg)

        # 4. 更新任务状态为 processing
        updated_task = self.task_repo.update(task_id, {
            "status": "processing",
            "error_message": None
        })
        logger.info(f"任务状态更新为 processing: {task_id}")

        # 5. 获取参考图路径（如果需要）
        reference_image_paths = []
        if use_reference_images:
            ref_filenames = repair_file_service.list_reference_images(task_id)
            for filename in ref_filenames:
                ref_path = repair_file_service.get_reference_image_path(task_id, filename)
                if ref_path:
                    reference_image_paths.append(ref_path)
            logger.debug(f"使用 {len(reference_image_paths)} 张参考图")
        else:
            logger.debug("不使用参考图")

        # 6. 添加后台任务
        if background_tasks:
            background_tasks.add_task(
                self._execute_task,
                task_id=task_id,
                prompt=task.prompt,
                main_image_path=main_image_path,
                reference_image_paths=reference_image_paths,
                output_count=task.output_count
            )
            logger.info(f"已添加后台任务: task_id={task_id}")
        else:
            logger.warning("没有提供 background_tasks，任务将同步执行")
            # 同步执行（用于测试或特殊情况）
            await self._execute_task(
                task_id=task_id,
                prompt=task.prompt,
                main_image_path=main_image_path,
                reference_image_paths=reference_image_paths,
                output_count=task.output_count
            )

        return updated_task

    # ==========================================
    # 任务执行（后台）
    # ==========================================

    async def _execute_task(
        self,
        task_id: str,
        prompt: str,
        main_image_path: str,
        reference_image_paths: List[str],
        output_count: int
    ) -> None:
        """
        后台执行任务

        Args:
            task_id: 任务 ID
            prompt: 修补 Prompt
            main_image_path: 主图路径
            reference_image_paths: 参考图路径列表
            output_count: 输出数量
        """
        logger.info(f"开始后台执行任务: task_id={task_id}, output_count={output_count}")

        temp_image_paths = []
        try:
            # 1. 调用 ImageGenerationService 生成图片
            result_image_paths, error_message = image_generation_service.generate_repair_images(
                task_id=task_id,
                prompt_template=prompt,
                main_image_path=main_image_path,
                reference_image_paths=reference_image_paths,
                output_count=output_count
            )

            temp_image_paths = result_image_paths

            # 2. 检查结果
            if error_message:
                logger.error(f"图片生成失败: {error_message}")
                self._update_task_status(task_id, "failed", error_message)
                return

            if not result_image_paths:
                error_msg = "没有生成任何图片"
                logger.error(error_msg)
                self._update_task_status(task_id, "failed", error_msg)
                return

            # 3. 保存生成的图片到任务目录
            saved_count = 0
            for i, temp_path in enumerate(result_image_paths):
                try:
                    # 读取临时文件
                    with open(temp_path, "rb") as f:
                        image_data = f.read()

                    # 保存到任务目录
                    repair_file_service.save_result_image(task_id, image_data, index=i)
                    saved_count += 1
                    logger.info(f"结果图 {i} 保存成功")
                except Exception as e:
                    logger.error(f"保存结果图 {i} 失败: {e}", exc_info=True)

            # 4. 更新任务状态
            if saved_count > 0:
                self._update_task_status(task_id, "completed")
                logger.info(f"修补任务完成: task_id={task_id}, 成功生成 {saved_count} 张图片")
            else:
                self._update_task_status(task_id, "failed", "所有结果图保存失败")
                logger.error(f"修补任务失败: 所有结果图保存失败")

        except Exception as e:
            error_msg = f"执行任务时发生异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._update_task_status(task_id, "failed", error_msg)
        finally:
            # 清理临时文件
            image_generation_service.cleanup_temp_images(temp_image_paths)

    # ==========================================
    # 状态更新
    # ==========================================

    def _update_task_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[RepairTask]:
        """
        更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态
            error_message: 错误信息（仅失败时）

        Returns:
            更新后的 RepairTask 对象
        """
        logger.info(f"更新任务状态: task_id={task_id}, status={status}")

        updates = {"status": status}
        if error_message is not None:
            updates["error_message"] = error_message
        else:
            updates["error_message"] = None

        updated_task = self.task_repo.update(task_id, updates)
        if updated_task:
            logger.info(f"任务状态更新成功: task_id={task_id}, status={status}")
        else:
            logger.warning(f"任务状态更新失败: task_id={task_id}")

        return updated_task

    # ==========================================
    # 任务状态查询
    # ==========================================

    def get_task_status(self, task_id: str) -> Optional[RepairTask]:
        """
        获取任务状态

        Args:
            task_id: 任务 ID

        Returns:
            RepairTask 对象，不存在则返回 None
        """
        logger.debug(f"获取任务状态: task_id={task_id}")
        return self.task_repo.get_by_id(task_id)


logger.debug("RepairTaskService 加载完成")
