# 视频创作模块设计文档

- 日期：2026-07-22
- 状态：待实现
- 定位：AetherFrame 第四大功能模块（素材加工 / 美图创作 / 图片修补 之外）

## 1. 背景与目标

当前项目为二次元角色创作的是静态单张图片。本模块让角色**动起来**：以灵感产线的美图产出为基底，编排一段简洁的居家风格文生视频 Prompt，调用 Seedance 2.0 文生视频模型，为角色生成一段美观的**居家动态写真**短视频。

### 1.1 视频内容纲领（约束 LLM Prompt 编排）

- 两大核心主题：**角色居家高级动态瞬间** + **自然展示角色腿脚 / 袜子**。腿脚/袜子自然展示是核心竞争力，Prompt 编排不得违反（见 memory `creation-leg-foot-exposure-principle`）。
- 4–15 秒短视频片段，高审美、有镜头感。
- 拒绝：故事化长剧情、复杂分镜、复杂动作、唱歌跳舞、做饭家务等低质俗套内容。
- 推荐创作方向：
  - 自然动态展示（呼吸、眨眼、头发、简单动作、场景互动）
  - 场景氛围（镜头推拉环绕、环境动态、真实世界感）
  - 服装美学展示（轻微转身、衣摆飘动、细节扫镜）
  - 镜头微互动（观众视角在角色面前与角色轻微互动）

参考示例（仅说明想法，非最佳）：

> 温暖的室内环境，阳光透过窗帘洒在木质地板上，角色正蹲下与活泼的小猫玩耍。镜头采用低角度固定拍摄，角色脚部及其周围区域始终保持在画面内。小猫时而绕过角色脚踝，时而轻轻用爪子拍打角色脚面，角色脚尖轻轻踢动逗弄小猫，地板上偶尔有纸球或小玩具滚动。镜头微微摇晃，营造出亲密随性的氛围，伴随轻柔的背景音乐和偶尔小猫咪呼噜声，整体画面温馨且生动，风格写实且细腻。

## 2. 已确认的产品决策

| 议题 | 决策 |
|---|---|
| 模块形态 | 完整作品库：视频落盘 `data/video/`，历史可回看 / 删除 |
| 导入来源 | 本地上传 + 灵感产线产出图卡片「去创作视频」跳转（带图 + 预生成 Prompt） |
| 图片在 Seedance 中的角色 | 首帧 / 参考图两种模式，UI 可切换，默认首帧 |
| Prompt 创作 | 模式 A（LLM 主导，单候选，可重新生成）+ 模式 B（手工输入，可选 LLM 优化） |
| 时长 | 4–15 秒自由选，默认 8 秒 |
| 音频 | 默认关闭（`generate_audio=false`），可手动开启 |
| 分辨率 | 用模型默认（不在 UI 暴露） |
| 长宽比 | 默认取最接近参考图宽高比的模型支持比例，可手动改 |
| 并发策略 | 串行单任务：存在 in-flight 视频任务时，新提交返回 409 |

## 3. 架构方案

采用**方案 A：独立第四模块，完整复刻现有分层**，与素材 / 创作 / 修补三模块结构对称。

### 3.1 后端新增文件

```
app/routes/video.py                      # /api/video 路由
app/services/video_service/
  __init__.py
  video_service.py                       # 任务编排：校验、创建、状态查询、历史、删除
  prompt_service.py                      # Prompt 编排：模式 A 生成 / 模式 B 优化
  runner.py                              # 后台任务：TOS 上传 → Seedance 轮询 → 下载落盘 → TOS 清理
  exceptions.py                          # 模块异常（冲突 / 未找到 / 通用错误）
app/models/video.py                      # VideoCreationTask 模型
app/repositories/video_repository.py     # 继承 BaseRepository[VideoCreationTask]
app/schemas/video.py                     # Pydantic 请求 / 响应
app/tools/llm/seedance.py                # 火山引擎 Ark SDK 封装（提交 + 轮询 + 下载）
app/prompts/video/
  __init__.py
  recommend.py                           # 模式 A：LLM 主导推荐 Prompt 模板
  optimize.py                            # 模式 B：LLM 优化用户 Prompt 模板
```

### 3.2 前端新增文件

```
page/src/pages/video/
  page.tsx
  components/                            # 参考图区 / Prompt 工作台 / 参数提交 / 历史列表
page/src/services/videoApi.ts
page/src/types/video.ts
```

- 路由 `/video` 注册进 `page/src/router/config.tsx`（lazy import + Suspense，与其他页面一致）。
- 首页导航按现有样式增加第四个模块入口。

### 3.3 复用与依赖

- **云存储**：直接 import `app/tools/beautify/storage.py` 的 `TosStorageClient`（已是通用 `CloudStorageClient` Protocol，桶 / AK / SK 现成）。不搬家、不重构。
- **LLM 文本推理**：`app/tools/llm/yibu_llm_infer.py` 的 `yibu_gemini_infer`（支持 `image_path` 多模态输入、`thinking_level`）。
- **缩略图**：`app/utils/thumbnails.get_or_create_thumbnail`。
- **文件响应缓存**：`app/utils/cache_response`。
- **新依赖**：`volcengine-python-sdk[ark]` 加入 `requirements.txt`。
- **配置**：Seedance 的 `api_key` / `base_url` / 模型 ID 加入 `app/tools/llm/config.py`（gitignored 惯例，需本地创建）。

## 4. 数据模型

### 4.1 `VideoCreationTask`（单表，风格参考 `ImageBeautifyTask`）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | String(40) PK | 任务 ID |
| source_kind | String(20) | `upload` / `quick_create` |
| source_task_id | String(64) nullable | 产线溯源任务 ID（upload 时空） |
| source_image_path | Text nullable | 产线溯源图相对路径（upload 时空） |
| ref_image_path | Text | 参考图在 `data/video/tasks/{id}/` 下的本地副本路径 |
| ref_prompt_text | Text nullable | 带入的生图 Prompt |
| video_prompt_text | Text nullable | 最终提交 Seedance 的视频 Prompt |
| prompt_mode | String(20) nullable | `llm` / `manual`（最终采用的 Prompt 来源） |
| image_role | String(20) | `first_frame` / `reference_image`，默认 `first_frame` |
| duration | Integer | 生成时长（秒），4–15 |
| generate_audio | Boolean | 默认 false |
| ratio | String(16) | 最终提交的长宽比（如 `3:4`） |
| status | String(20) | 见 §5 状态机 |
| prompt_job_status | String(20) nullable | LLM Prompt 作业状态：`pending` / `running` / `completed` / `failed` |
| prompt_job_result | Text nullable | LLM 作业产出的 Prompt 文本 |
| prompt_job_error | Text nullable | LLM 作业错误信息 |
| seedance_task_id | String(64) nullable | Ark 任务 ID（排障用） |
| video_filename | String(255) nullable | 落盘文件名（如 `output.mp4`） |
| error_message | Text nullable | 失败原因 |
| created_at / updated_at | DateTime(tz) | 常规时间字段 |

### 4.2 数据目录

- `data/video/tasks/{task_id}/`：存参考图本地副本 + 产出视频 `output.mp4`。
- 删除任务时连目录一起删除。

### 4.3 建表 / 迁移

- 走 `app/models/database.py` 现有 inline migration 模式（`migrate_*` 函数检查列存在后 `ALTER TABLE`，无 Alembic）。
- `app/main.py` lifespan 中确保 `data/video/tasks/` 目录创建（沿用 directory 初始化模式）。

## 5. 任务状态机

```
draft            导入图片后，编排 Prompt 中（历史列表可见、可编辑、可删除）
  → pending      已提交生成，排队
  → uploading    上传参考图到 TOS
  → generating   Seedance 轮询中
  → downloading  下载产出视频落盘
  → completed    完成（不可重跑；再来一版需重新导入建新任务）
  → failed       任一环节失败，记录 error_message，可重新提交（回到 pending 重跑）
```

- 导入即建 `draft` 记录，Prompt 编排挂在任务上。
- `completed` 任务不可重跑，保留每次产出的完整历史。
- **应用重启恢复**：沿用 `app/services/startup_image_tasks.py` 模式，启动时把 in-flight（uploading / generating / downloading）的视频任务标记为 `failed`（可重新提交），避免僵尸任务。

## 6. API 设计

前缀 `/api/video`，统一 `ApiResponse(success, data, message)` 包装。

| 端点 | 作用 |
|---|---|
| `POST /tasks/import` | 建草稿。multipart 上传本地图，或 JSON 传 `source_kind=quick_create + source_task_id + source_image_path + ref_prompt_text`。图片复制到 `data/video/tasks/{id}/`，返回任务信息 + 按图片宽高比推荐的 ratio |
| `POST /tasks/{id}/prompt-job/start` | 启动 LLM Prompt 作业，body `{mode: "recommend" \| "optimize", manual_prompt?}`。模式 A/B 共用一个作业槽（每任务同时只跑一个），走 BackgroundTasks |
| `GET /tasks/{id}/prompt-job/status` | 轮询 LLM 作业，完成时带回生成的 Prompt 文本 |
| `POST /tasks/{id}/submit` | 提交生成。body：最终 Prompt、image_role、duration、generate_audio、ratio。串行校验：存在 in-flight 视频任务时返回 409 |
| `GET /tasks/{id}/status` | 轮询任务状态（路径加入 `_SuppressPollAccessLog`） |
| `GET /tasks` | 历史列表 |
| `GET /tasks/{id}/video` | `FileResponse` 输出视频（支持 Range，`<video>` 可拖进度条） |
| `GET /tasks/{id}/image` | 参考图 / 缩略图（复用 `get_or_create_thumbnail`） |
| `DELETE /tasks/{id}` | 删记录 + 删目录；运行中拒绝 |

## 7. 后台 Runner 流程

`app/services/video_service/runner.py`，使用 `BackgroundSessionLocal`（NullPool）：

1. `uploading`：`TosStorageClient.upload_and_presign(ref_image_path)` → 预签名 URL。
2. `generating`：`seedance.py` 提交 Ark 任务（模型 `doubao-seedance-2-0-260128`）：
   - `image_role=first_frame` → `image_url` 项不带 `role`（作为视频首帧）。
   - `image_role=reference_image` → `image_url` 项带 `role: "reference_image"`。
   - 参数：`generate_audio`、`ratio`、`duration`。
   - 30 秒间隔轮询 `tasks.get(task_id)`，总超时约 20 分钟。`succeeded` / `failed` 终止。
3. `downloading`：流式下载 `content.video_url` 到 `data/video/tasks/{id}/output.mp4`。
4. **finally（无论成败）**：删除 TOS 上的图片对象（`TosStorageClient.delete(object_key)`）。
5. 置 `completed` / `failed`（失败记录 Ark 返回的 `error`）。

### 7.1 Ratio 策略

`seedance.py` 维护模型支持的比例常量表（实现时以火山引擎官方文档为准核对）。导入时按参考图宽高比选最近的支持比例作为默认，前端可改。

## 8. LLM Prompt 编排

`app/prompts/video/`，两份模板，均内置 §1.1 视频内容纲领（两大核心主题、4–15 秒、高审美镜头感、四个推荐方向、negative 清单）：

- `recommend`（模式 A）：多模态输入参考图（`yibu_gemini_infer` 的 `image_path`）+ 可选生图 Prompt，产出一套推荐的视频 Prompt。
- `optimize`（模式 B）：保留用户手写 Prompt 的意图与要素，按同一纲领润色镜头语言与动态描述。

Prompt 作业由 `prompt_service.py` 编排，走 BackgroundTasks，结果写入 `prompt_job_*` 字段，前端轮询取回后填入编辑器。

## 9. 前端交互

### 9.1 产线卡片跳转

- `page/src/pages/home/components/BatchTaskCard.tsx` 每张产出图操作区增加「去创作视频」按钮。
- 点击直接调 `POST /tasks/import`（JSON 带 source 溯源 + 该图所在组的完整 Prompt），成功后 `navigate("/video?task={id}")`。不经 URL 传大段 Prompt 文本，页面刷新不丢。

### 9.2 视频创作页三区布局

1. **参考图区**：本地上传（拖拽 / 点选）或显示已导入的图；展示推荐 ratio。
2. **Prompt 工作台**：模式 A「AI 推荐」按钮（可重新生成）/ 模式 B 手动输入 +「AI 优化」按钮；结果统一进同一个可编辑文本框；LLM 作业进行中显示轮询状态。
3. **参数与提交**：image_role 切换（默认首帧）、时长滑杆 4–15s（默认 8）、音频开关（默认关）、ratio 下拉；提交后就地显示状态进度（uploading → generating → downloading），完成后内嵌 `<video>` 播放 + 下载按钮。

### 9.3 历史列表

- 页面下方网格卡片，封面用参考图缩略图，状态徽标（草稿 / 生成中 / 完成 / 失败）。
- 点开播放、下载、删除；草稿点开回到编辑态；失败任务可重新提交。

## 10. 错误处理

- 导入校验：仅接受图片类型，大小上限沿用素材模块上传限制。
- 提交 409（已有任务在跑）→ 前端 toast 明确提示串行约束。
- Runner 各环节失败均落 `failed + error_message`；TOS 清理放 finally 保证不残留。
- 应用重启把 in-flight 任务标记 `failed`（见 §5）。

## 11. 测试

- **pytest**：
  - repository CRUD。
  - service 状态机流转（mock Seedance 客户端 + mock TOS）。
  - 路由层：导入校验、串行 409、运行中禁删。
  - runner 单测：fake 客户端走通全链路（含 finally 清理）。
- **前端**：`npm run type-check` + `npm run lint`（项目无前端测试框架，维持现状）。
- **人工验收**：真实跑通一次「产线图导入 → AI 推荐 Prompt → 生成 → 播放下载」全链路。

## 12. 不做（YAGNI）

- 不做并行多视频任务。
- 不做多候选 Prompt（模式 A 单候选可重生成）。
- 不在 UI 暴露分辨率选项。
- 不做视频编辑 / 拼接 / 二次处理。
- 不做批量视频产线。
