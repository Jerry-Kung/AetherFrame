# 生产工作流人工 Feedback 入口 + 一键结构化导出 — 设计文档

日期：2026-07-08
状态：已批准（用户确认方案 A + 四节设计定稿）
背景：Phase 2 实验暂停，用户将在生产环境跑批检验优化成果。依据
[feedback-case-data-first] 原则，生产真实出图 + 人工 feedback 是后续优化的核心
依据，需要在首页工作流页面（灵感工坊产线记录）提供逐图 feedback 填写入口，并
支持一键导出结构化结果，供 Claude 统一读取归档为正式实验 Case
（`experiments/cases/`，格式见 `experiments/casebank/case_format.py`）。

## 需求（用户已确认）

1. 首页灵感工坊的每条产线记录中，**每张图片**可填写人工 feedback。
2. 表单结构：**自由文本 + 「腿脚崩坏」勾选**（勾选数对应 Case 的 `bad` 计数）。
3. 导出为**浏览器下载 JSON**（与盲评页「导出评分 JSON」同模式），用户把文件交给
   Claude 归档。
4. 导出按钮**一键式、无状态、每次全量导出**所有已填 feedback；重复归档由 Claude
   按 Case ID 去重。
5. 持久化选**方案 A：后端 SQLite 新表**（feedback 是长期数据资产，不放
   localStorage / result_json）。

## 1. 数据模型（后端）

新表 `creation_image_feedbacks`，一行 = 一张图的 feedback：

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | String PK | uuid |
| `quick_create_task_id` | String(64)，索引 | 指向 `creation_quick_create_tasks.id` |
| `prompt_id` | String(128) | 与前端图片 ID 构成（`taskId-promptId-index`）对应 |
| `image_index` | Integer | 组内图片序号（0 起） |
| `leg_foot_bad` | Boolean，默认 False | 腿脚崩坏勾选 |
| `feedback_text` | Text，默认 "" | 自由文本 |
| `created_at` / `updated_at` | DateTime | 常规时间戳 |

- 唯一约束 `(quick_create_task_id, prompt_id, image_index)`；保存即 upsert。
- **清空即删**：文本为空且未勾选时删除该行——表里只存「已填」记录，导出无需再过滤。
- 新表由 `app/models/database.py` 现有 `create_all` 启动逻辑自动创建，无需手写迁移。
- feedback 锚定在 quick create 任务而非 batch item：图片本体属于 quick create
  记录，将来非产线入口（快速创作页）也能复用同一张表。
- **删除联动**：删除产线记录会同步删除 quick create 记录及其 feedback（服务层
  显式删除，不依赖 SQLite FK PRAGMA）。前端删除确认弹窗文案补一句提醒：
  想保留 feedback 的先导出再删。

## 2. API（`/api/creation` 前缀，ApiResponse 包装）

### 2.1 保存（upsert）

`PUT /quick-create/tasks/{task_id}/feedback/{prompt_id}/{image_index}`

- body：`{ "feedback_text": str, "leg_foot_bad": bool }`
- task 不存在 → 404；`image_index < 0` → 422。
- 文本空且未勾选 → 删除已有行（幂等，行不存在也返回成功）。
- 返回保存后的行（或 `null` 表示已清除）。

### 2.2 回显（扩展现有接口）

`GET /batch-automation/items-hydrated` 响应中每个 item 增加：

```json
"feedbacks": [ { "prompt_id": "...", "image_index": 0,
                 "leg_foot_bad": true, "feedback_text": "..." } ]
```

一次批量查询（按 item 的 `quick_create_task_id` 集合 IN 查询），不引入 N+1。

### 2.3 全量导出

`GET /feedback/export`

聚合所有已填 feedback，按 quick create 任务组织；有对应 batch item 的 join 出
seed/角色信息（无 batch item 的 quick create 任务也导出：`seed_prompt_text` 取任务
自身的 `seed_prompt` 列，`batch_item_id`、`seed_prompt_id`、`seed_section` 为 null）。
响应 data：

```json
{
  "schema": "aetherframe_feedback_v1",
  "exported_at": "2026-07-08T12:00:00+08:00",
  "records": [
    {
      "batch_item_id": "...",
      "quick_create_task_id": "...",
      "character_id": "...",
      "character_name": "...",
      "seed_prompt_id": "...",
      "seed_section": "...",
      "seed_prompt_text": "...",
      "created_at": "...",
      "prompt_groups": [
        {
          "prompt_id": "...",
          "prompt_index": 0,
          "prompt_title": "...",
          "full_prompt": "...",
          "total_images": 3,
          "images": [
            { "image_index": 0, "image_path": "...",
              "leg_foot_bad": true, "feedback_text": "..." }
          ]
        }
      ]
    }
  ]
}
```

- `prompt_groups` 只含有已填 feedback 的组；`images` 只含已填的图；
  `total_images` 是该组实际出图总数（供 Case 的 `images` 计数）。
- `full_prompt` 取 quick create 任务 `selected_prompts_json` 中该 prompt 的全文；
  `prompt_title` 取预生成 Prompt 卡片标题（取不到时回落 prompt_id）。
- 无已填记录 → `records: []`（HTTP 200，前端提示而非报错）。

## 3. 前端 UI（首页灵感工坊）

### 3.1 逐图填写入口（`BatchTaskCard` 展开区图片网格）

- 每张图**左下角**加 feedback 按钮（右下角已有「AI 评论」按钮，互不遮挡）。
- 状态样式：未填 = 灰白底描边小按钮；已填 = 玫瑰渐变高亮（与「AI 评论」同系）。
- 点击弹出 `ImageFeedbackModal`（新组件，放 `page/src/pages/home/components/`）：
  - 文本框（自由文本，可空）+「腿脚崩坏」勾选 + 保存 / 取消；
  - 已填时预填现值；文本清空且取消勾选后保存 = 清除该图 feedback；
  - 保存失败在弹窗内展示错误信息，不关闭弹窗、不丢已填内容；
  - 视觉沿用现有玫瑰系弹窗（参照删除/标记确认弹窗）。
- feedback 数据随 `items-hydrated` 一次拉回，挂到 `BatchTask` 类型
  （`feedbacks` 字段），保存成功后就地 patch 本地 state，不整页刷新。

### 3.2 一键导出按钮（`BatchCreationPage`「产线产出」标题行右侧）

- 按钮文案「导出 Feedback JSON」；点击调 `GET /feedback/export`，前端将 data
  以 Blob 触发下载，文件名 `feedback_export_YYYYMMDD-HHmm.json`。
- 成功后提示导出的记录数；`records` 为空时提示「还没有已填写的 feedback」。
- 导出期间按钮禁用防重复点击。

### 3.3 删除确认文案

产线记录删除确认弹窗提示语追加：已填写的 feedback 会一并删除，需要保留请先导出。

## 4. Case 映射约定（Claude 归档时执行，写入本 spec 作为口径）

- 一个 Case = 一条产线记录 × 一个 Prompt 组：
  - `case_id`：`Case_prod_{YYYYMMDD}_{qc_hex8}_{prompt_index}`——`qc_hex8` 取
    `quick_create_task_id` 去掉 `qcreate_` 前缀后的前 8 位十六进制；
    `prompt_index` 取导出组的 `prompt_index` 字段（result_json 生成顺序位，
    稳定不随填写顺序变化；为 -1 时回落 `prompt_id` 前 8 位）；
  - `seed_prompt` = `seed_prompt_text` 原文；`final_prompt` = 该组 `full_prompt`；
  - `images` = `total_images`；`bad` = 组内 `leg_foot_bad=true` 的数量；
  - `feed_back` = 逐图「图{image_index+1}: {feedback_text}」按序拼接
    （仅勾选无文本的图记「图N: 腿脚崩坏」）；
  - meta：`source=production_feedback`、`variant=production`、
    `difficulty=unknown`、`date` 取导出文件 `exported_at` 日期；
  - `tags` 归档时由 Claude 按 feedback 原文以当时 taxonomy 版本补填，
    经用户抽查（同 manual_0706 首次补填口径）。
- 去重：Case ID 由稳定字段派生，全量重复导出在归档时按 Case ID 跳过已有 Case。
- **工作流约定**：对给了 feedback 的 Prompt 组，建议把组内每张图都过目；
  未填文本且未勾选的图视为「无问题」——否则 `bad` 会低估。

## 5. 错误处理

- 保存：task 不存在 404；参数不合法 422；其余 500 走 ApiResponse 统一错误。
- 导出：空数据是正常路径（`records: []`）；聚合中单条记录关联数据缺失
  （如 quick create 任务已删）时跳过该条并继续，不让一条坏数据阻断全量导出。
- 前端：保存失败弹窗内报错不丢输入；导出失败在产出区提示错误文案。

## 6. 测试

- 后端 pytest（沿用 `tests/` 现有模式）：
  - repo/service：upsert 幂等、清空即删、`(task, prompt, index)` 唯一性、
    导出聚合（含 batch item join、无 batch item 回落、只含已填、
    `total_images` 计数、坏数据跳过）；
  - 路由：保存/清除/404/422、items-hydrated 带 feedbacks、export 空与非空。
- 前端：`npm run type-check` + `npm run lint` 通过（项目无前端测试设施，不新增）。

## 7. 明确不做（YAGNI）

- 不做三组三档评分（盲评专用，生产入口只要 文本 + 腿脚勾选）；
- 不做增量导出/已导出状态；
- 不做服务器端落盘副本；
- 不在快速创作页/灯箱内加入口（本期只做首页产线记录网格）；
- 不做后端直接生成 Case txt（归档由 Claude 读 JSON 执行，保留人工 tags 复核环节）。

## 修订记录

2026-07-08 终审修订：case_id 派生改用 qc id 十六进制段 + 导出新增 prompt_groups[].prompt_index（原「task_id 前 8 位」恒为 qcreate_ 前缀、promptIdx 不稳定，会破坏归档去重）。
