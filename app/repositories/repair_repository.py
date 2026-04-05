import logging
import uuid
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.repositories.base import BaseRepository
from app.models.repair import RepairTask, PromptTemplate

logger = logging.getLogger(__name__)


class RepairTaskRepository(BaseRepository[RepairTask]):
    """修补任务数据访问层"""
    
    def __init__(self, db: Session):
        super().__init__(db, RepairTask)
    
    def create(self, task_data: Dict) -> RepairTask:
        """创建新任务"""
        task_data = task_data.copy()
        if "id" not in task_data:
            task_data["id"] = f"task_{uuid.uuid4().hex[:8]}"
        if "status" not in task_data:
            task_data["status"] = "pending"
        
        task = super().create(task_data)
        logger.info(f"创建任务成功: {task.id} - {task.name}")
        return task
    
    def list(self, skip: int = 0, limit: int = 100) -> List[RepairTask]:
        """获取任务列表，按创建时间倒序"""
        logger.debug(f"查询任务列表: skip={skip}, limit={limit}")
        return super().list_all(skip, limit, order_by=desc(RepairTask.created_at))
    
    def update_status(
        self, 
        task_id: str, 
        status: str, 
        error_message: Optional[str] = None
    ) -> Optional[RepairTask]:
        """更新任务状态"""
        updates = {"status": status}
        if error_message is not None:
            updates["error_message"] = error_message
        
        logger.info(f"更新任务状态: {task_id} -> {status}")
        return self.update(task_id, updates)


class PromptTemplateRepository(BaseRepository[PromptTemplate]):
    """Prompt 模板数据访问层"""
    
    def __init__(self, db: Session):
        super().__init__(db, PromptTemplate)
    
    def create(self, template_data: Dict) -> PromptTemplate:
        """创建新模板"""
        template_data = template_data.copy()
        if "id" not in template_data:
            template_data["id"] = f"tpl_{uuid.uuid4().hex[:8]}"
        if "is_builtin" not in template_data:
            template_data["is_builtin"] = False
        if "sort_order" not in template_data:
            template_data["sort_order"] = 0
        if "description" not in template_data:
            template_data["description"] = ""
        if "tags" not in template_data:
            template_data["tags"] = "[]"

        template = super().create(template_data)
        logger.info(f"创建模板成功: {template.id} - {template.label}")
        return template
    
    def list_builtin(self) -> List[PromptTemplate]:
        """获取内置模板列表，按sort_order排序"""
        logger.debug("查询内置模板列表")
        return (
            self.db.query(PromptTemplate)
            .filter(PromptTemplate.is_builtin == True)
            .order_by(PromptTemplate.sort_order)
            .all()
        )
    
    def list_custom(self) -> List[PromptTemplate]:
        """获取自定义模板列表，按创建时间排序"""
        logger.debug("查询自定义模板列表")
        return (
            self.db.query(PromptTemplate)
            .filter(PromptTemplate.is_builtin == False)
            .order_by(desc(PromptTemplate.created_at))
            .all()
        )
    
    def list_all(self) -> List[PromptTemplate]:
        """获取所有模板，内置模板在前，自定义在后"""
        logger.debug("查询所有模板")
        builtin = self.list_builtin()
        custom = self.list_custom()
        return builtin + custom
    
    def update(self, template_id: str, updates: Dict) -> Optional[PromptTemplate]:
        """更新模板"""
        # 不允许修改 is_builtin
        updates = updates.copy()
        updates.pop("is_builtin", None)
        return super().update(template_id, updates)
    
    def delete(self, template_id: str) -> bool:
        """删除模板（只能删除自定义模板）"""
        template = self.get_by_id(template_id)
        if not template:
            logger.warning(f"删除失败，模板不存在: {template_id}")
            return False
        
        if template.is_builtin:
            logger.warning(f"删除失败，内置模板不可删除: {template_id}")
            return False
        
        return super().delete(template_id)
