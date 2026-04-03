# 异步任务处理设计文档

> 最后更新：2026-04-03  
> 所属项目：AetherFrame - 图片修补模块  
> 对应任务：To Do 10 - 实现异步任务处理

---

## 概述

本文档详细设计图片修补模块的异步任务处理功能，采用轻量级方案，避免引入复杂的任务队列，遵循个人项目的易维护原则。

---

## 设计原则

### 轻量级优先
- 使用 FastAPI BackgroundTasks 而非 Celery/RQ
- 本地数据库轮询状态更新
- 零额外依赖

### 易维护
- 清晰的业务逻辑分层
- 完整的任务生命周期管理
- 详细的日志记录

### 可扩展
- 预留任务队列扩展接口
- 支持任务重试机制
- 支持任务进度反馈

---

## 技术方案选型

### 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|-----|------|------|---------|
| **FastAPI BackgroundTasks** | 轻量级、零配置、与FastAPI无缝集成 | 重启后任务丢失、无重试机制 | 个人项目、短期任务 |
| Celery | 功能完整、支持分布式、任务持久化 | 复杂、依赖Redis/RabbitMQ | 企业级、大规模应用 |
| RQ (Redis Queue) | 简单、基于Redis | 依赖Redis、功能相对简单 | 中等规模项目 |

### 最终选择

**FastAPI BackgroundTasks + 数据库状态管理**

理由：
- 个人项目，任务量小
- 图片修补任务时间可控（几分钟内完成）
- 简化架构，降低维护成本
- 未来可轻松升级到Celery

---

## 任务状态机设计

### 状态定义

| 状态 | 说明 | 允许的下一状态 |
|-----|------|---------------|
| `pending` | 任务创建，等待处理 | `processing`, `failed` |
| `processing` | 任务正在处理中 | `completed`, `failed` |
| `completed` | 任务处理成功 | -（终态） |
| `failed` | 任务处理失败 | -（终态） |

### 状态转换图

```
pending
  │
  ├─→ processing
  │     │
  │     ├─→ completed
  │     │
  │     └─→ failed
  │
  └─→ failed (启动失败)
```

---

## 架构设计

### 分层架构

```
┌─────────────────────────────────┐
│   API Router Layer              │
│   - repair.py                   │
│   * 接收启动请求                │
│   * 返回任务状态                │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   Task Service Layer            │
│   - repair_service/repair_task… │ ← 任务服务
│   * 任务启动                    │
│   * 状态更新                    │
│   * 进度跟踪                    │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   Image Generation Layer        │
│   - repair_service/image_gen…   │
│   * 调用图片生成工具            │
│   * 保存结果图片                │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   BackgroundTasks               │
│   - FastAPI 内置                │
│   * 异步执行                    │
└─────────────────────────────────┘
```

### 目录结构

```
app/
├── services/
│   ├── repair_service/           # 修补领域包
│   │   ├── repair_task_service.py
│   │   ├── image_generation_service.py
│   │   ├── repair_service.py
│   │   ├── repair_file_service.py
│   │   └── repair_execution.py
│   ├── file_service.py
│   └── directory_service.py
├── routes/
│   └── repair.py
└── schemas/
    └── repair.py
```

---

## 核心模块设计

### 1. RepairTaskService - 任务处理服务

#### 职责
- 管理任务生命周期
- 处理任务启动、取消、重试
- 更新任务状态和进度
- 错误处理和日志记录

#### 核心方法

```python
class RepairTaskService:
    def __init__(self, db: Session):
        self.task_repo = RepairTaskRepository(db)
        self.db = db
    
    # ========== 任务启动 ==========
    async def start_task(
        self,
        task_id: str,
        use_reference_images: bool = True,
        background_tasks: BackgroundTasks = None
    ) -> RepairTask:
        """
        启动修补任务
        - 验证任务状态
        - 验证主图存在
        - 添加后台任务
        - 更新状态为processing
        """
    
    # ========== 任务执行 ==========
    async def _execute_task(
        self,
        task_id: str,
        use_reference_images: bool
    ):
        """
        后台执行任务
        - 更新状态为processing
        - 调用图片生成服务
        - 保存结果图片
        - 更新状态为completed/failed
        """
    
    # ========== 状态更新 ==========
    def _update_task_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[RepairTask]:
        """
        更新任务状态
        - 验证状态转换合法性
        - 更新updated_at时间戳
        """
    
    # ========== 进度跟踪（预留） ==========
    def _update_task_progress(
        self,
        task_id: str,
        progress: int,  # 0-100
        message: Optional[str] = None
    ):
        """
        更新任务进度（预留功能）
        """
```

### 2. ImageGenerationService - 图片生成服务

#### 职责
- 封装图片生成工具调用
- 处理输入图片
- 调用AI生成模型
- 保存生成结果

#### 核心方法

```python
class ImageGenerationService:
    def __init__(self):
        pass
    
    async def generate_repair_images(
        self,
        task_id: str,
        prompt: str,
        output_count: int,
        use_reference_images: bool = True
    ) -> List[str]:
        """
        生成修补图片
        - 加载主图
        - 加载参考图（如果启用）
        - 调用图片生成工具
        - 保存结果图片
        - 返回结果文件路径列表
        """
    
    def _load_main_image(self, task_id: str) -> bytes:
        """加载主图"""
    
    def _load_reference_images(self, task_id: str) -> List[bytes]:
        """加载参考图"""
    
    def _save_result_images(
        self,
        task_id: str,
        images: List[bytes]
    ) -> List[str]:
        """保存结果图片"""
```

---

## API 接口设计

### 1. 启动任务

**接口**：`POST /api/repair/tasks/{task_id}/start`

**功能**：启动修补任务的异步处理

**路径参数**：
- `task_id` (string, required): 任务 ID

**请求体**：
```json
{
  "useReferenceImages": true
}
```

**字段说明**：
- `useReferenceImages` (bool, optional): 是否使用参考图，默认 true

**响应示例**：
```json
{
  "success": true,
  "data": {
    "id": "task-001",
    "status": "processing",
    "updatedAt": "2026-04-03T10:00:00Z"
  },
  "message": "任务已开始处理"
}
```

**错误响应**：
| HTTP 状态码 | 说明 |
|------------|------|
| 404 | 任务不存在 |
| 409 | 任务状态不允许启动（非pending） |
| 400 | 主图未上传 |

---

### 2. 获取任务状态

**接口**：`GET /api/repair/tasks/{task_id}/status`

**功能**：获取任务处理状态（用于轮询）

**路径参数**：
- `task_id` (string, required): 任务 ID

**响应示例**：
```json
{
  "success": true,
  "data": {
    "id": "task-001",
    "status": "processing",
    "progress": 50,  // 预留字段
    "errorMessage": null,
    "updatedAt": "2026-04-03T10:05:00Z",
    "resultImages": [  // 只有completed时才有
      {
        "filename": "result_0.png",
        "url": "/api/repair/tasks/task-001/images/result/result_0.png"
      }
    ]
  }
}
```

---

## 数据模型扩展

### 扩展 RepairTask 模型（已存在）

已有的模型字段已足够，无需新增字段。

### 扩展 Pydantic Schemas

在 `app/schemas/repair.py` 中添加：

```python
# ========== 任务启动 ==========
class TaskStartRequest(BaseModel):
    use_reference_images: bool = Field(True, description="是否使用参考图")

# ========== 任务状态响应 ==========
class TaskStatusResponse(BaseModel):
    id: str
    status: str
    progress: Optional[int] = Field(None, ge=0, le=100)  # 预留
    error_message: Optional[str]
    updated_at: datetime
    result_images: Optional[List[ImageInfo]] = None
    
    class Config:
        from_attributes = True
```

---

## 任务执行流程

### 完整流程图

```
1. 前端请求 POST /api/repair/tasks/{task_id}/start
   ↓
2. 验证任务存在且状态为 pending
   ↓
3. 验证主图已上传
   ↓
4. 更新任务状态为 processing
   ↓
5. 将 _execute_task 添加到 BackgroundTasks
   ↓
6. 立即返回响应给前端
   ↓
7. 后台开始执行 _execute_task:
   a. 加载主图和参考图
   b. 调用图片生成服务
   c. 保存结果图片
   d. 更新任务状态为 completed/failed
   ↓
8. 前端轮询 GET /api/repair/tasks/{task_id}/status
   ↓
9. 显示最终结果或错误信息
```

---

## 错误处理

### 错误类型

| 阶段 | 错误类型 | 处理方式 |
|-----|---------|---------|
| 任务启动 | 任务不存在 | 404 Not Found |
| 任务启动 | 任务状态不为pending | 409 Conflict |
| 任务启动 | 主图未上传 | 400 Bad Request |
| 任务执行 | 图片生成失败 | 记录错误，状态设为failed |
| 任务执行 | 文件保存失败 | 记录错误，状态设为failed |
| 任务执行 | 其他异常 | 记录错误，状态设为failed |

### 错误日志记录

```python
import logging

logger = logging.getLogger(__name__)

try:
    # 任务执行代码
    logger.info(f"开始执行任务: {task_id}")
    # ...
    logger.info(f"任务完成: {task_id}")
except Exception as e:
    logger.error(f"任务执行失败: {task_id}", exc_info=True)
    # 更新状态为failed
```

---

## 与现有模块集成

### 1. 在 repair.py 路由中添加新端点

```python
# app/routes/repair.py

from app.services.repair_service import RepairTaskService

@router.post("/tasks/{task_id}/start", response_model=ApiResponse)
async def start_task(
    task_id: str,
    request: TaskStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """启动修补任务"""
    service = RepairTaskService(db)
    task = await service.start_task(
        task_id,
        request.use_reference_images,
        background_tasks
    )
    return ApiResponse(
        success=True,
        data={
            "id": task.id,
            "status": task.status,
            "updatedAt": task.updated_at.isoformat()
        },
        message="任务已开始处理"
    )

@router.get("/tasks/{task_id}/status", response_model=ApiResponse)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """获取任务状态"""
    service = RepairTaskService(db)
    # ... 实现获取状态逻辑
```

### 2. 与 ImageGenerationService 集成

参考 `docs/backend/image_generation_integration.md` 中的设计。

---

## 实现检查清单

### 文档检查
- [x] 设计原则符合轻量级要求
- [x] 与整体架构适配
- [x] 任务状态机设计完整
- [x] API 设计简洁明了
- [x] 错误处理完整

### 代码实现检查（后续）
- [x] 修补任务与生成逻辑位于 `app/services/repair_service/` 包内
- [ ] 在 `app/schemas/repair.py` 中添加新模型
- [ ] 在 `app/routes/repair.py` 中添加新端点
- [ ] 编写单元测试
- [ ] 端到端测试：创建任务 → 上传图片 → 启动任务 → 轮询状态 → 查看结果

---

## 后续扩展

### 短期扩展（无需架构调整）
- 添加任务进度详细反馈（0-100%）
- 添加任务取消功能（processing → failed）
- 添加任务历史记录

### 中期扩展（小量调整）
- 使用 Celery 替代 BackgroundTasks（任务持久化）
- 添加任务重试机制
- 添加任务优先级

### 长期扩展（架构调整）
- 支持分布式任务处理
- 添加任务调度功能
- 添加任务统计和监控

---

## 总结

本文档详细设计了异步任务处理功能，采用 FastAPI BackgroundTasks 的轻量级方案：

✅ **轻量级**：无额外依赖，零配置  
✅ **易维护**：清晰的分层架构，职责分离  
✅ **状态管理**：完整的任务生命周期和状态机  
✅ **错误处理**：完善的异常处理和日志记录  
✅ **可扩展**：预留未来升级到 Celery 的接口  

设计与现有架构完美适配，可以直接开始实现。
