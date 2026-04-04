# 数据库架构设计

> 最后更新：2026-04-02

---

## 设计原则

### 轻量级优先
- 使用 SQLite 单文件数据库
- 零配置，开箱即用
- 避免过度设计

### 易维护
- 清晰的分层架构
- 完整的日志记录
- 统一的 Repository 基类

### 可扩展
- BaseRepository 基类便于添加新模块
- 模块化的 Repository 设计
- 预留未来扩展空间

---

## 架构分层

```
┌─────────────────────────────────┐
│   API Router (FastAPI)        │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   Service 层 (业务逻辑)        │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   Repository 层 (数据访问)      │ ← 本层
│   - BaseRepository             │
│   - RepairTaskRepository       │
│   - PromptTemplateRepository   │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   SQLAlchemy ORM               │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   SQLite Database              │
│   (data/db/aetherframe.db)     │
└─────────────────────────────────┘
```

---

## BaseRepository 基类

### 设计目的
为所有模块的 Repository 提供通用功能，减少代码重复。

### 提供的通用方法
- `get_by_id(id)` - 根据 ID 获取单个实体
- `list_all(skip, limit, order_by)` - 获取实体列表（支持分页和排序）
- `create(data)` - 创建新实体
- `update(id, updates)` - 更新实体
- `delete(id)` - 删除实体
- `count()` - 统计实体数量

### 使用示例

```python
# 1. 继承 BaseRepository
class MyModelRepository(BaseRepository[MyModel]):
    def __init__(self, db: Session):
        super().__init__(db, MyModel)
    
    # 2. 添加模块特定的方法
    def find_by_status(self, status: str) -> List[MyModel]:
        return self.db.query(MyModel).filter(MyModel.status == status).all()
```

---

## 数据库配置

### 连接配置
```python
# SQLite 连接字符串
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# 引擎配置
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 多线程支持
    echo=False  # 设为 True 可查看 SQL 日志
)
```

### Session 管理
```python
# Session 工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# FastAPI 依赖注入
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 添加新模块的步骤

### 1. 创建数据模型
```python
# app/models/my_module.py
from app.models.database import Base

class MyModel(Base):
    __tablename__ = "my_models"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    # ... 其他字段
```

### 2. 创建 Repository
```python
# app/repositories/my_module_repository.py
from app.repositories.base import BaseRepository
from app.models.my_module import MyModel

class MyModelRepository(BaseRepository[MyModel]):
    def __init__(self, db: Session):
        super().__init__(db, MyModel)
    
    # 添加模块特定的方法
    def find_by_name(self, name: str) -> Optional[MyModel]:
        return self.db.query(MyModel).filter(MyModel.name == name).first()
```

### 3. 在 init_db() 中导入模型
```python
# app/models/database.py
def init_db():
    from app.models.repair import RepairTask, PromptTemplate
    from app.models.my_module import MyModel  # ← 添加这行
    
    Base.metadata.create_all(bind=engine)
```

### 4. 添加测试
在 `tests/test_database_integration.py` 中添加新模块的测试用例。

---

## Schema 演进（无 Alembic）

对 SQLite 的**列级变更**采用启动时轻量检测与 `ALTER TABLE` 补齐，例如 `app.models.database` 中的 `migrate_prompt_templates_add_description()`：在 `init_db()` 于 `create_all` 之后执行，若 `prompt_templates` 表缺少 `description` 列则添加，保证旧库升级与新建库一致。Prompt 模板的权威数据仍在数据库表中，不由 JSON 文件承载。

---

## 目录结构

```
app/
├── models/
│   ├── __init__.py
│   ├── database.py          # 数据库连接配置
│   └── repair.py            # 修补模块模型
└── repositories/
    ├── __init__.py
    ├── base.py              # BaseRepository 基类
    └── repair_repository.py # 修补模块 Repository
```

---

## 后续扩展考虑

### 短期（无需变更架构）
- 添加更多模块（素材加工、美图创作）
- 添加更多查询方法到现有 Repository
- 添加数据库备份工具

### 中期（小量调整）
- 添加 Alembic 数据库迁移
- 添加连接池配置
- 添加查询缓存

### 长期（架构调整）
- 支持其他数据库（PostgreSQL/MySQL）
- 添加读写分离
- 添加分布式缓存（Redis）
