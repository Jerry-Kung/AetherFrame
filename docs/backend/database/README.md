# 数据库模块文档

> 最后更新：2026-04-02  
> 所属项目：AetherFrame - 图片修补模块

---

## 概述

本目录包含 AetherFrame 项目数据库相关的所有文档和参考。

---

## 目录结构

```
docs/backend/database/
├── README.md                      # 本文件 - 总览和快速参考
├── architecture.md                # 架构设计和可扩展性说明
└── reference.md                   # API 参考和使用示例
```

---

## 快速开始

### 1. 初始化数据库

数据库在应用启动时自动初始化：

```python
# app/main.py 中已配置
from app.models.database import init_db
init_db()
```

### 2. 使用 Repository

```python
from app.models.database import SessionLocal
from app.repositories.repair_repository import RepairTaskRepository, PromptTemplateRepository

# 获取 Session
db = SessionLocal()

# 使用 Repository
task_repo = RepairTaskRepository(db)
template_repo = PromptTemplateRepository(db)

# 创建任务
task = task_repo.create({
    "name": "我的任务",
    "prompt": "修补描述",
    "output_count": 2
})

# 查询模板
templates = template_repo.list_all()

db.close()
```

### 3. 健康检查

```bash
curl http://localhost:8000/health
```

响应示例：
```json
{
  "status": "ok",
  "service": "AetherFrame",
  "database": {
    "connected": true,
    "info": { ... }
  }
}
```

---

## 核心组件

### 1. 数据库连接（app/models/database.py）

| 组件 | 说明 |
|------|------|
| `engine` | SQLAlchemy 引擎 |
| `SessionLocal` | Session 工厂 |
| `Base` | 声明基类 |
| `get_db()` | FastAPI 依赖注入 |
| `init_db()` | 初始化表 |
| `check_db_connection()` | 连接检查 |
| `get_db_info()` | 获取数据库信息 |

### 2. 数据模型（app/models/repair.py）

| 模型 | 说明 |
|------|------|
| `RepairTask` | 修补任务表 |
| `PromptTemplate` | Prompt 模板表 |

### 3. Repository 层（app/repositories/）

| 文件 | 说明 |
|------|------|
| `base.py` | 通用 BaseRepository 基类 |
| `repair_repository.py` | 修补模块 Repository |

**BaseRepository 提供的通用方法：**
- `get_by_id(id)` - 根据 ID 获取
- `list_all(skip, limit, order_by)` - 获取列表
- `create(data)` - 创建
- `update(id, updates)` - 更新
- `delete(id)` - 删除
- `count()` - 统计

---

## 测试

运行数据库集成测试：

```bash
python -m pytest tests/test_database_integration.py -v
```

**测试覆盖：** 25 个测试用例 ✓
- 数据库连接（7个）
- RepairTaskRepository（7个）
- PromptTemplateRepository（9个）
- BaseRepository（2个）

---

## 文件存储位置

```
data/
└── db/
    └── aetherframe.db          # SQLite 数据库文件
```

---

## 后续添加新模块的步骤

如需添加新的功能模块（如素材加工、美图创作）：

1. **创建数据模型** - `app/models/{module}.py`
2. **创建 Repository** - `app/repositories/{module}_repository.py`（继承 BaseRepository）
3. **在 `init_db()` 中导入模型** - 确保表被创建
4. **添加测试** - `tests/test_database_integration.py`

---

## 更多信息

详细文档请参考同目录下的：
- [architecture.md](architecture.md) - 架构设计和可扩展性
- [reference.md](reference.md) - API 参考和使用示例
