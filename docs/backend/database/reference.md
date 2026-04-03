# 数据库 API 参考

> 最后更新：2026-04-02  
> 所属项目：AetherFrame

---

## 目录

1. [数据库连接 API](#数据库连接-api)
2. [Repository 基类 API](#repository-基类-api)
3. [修补任务 Repository API](#修补任务-repository-api)
4. [Prompt 模板 Repository API](#prompt-模板-repository-api)

---

## 数据库连接 API

### 模块：`app.models.database`

---

#### `get_db()`

FastAPI 依赖注入函数，获取数据库 Session。

**用法：**
```python
from fastapi import Depends
from sqlalchemy.orm import Session
from app.models.database import get_db

@router.get("/items")
async def list_items(db: Session = Depends(get_db)):
    # 使用 db
    pass
```

---

#### `init_db()`

初始化数据库，创建所有表。

**用法：**
```python
from app.models.database import init_db

init_db()
```

**日志：**
```
========== 开始初始化数据库 ==========
所有数据表创建成功
========== 数据库初始化完成 ==========
```

---

#### `check_db_connection() -> bool`

检查数据库连接是否正常。

**返回：** `True` 连接正常，`False` 连接失败

**用法：**
```python
from app.models.database import check_db_connection

if check_db_connection():
    print("数据库连接正常")
else:
    print("数据库连接失败")
```

---

#### `get_db_info() -> dict`

获取数据库信息。

**返回字段：**
- `database_path` - 数据库文件路径
- `database_dir` - 数据库目录
- `connection_url` - SQLAlchemy 连接 URL
- `directory_exists` - 目录是否存在
- `database_exists` - 文件是否存在
- `database_size_bytes` - 文件大小（如存在）

**用法：**
```python
from app.models.database import get_db_info

info = get_db_info()
print(f"数据库大小: {info.get('database_size_bytes', 0)} bytes")
```

---

## Repository 基类 API

### 类：`app.repositories.base.BaseRepository[T]`

通用 Repository 基类，所有模块的 Repository 都可以继承此类。

---

#### `__init__(db: Session, model: Type[T])`

构造函数。

**参数：**
- `db` - SQLAlchemy Session
- `model` - 模型类

---

#### `get_by_id(id: str) -> Optional[T]`

根据 ID 获取单个实体。

**参数：**
- `id` - 实体 ID

**返回：** 实体对象或 None

---

#### `list_all(skip: int = 0, limit: int = 100, order_by=None) -> List[T]`

获取实体列表。

**参数：**
- `skip` - 跳过条数（分页）
- `limit` - 最大返回条数
- `order_by` - 排序表达式（可选）

**返回：** 实体列表

---

#### `create(data: Dict) -> T`

创建新实体。

**参数：**
- `data` - 字段字典

**返回：** 创建的实体

---

#### `update(id: str, updates: Dict) -> Optional[T]`

更新实体。

**参数：**
- `id` - 实体 ID
- `updates` - 要更新的字段字典

**返回：** 更新后的实体或 None

---

#### `delete(id: str) -> bool`

删除实体。

**参数：**
- `id` - 实体 ID

**返回：** 是否删除成功

---

#### `count() -> int`

统计实体数量。

**返回：** 实体总数

---

## 修补任务 Repository API

### 类：`app.repositories.repair_repository.RepairTaskRepository`

继承自 `BaseRepository[RepairTask]`

---

#### `create(task_data: Dict) -> RepairTask`

创建新任务（自动生成 ID 和默认状态）。

**参数：**
- `task_data` - 任务数据
  - `id` - 可选，任务 ID（自动生成）
  - `name` - 任务名称
  - `prompt` - 修补描述
  - `output_count` - 输出数量
  - `status` - 可选，状态（默认 pending）

**返回：** RepairTask 对象

---

#### `list(skip: int = 0, limit: int = 100) -> List[RepairTask]`

获取任务列表，按创建时间倒序。

**参数：**
- `skip` - 跳过条数
- `limit` - 最大返回条数

**返回：** RepairTask 列表

---

#### `update_status(task_id: str, status: str, error_message: Optional[str] = None) -> Optional[RepairTask]`

更新任务状态（专用方法）。

**参数：**
- `task_id` - 任务 ID
- `status` - 新状态（pending/processing/completed/failed）
- `error_message` - 错误信息（失败时）

**返回：** 更新后的 RepairTask 或 None

---

## Prompt 模板 Repository API

### 类：`app.repositories.repair_repository.PromptTemplateRepository`

继承自 `BaseRepository[PromptTemplate]`

---

#### `create(template_data: Dict) -> PromptTemplate`

创建新模板（自动生成 ID 和默认值）。

**参数：**
- `template_data` - 模板数据
  - `id` - 可选，模板 ID
  - `label` - 模板名称
  - `text` - 模板内容
  - `is_builtin` - 可选，是否内置（默认 False）
  - `sort_order` - 可选，排序（默认 0）

**返回：** PromptTemplate 对象

---

#### `list_builtin() -> List[PromptTemplate]`

获取内置模板列表，按 sort_order 排序。

**返回：** 内置模板列表

---

#### `list_custom() -> List[PromptTemplate]`

获取自定义模板列表，按创建时间倒序。

**返回：** 自定义模板列表

---

#### `list_all() -> List[PromptTemplate]`

获取所有模板，内置模板在前，自定义在后。

**返回：** 所有模板列表

---

#### `update(template_id: str, updates: Dict) -> Optional[PromptTemplate]`

更新模板（is_builtin 不可修改）。

**参数：**
- `template_id` - 模板 ID
- `updates` - 要更新的字段

**返回：** 更新后的 PromptTemplate 或 None

---

#### `delete(template_id: str) -> bool`

删除模板（只能删除自定义模板）。

**参数：**
- `template_id` - 模板 ID

**返回：** 是否删除成功（内置模板返回 False）

---

## 完整示例

### 使用 Repository 进行 CRUD

```python
from app.models.database import SessionLocal
from app.repositories.repair_repository import RepairTaskRepository

# 创建 Session
db = SessionLocal()

# 创建 Repository
repo = RepairTaskRepository(db)

# 创建
task = repo.create({
    "name": "测试任务",
    "prompt": "修补描述",
    "output_count": 2
})

# 查询
task = repo.get_by_id(task.id)

# 更新
repo.update(task.id, {"name": "新名称"})

# 更新状态
repo.update_status(task.id, "processing")

# 列表
tasks = repo.list(limit=10)

# 删除
repo.delete(task.id)

db.close()
```

---

**文档结束**
