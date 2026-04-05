import logging
from typing import List, Optional, Dict, Type, TypeVar, Generic
from sqlalchemy.orm import Session
from sqlalchemy import desc

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    通用 Repository 基类
    为所有模块的 Repository 提供通用功能
    """
    
    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model
    
    def get_by_id(self, id: str) -> Optional[T]:
        """根据ID获取单个实体"""
        logger.debug(f"查询 {self.model.__name__}: {id}")
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def list_all(self, skip: int = 0, limit: int = 100, order_by=None) -> List[T]:
        """获取所有实体列表"""
        query = self.db.query(self.model)
        
        if order_by is not None:
            query = query.order_by(order_by)
        else:
            # 默认按创建时间倒序
            if hasattr(self.model, 'created_at'):
                query = query.order_by(desc(self.model.created_at))
        
        return query.offset(skip).limit(limit).all()
    
    def create(self, data: Dict) -> T:
        """创建新实体"""
        entity = self.model(**data)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        logger.info(f"创建 {self.model.__name__} 成功: {entity.id}")
        return entity
    
    def update(self, id: str, updates: Dict) -> Optional[T]:
        """更新实体"""
        entity = self.get_by_id(id)
        if not entity:
            logger.warning(f"更新失败，{self.model.__name__} 不存在: {id}")
            return None
        
        for key, value in updates.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        
        self.db.commit()
        self.db.refresh(entity)
        logger.info(f"更新 {self.model.__name__} 成功: {id}")
        return entity
    
    def delete(self, id: str) -> bool:
        """删除实体"""
        entity = self.get_by_id(id)
        if not entity:
            logger.warning(f"删除失败，{self.model.__name__} 不存在: {id}")
            return False
        
        self.db.delete(entity)
        self.db.commit()
        logger.info(f"删除 {self.model.__name__} 成功: {id}")
        return True
    
    def count(self) -> int:
        """统计实体数量"""
        count = self.db.query(self.model).count()
        logger.debug(f"{self.model.__name__} 总数: {count}")
        return count
