# 修补模块 API 完整参考文档

> 最后更新：2026-04-03  
> 所属项目：AetherFrame - 图片修补模块  
> 版本：v2.0

---

## 目录

1. [概述](#概述)
2. [设计原则](#设计原则)
3. [架构设计](#架构设计)
4. [API 接口总览](#api-接口总览)
5. [任务管理接口](#任务管理接口)
6. [文件上传接口](#文件上传接口)
7. [Prompt 模板接口](#prompt-模板接口)
8. [任务执行接口](#任务执行接口)
9. [统一响应格式](#统一响应格式)
10. [错误处理](#错误处理)

---

## 概述

本文档描述图片修补模块的完整 API 设计，包含任务管理、文件上传、Prompt 模板和任务执行四个主要功能模块。采用清晰的分层架构（Router → Service → Repository），遵循轻量级、易维护的个人项目开发原则。

### 技术栈

- **Web 框架**: FastAPI 0.104.1
- **数据库**: SQLite + SQLAlchemy 2.0.35
- **数据验证**: Pydantic
- **测试框架**: Pytest 7.4.3

---

## 设计原则

### 轻量级优先
- 使用标准 RESTful 风格
- 避免过度复杂的响应格式
- 最小化依赖

### 易维护
- 清晰的分层架构（Router → Service → Repository）
- 统一的错误处理
- 完整的日志记录

### 可扩展
- 预留未来功能扩展空间
- 支持分页和排序
- 统一的 API 响应格式

### 安全可靠
- 文件类型验证（PNG、JPG、WebP）
- 文件大小限制（10MB/张）
- 文件名安全处理
- 路径遍历防护

---

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────┐
│         路由层 (Routes)                  │
│  app/routes/repair.py                    │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│       业务逻辑层 (Services)               │
│  app/services/repair_service/            │
│  (repair_service, repair_task_service,   │
│   image_generation_service, …)           │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│      数据访问层 (Repositories)           │
│  app/repositories/repair_repository.py   │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│        数据模型层 (Models)                │
│  app/models/repair.py                    │
│  app/models/database.py                  │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│        SQLite 数据库 + 文件系统           │
│  data/db/aetherframe.db                  │
│  data/repair/tasks/{task_id}/            │
└─────────────────────────────────────────┘
```

### 目录结构

```
app/
├── schemas/                          # Pydantic 模式
│   ├── __init__.py
│   └── repair.py                     # 修补模块 API 模式
├── models/                           # 数据模型
│   ├── __init__.py
│   ├── database.py                   # 数据库配置
│   └── repair.py                     # 修补模块数据模型
├── repositories/                     # 数据访问层
│   ├── __init__.py
│   └── repair_repository.py          # 修补模块 Repository
├── services/                         # 业务逻辑层
│   └── repair_service/               # 修补领域包
│       ├── repair_service.py         # 修补业务逻辑
│       ├── repair_task_service.py    # 异步任务处理
│       ├── repair_file_service.py    # 修补文件服务
│       ├── image_generation_service.py
│       └── repair_execution.py
│   └── directory_service.py          # 目录服务
├── routes/                           # API 路由
│   ├── __init__.py
│   └── repair.py                     # 修补模块路由
└── main.py                           # 应用入口
```

---

## API 接口总览

### 基础路径

所有 API 端点的基础路径为：`/api/repair`

### 接口分类

| 模块 | 端点前缀 | 功能描述 |
|------|---------|---------|
| 任务管理 | `/tasks` | 任务的 CRUD 操作 |
| 文件上传 | `/tasks/{task_id}/images` | 主图、参考图的上传和管理 |
| Prompt 模板 | `/templates` | Prompt 模板的 CRUD 操作 |
| 任务执行 | `/tasks/{task_id}/start, /tasks/{task_id}/status` | 启动和监控异步任务 |

---

## 任务管理接口

### 1. 获取任务列表

**接口**: `GET /api/repair/tasks`

**功能**: 获取所有修补任务列表，支持分页、排序和状态过滤

**查询参数**:
- `skip` (int, optional): 跳过数量，默认 0
- `limit` (int, optional): 返回数量，默认 50，最大 100
- `order_by` (string, optional): 排序字段，默认 `created_at`
  - 可选值: `id`, `name`, `status`, `created_at`, `updated_at`
- `order_dir` (string, optional): 排序方向，`asc` 或 `desc`，默认 `desc`
- `status` (string, optional): 按状态过滤
  - 可选值: `pending`, `processing`, `completed`, `failed`

**响应示例**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "task-001",
        "name": "樱花少女服装修补",
        "status": "completed",
        "prompt": "修补裙子上的破损部分",
        "output_count": 2,
        "created_at": "2026-04-01T12:00:00Z",
        "updated_at": "2026-04-01T12:30:00Z",
        "has_main_image": true,
        "reference_image_count": 3,
        "result_image_count": 2
      }
    ],
    "total": 1,
    "skip": 0,
    "limit": 50
  },
  "message": "获取任务列表成功"
}
```

---

### 2. 创建新任务

**接口**: `POST /api/repair/tasks`

**功能**: 创建新的修补任务

**请求体**:
```json
{
  "name": "任务名称",
  "prompt": "任务描述和修补要求",
  "output_count": 2
}
```

**字段说明**:
- `name` (string, required): 任务名称，1-200 字符
- `prompt` (string, optional): 任务描述和修补要求
- `output_count` (int, required): 生成图片数量，1-10

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "task-001",
    "name": "任务名称",
    "status": "pending",
    "prompt": "任务描述和修补要求",
    "output_count": 2,
    "created_at": "2026-04-02T10:00:00Z",
    "updated_at": "2026-04-02T10:00:00Z",
    "has_main_image": false,
    "reference_image_count": 0,
    "result_image_count": 0
  },
  "message": "任务创建成功"
}
```

---

### 3. 获取任务详情

**接口**: `GET /api/repair/tasks/{task_id}`

**功能**: 获取指定任务的详细信息

**路径参数**:
- `task_id` (string, required): 任务 ID

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "task-001",
    "name": "樱花少女服装修补",
    "status": "pending",
    "prompt": "修补裙子上的破损部分",
    "output_count": 2,
    "created_at": "2026-04-01T12:00:00Z",
    "updated_at": "2026-04-01T12:00:00Z",
    "has_main_image": true,
    "reference_image_count": 2,
    "result_image_count": 0,
    "error_message": null,
    "main_image": {
      "filename": "main.png",
      "url": "/api/repair/tasks/task-001/images/main/main.png"
    },
    "reference_images": [
      {
        "filename": "ref1.png",
        "url": "/api/repair/tasks/task-001/images/reference/ref1.png"
      }
    ],
    "result_images": []
  },
  "message": "获取任务详情成功"
}
```

---

### 4. 更新任务信息

**接口**: `PUT /api/repair/tasks/{task_id}`

**功能**: 更新任务信息（仅允许 pending 状态的任务）

**路径参数**:
- `task_id` (string, required): 任务 ID

**请求体**:
```json
{
  "name": "更新后的任务名称",
  "prompt": "更新后的描述",
  "output_count": 3
}
```

**字段说明**: 所有字段都是可选的

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "task-001",
    "name": "更新后的任务名称",
    "status": "pending",
    "prompt": "更新后的描述",
    "output_count": 3,
    "created_at": "2026-04-01T12:00:00Z",
    "updated_at": "2026-04-02T10:00:00Z",
    "has_main_image": false,
    "reference_image_count": 0,
    "result_image_count": 0
  },
  "message": "任务更新成功"
}
```

---

### 5. 删除任务

**接口**: `DELETE /api/repair/tasks/{task_id}`

**功能**: 删除任务及其所有文件

**路径参数**:
- `task_id` (string, required): 任务 ID

**响应示例**:
```json
{
  "success": true,
  "data": null,
  "message": "任务删除成功"
}
```

---

## 文件上传接口

### 1. 上传主图

**接口**: `POST /api/repair/tasks/{task_id}/main-image`

**功能**: 为指定任务上传主图，会覆盖已有的主图

**路径参数**:
- `task_id` (string, required): 任务 ID

**请求格式**: `multipart/form-data`

**表单字段**:
- `file` (File, required): 图片文件

**支持格式**: PNG、JPG/JPEG、WebP

**文件大小限制**: 最大 10MB

**响应示例**:
```json
{
  "success": true,
  "data": {
    "filename": "main_abc123.png",
    "url": "/api/repair/tasks/task-001/images/main/main_abc123.png",
    "task_id": "task-001"
  },
  "message": "主图上传成功"
}
```

---

### 2. 批量上传参考图

**接口**: `POST /api/repair/tasks/{task_id}/reference-images`

**功能**: 为指定任务批量上传参考图

**路径参数**:
- `task_id` (string, required): 任务 ID

**请求格式**: `multipart/form-data`

**表单字段**:
- `files` (File[], required): 图片文件列表

**支持格式**: PNG、JPG/JPEG、WebP

**文件大小限制**: 每张最大 10MB

**响应示例**:
```json
{
  "success": true,
  "data": {
    "uploaded": [
      {
        "filename": "ref_abc123.png",
        "url": "/api/repair/tasks/task-001/images/reference/ref_abc123.png"
      }
    ],
    "failed": [
      {
        "original_filename": "invalid.txt",
        "error": "不支持的文件格式"
      }
    ],
    "total": 2,
    "task_id": "task-001"
  },
  "message": "成功上传 1 张参考图，1 张失败"
}
```

---

### 3. 获取图片文件

**接口**: `GET /api/repair/tasks/{task_id}/images/{image_type}/{filename}`

**功能**: 获取指定的图片文件

**路径参数**:
- `task_id` (string, required): 任务 ID
- `image_type` (string, required): 图片类型
  - 可选值: `main` (主图), `reference` (参考图), `result` (结果图)
- `filename` (string, required): 文件名

**响应**: 图片文件（FileResponse）

---

### 4. 删除主图

**接口**: `DELETE /api/repair/tasks/{task_id}/main-image`

**功能**: 删除任务的主图

**路径参数**:
- `task_id` (string, required): 任务 ID

**响应示例**:
```json
{
  "success": true,
  "data": null,
  "message": "主图删除成功"
}
```

---

### 5. 删除参考图

**接口**: `DELETE /api/repair/tasks/{task_id}/reference-images/{filename}`

**功能**: 删除指定的参考图

**路径参数**:
- `task_id` (string, required): 任务 ID
- `filename` (string, required): 文件名

**响应示例**:
```json
{
  "success": true,
  "data": null,
  "message": "参考图删除成功"
}
```

---

## Prompt 模板接口

### 1. 获取模板列表

**接口**: `GET /api/repair/templates`

**功能**: 获取所有 Prompt 模板列表，内置模板在前，自定义模板在后

**查询参数**:
- `template_type` (string, optional): 模板类型过滤
  - 可选值: `builtin` (内置模板), `custom` (自定义模板)

**响应示例**:
```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "id": "template-001",
        "label": "通用服装修补",
        "text": "请修补图片中服装的破损部分，保持原有风格和颜色",
        "is_builtin": true,
        "sort_order": 1,
        "created_at": "2026-04-01T12:00:00Z"
      },
      {
        "id": "template-002",
        "label": "我的自定义模板",
        "text": "自定义修补描述...",
        "is_builtin": false,
        "sort_order": 100,
        "created_at": "2026-04-02T10:00:00Z"
      }
    ],
    "total": 2
  },
  "message": "获取模板列表成功"
}
```

---

### 2. 创建自定义模板

**接口**: `POST /api/repair/templates`

**功能**: 创建新的自定义 Prompt 模板

**请求体**:
```json
{
  "label": "模板名称",
  "text": "模板内容"
}
```

**字段说明**:
- `label` (string, required): 模板名称，1-100 字符
- `text` (string, required): 模板内容，1-2000 字符

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "template-003",
    "label": "模板名称",
    "text": "模板内容",
    "is_builtin": false,
    "sort_order": 101,
    "created_at": "2026-04-02T10:00:00Z"
  },
  "message": "模板创建成功"
}
```

---

### 3. 获取模板详情

**接口**: `GET /api/repair/templates/{template_id}`

**功能**: 获取指定模板的详细信息

**路径参数**:
- `template_id` (string, required): 模板 ID

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "template-001",
    "label": "通用服装修补",
    "text": "请修补图片中服装的破损部分，保持原有风格和颜色",
    "is_builtin": true,
    "sort_order": 1,
    "created_at": "2026-04-01T12:00:00Z"
  },
  "message": "获取模板详情成功"
}
```

---

### 4. 更新模板

**接口**: `PUT /api/repair/templates/{template_id}`

**功能**: 更新模板（仅允许更新自定义模板）

**路径参数**:
- `template_id` (string, required): 模板 ID

**请求体**:
```json
{
  "label": "更新后的名称",
  "text": "更新后的内容"
}
```

**字段说明**: 所有字段都是可选的

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "template-002",
    "label": "更新后的名称",
    "text": "更新后的内容",
    "is_builtin": false,
    "sort_order": 100,
    "created_at": "2026-04-02T10:00:00Z"
  },
  "message": "模板更新成功"
}
```

---

### 5. 删除模板

**接口**: `DELETE /api/repair/templates/{template_id}`

**功能**: 删除模板（仅允许删除自定义模板）

**路径参数**:
- `template_id` (string, required): 模板 ID

**响应示例**:
```json
{
  "success": true,
  "data": null,
  "message": "模板删除成功"
}
```

---

## 任务执行接口

### 1. 启动修补任务

**接口**: `POST /api/repair/tasks/{task_id}/start`

**功能**: 启动修补任务的异步处理

**路径参数**:
- `task_id` (string, required): 任务 ID

**请求体**:
```json
{
  "useReferenceImages": true
}
```

**字段说明**:
- `useReferenceImages` (bool, optional): 是否使用参考图，默认 true

**响应示例（成功）**:
```json
{
  "success": true,
  "data": {
    "id": "task-001",
    "status": "processing",
    "updated_at": "2026-04-03T10:00:00Z"
  },
  "message": "任务已开始处理"
}
```

**错误响应**:
| HTTP 状态码 | 说明 |
|------------|------|
| 404 | 任务不存在 |
| 409 | 任务状态不允许启动（非pending） |
| 400 | 主图未上传 |

---

### 2. 获取任务状态

**接口**: `GET /api/repair/tasks/{task_id}/status`

**功能**: 获取任务处理状态（用于轮询）

**路径参数**:
- `task_id` (string, required): 任务 ID

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "task-001",
    "status": "processing",
    "progress": null,
    "error_message": null,
    "updated_at": "2026-04-03T10:05:00Z",
    "result_images": null
  }
}
```

**任务完成时响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "task-001",
    "status": "completed",
    "progress": null,
    "error_message": null,
    "updated_at": "2026-04-03T10:10:00Z",
    "result_images": [
      {
        "filename": "result_0.png",
        "url": "/api/repair/tasks/task-001/images/result/result_0.png"
      },
      {
        "filename": "result_1.png",
        "url": "/api/repair/tasks/task-001/images/result/result_1.png"
      }
    ]
  }
}
```

---

## 统一响应格式

所有 API 响应使用统一格式：

### 成功响应

```json
{
  "success": true,
  "data": { /* 具体数据 */ },
  "message": "操作成功"
}
```

### 错误响应

```json
{
  "success": false,
  "data": null,
  "message": "错误描述"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `success` | boolean | 是 | 操作是否成功 |
| `data` | any | 否 | 返回的数据，成功时可能为 null |
| `message` | string | 否 | 提示信息或错误描述 |

---

## 错误处理

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 操作冲突（如状态不允许） |
| 500 | 服务器内部错误 |

### 常见错误信息

| 错误信息 | 说明 |
|----------|------|
| 任务不存在 | 指定的 task_id 不存在 |
| 模板不存在 | 指定的 template_id 不存在 |
| 任务状态不允许更新 | 任务不是 pending 状态 |
| 内置模板不允许更新 | 尝试修改内置模板 |
| 内置模板不允许删除 | 尝试删除内置模板 |
| 不支持的文件格式 | 文件格式不符合要求 |
| 文件大小超过限制 | 文件大小超过 10MB |
| 文件保存失败 | 文件系统写入失败 |

---

## 附录

### 文件目录结构

```
data/
├── db/
│   └── aetherframe.db          # SQLite 数据库文件
└── repair/
    └── tasks/
        └── {task_id}/
            ├── main/            # 主图目录
            │   └── {filename}
            ├── reference/       # 参考图目录
            │   └── {filename}
            └── result/          # 结果图目录
                └── {filename}
```

### 任务状态说明

| 状态 | 说明 |
|------|------|
| `pending` | 等待处理，任务刚创建，可以编辑 |
| `processing` | 处理中，正在生成图片 |
| `completed` | 已完成，图片生成成功 |
| `failed` | 失败，图片生成失败 |

### 完整修补任务流程

```
1. 创建任务
   POST /api/repair/tasks
   ↓

2. 上传主图
   POST /api/repair/tasks/{id}/main-image
   ↓

3. 上传参考图（可选）
   POST /api/repair/tasks/{id}/reference-images
   ↓

4. 启动修补任务
   POST /api/repair/tasks/{id}/start
   ↓

5. 轮询任务状态
   GET /api/repair/tasks/{id}/status
   ↓

6. 获取最终结果
   GET /api/repair/tasks/{id}
```

---

*文档结束*
