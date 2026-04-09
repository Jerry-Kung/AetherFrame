# 图片生成工具集成设计文档

> 最后更新：2026-04-03  
> 所属任务：To Do 9 - 集成图片生成工具  
> 所属项目：AetherFrame - 图片修补模块

---

## 概述

本文档详细描述图片修补模块中图片生成工具的集成方案，包括与现有 Nano Banana Pro 工具的对接、Prompt 拼接规则、业务流程设计等。

---

## 设计原则

1. **轻量级优先**：复用现有的 Nano Banana Pro 工具，避免重复开发
2. **易维护**：清晰的分层设计，职责分离
3. **可扩展**：为未来支持更多图片生成模型预留扩展空间
4. **可靠**：完善的错误处理和状态管理

---

## 现有工具分析

### Nano Banana Pro 工具

**文件位置**：`app/tools/llm/nano_banana_pro.py`

**核心函数**：
```python
def generate_image_with_nano_banana_pro(
    Content,
    output_path: str,
    file_name: str,
    aspect_ratio: str = "16:9",
) -> bool
```

**参数说明**：
- `Content`: 内容列表，格式为 `[{"text": "xxx"}, {"picture": "本地路径"}, ...]`
- `output_path`: 输出目录
- `file_name`: 保存的文件名
- `aspect_ratio`: 宽高比，默认 "16:9"

**返回值**：`bool` - 成功返回 True，失败返回 False

---

## Prompt 拼接规则

根据用户需求，图片修补阶段的 Prompt 拼接格式如下：

```python
content = [
    {"text": f"{修补prompt模版}"},
    {"picture": "待修补的图片路径"},
    {"text": "以下是角色参考图，作为你修补任务的重要参考"},
    {"picture": "角色参考图1路径"},
    {"picture": "角色参考图2路径"},
    # ... 更多参考图
]
```

**拼接顺序**：
1. 修补 Prompt 模板（文本）
2. 待修补的主图（图片）
3. 引导文本（固定）
4. 角色参考图列表（图片，顺序添加）

---

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────┐
│   API 层 (repair.py)                   │
│   - POST /tasks/{task_id}/start        │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│   RepairTaskService                     │
│   (repair_service/repair_task_service)  │
│   - start_task() / BackgroundTasks     │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│   repair_service/repair_execution.py      │
│   - run_repair_generation_pipeline()    │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│   repair_service/image_generation_...   │
│   - build_repair_content()              │
│   - generate_repair_images()            │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│   LLM Tools 层                          │
│   - nano_banana_pro.py                  │
└─────────────────────────────────────────┘
```

---

## 核心模块设计

### 1. ImageGenerationService（新增）

**文件位置**：`app/services/repair_service/image_generation_service.py`

**职责**：
- 构建图片修补任务的 Content 列表
- 调用 Nano Banana Pro 生成图片
- 处理生成结果
- 错误处理和重试

**核心方法**：

#### build_repair_content()
构建修补任务的 Content 列表

```python
def build_repair_content(
    prompt_template: str,
    main_image_path: str,
    reference_image_paths: List[str]
) -> List[Dict]:
    """
    构建图片修补任务的 Content 列表
    
    Args:
        prompt_template: 修补 Prompt 模板
        main_image_path: 主图路径
        reference_image_paths: 参考图路径列表
        
    Returns:
        Content 列表，符合 Nano Banana Pro 要求的格式
    """
```

#### generate_repair_images()
生成修补图片

```python
def generate_repair_images(
    task_id: str,
    prompt_template: str,
    main_image_path: str,
    reference_image_paths: List[str],
    output_count: int = 2,
    aspect_ratio: str = "16:9"
) -> Tuple[List[str], Optional[str], Optional[str]]:
    """
    生成修补图片
    
    Args:
        task_id: 任务 ID
        prompt_template: 修补 Prompt 模板
        main_image_path: 主图路径
        reference_image_paths: 参考图路径列表
        output_count: 输出图片数量
        aspect_ratio: 宽高比
        
    Returns:
        (成功生成的图片路径列表, 错误信息)
    """
```

---

### 2. RepairTaskService 与 repair_execution

生产路径由 **`RepairTaskService.start_task()`**（[`app/services/repair_service/repair_task_service.py`](../../app/services/repair_service/repair_task_service.py)）处理：校验任务、置为 `processing`、注册 `BackgroundTasks` 或使用 `asyncio.to_thread` 执行同步流水线。

同步生成与落盘逻辑集中在 **`run_repair_generation_pipeline()`**（[`app/services/repair_service/repair_execution.py`](../../app/services/repair_service/repair_execution.py)）：从任务记录读取 `aspect_ratio`（见下）并传入 `generate_repair_images`、写入结果目录、通过回调更新任务状态（后台任务使用独立 DB 会话）、最后清理临时文件。

`RepairService` 负责任务 CRUD、文件上传与响应组装，**不再**包含启动修补或生成流水线，避免与 `RepairTaskService` 重复实现。

---

## 任务状态流转

```
pending ──> processing ──> completed
                │
                └─────> failed
```

**状态说明**：
- `pending`: 任务创建完成，等待启动
- `processing`: 正在生成图片
- `completed`: 生成成功完成
- `failed`: 生成失败

---

## 错误处理策略

### 错误类型

1. **验证错误**：
   - 任务不存在
   - 任务状态不允许
   - 主图不存在
   - 参考图不存在

2. **生成错误**：
   - API 调用失败
   - 网络超时
   - 返回数据解析失败
   - 图片保存失败

3. **系统错误**：
   - 文件系统错误
   - 数据库错误

### 处理策略

- **验证错误**：立即返回，不更新任务状态
- **生成错误**：记录错误信息，更新任务状态为 `failed`，保存错误信息到 `error_message` 字段
- **系统错误**：记录详细日志，更新任务状态为 `failed`

---

## 目录结构影响

### 目录（当前）

修补相关实现集中在包 **`app/services/repair_service/`**（含 `image_generation_service.py`、`repair_execution.py`、`repair_task_service.py` 等）；路由仍在 `app/routes/repair.py`。

---

## API 接口设计

### POST /api/repair/tasks/{task_id}/start

启动修补任务

**请求体**：
```json
{
  "useReferenceImages": true
}
```

**响应示例（成功）**：
```json
{
  "success": true,
  "message": "任务已启动",
  "data": {
    "taskId": "task-001",
    "status": "processing"
  }
}
```

**响应示例（失败）**：
```json
{
  "success": false,
  "message": "任务不存在或状态不允许",
  "error": "具体错误信息"
}
```

---

## 使用示例

### 完整流程示例

```python
# 1. 创建任务
task = repair_service.create_task(TaskCreate(
    name="樱花少女服装修补",
    prompt="修复图片中的服装，使其更加完整",
    output_count=2
))

# 2. 上传主图
repair_service.upload_main_image(task.id, main_file)

# 3. 上传参考图
repair_service.upload_reference_images(task.id, ref_files)

# 4. 启动修补任务（由路由注入 BackgroundTasks，内部为 RepairTaskService.start_task）
# POST /api/repair/tasks/{task_id}/start
# 若在脚本中调用：await RepairTaskService(db).start_task(
#     task.id, use_reference_images=True, background_tasks=background_tasks
# )

# 5. 轮询获取任务状态
# GET /api/repair/tasks/{task_id}/status
```

---

## 配置项

### 图片生成相关

- **宽高比**：修补任务表 `repair_tasks.aspect_ratio` 持久化用户选择（`TaskCreate`/`TaskUpdate` 校验为 `16:9`、`4:3`、`1:1`、`3:4`、`9:16`）；`RepairTaskService.start_task` 将其传入 `run_repair_generation_pipeline` → `generate_repair_images` → `generate_image_with_nano_banana_pro`。未设置时逻辑默认与 `app/services/repair_service/image_generation_service.py` 中的 `DEFAULT_REPAIR_ASPECT_RATIO`（`16:9`）一致。
- **imageSize（如 2K）与 HTTP 调用**：由 `app/tools/llm/nano_banana_pro.py` 内建；若需可配置或超时/重试，应扩展该工具函数的参数与实现，而非在 service 层保留未使用的字典配置。

---

## 日志记录

### 日志级别

- `INFO`: 任务开始、完成等关键节点
- `DEBUG`: 详细的执行步骤
- `WARNING`: 非致命错误（如重试）
- `ERROR`: 致命错误

### 日志内容示例

```
[INFO] 启动修补任务: task_id=task-001
[DEBUG] 构建 Content 列表: prompt=..., main_image=..., refs=3
[INFO] 开始调用 Nano Banana Pro 生成图片
[DEBUG] 生成第 1 张图片...
[INFO] 图片生成成功: result_0.png
[DEBUG] 生成第 2 张图片...
[INFO] 图片生成成功: result_1.png
[INFO] 修补任务完成: task_id=task-001, 成功生成 2 张图片
```

---

## 测试要点

### 单元测试

1. `build_repair_content()` 测试
   - 正常情况（有参考图）
   - 正常情况（无参考图）
   - 参考图为空列表

2. `generate_repair_images()` 测试
   - 成功生成多张图片
   - 部分失败的情况
   - 全部失败的情况

### 集成测试

1. 完整流程测试
   - 创建任务 → 上传文件 → 启动任务 → 检查结果
   
2. 错误处理测试
   - 任务不存在时启动
   - 任务状态为 processing 时再次启动
   - 主图不存在时启动

---

## 后续扩展考虑

### 短期
- 支持更多图片生成模型（如 DALL-E、Midjourney API）
- 添加生成进度回调
- 支持生成参数自定义（温度、top_p 等）

### 中期
- 添加生成历史记录
- 支持结果图的后处理（裁剪、缩放等）
- 添加生成质量评估

### 长期
- 支持批量任务处理
- 添加生成任务队列
- 支持多模型对比生成

---

## 总结

本设计方案：
1. ✅ 复用现有的 Nano Banana Pro 工具
2. ✅ 遵循轻量级设计原则
3. ✅ 清晰的分层架构
4. ✅ 完善的错误处理
5. ✅ 与现有代码无缝集成
6. ✅ 为未来扩展预留空间

通过新增 `ImageGenerationService` 和扩展 `RepairService`，可以实现图片修补任务的完整流程。
