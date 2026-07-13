# 灵感产线批量删除功能设计

日期：2026-07-13
状态：已与用户确认设计，待实现

## 背景

首页"灵感产线"（批量创作，`creation_batch_run_items`）产量大，每天有大量已使用或低质量的产线记录需要删除。现状只能逐条点开卡片手工删除，效率低。本设计为列表页增加"批量管理"模式，支持勾选多条产线记录一次性删除。

用户已确认的三个关键决策：

1. **选择方式**：进入批量模式后逐卡勾选，配"全选/取消全选"快捷操作（不做条件式删除、不做"全选失败"等状态筛选按钮）。
2. **运行中保护**：`running` / `pending` 状态的产线记录禁选，前后端双重校验（现有单删无此保护，批量删除必须有）。
3. **feedback 保护**：确认弹窗显示本次连带删除的人工 feedback 总数，M > 0 时醒目提示"建议先导出 Feedback JSON"，但不强制阻断。

## 现状要点（调研结论）

- 一条产线记录 = `CreationBatchRunItem`（`app/models/creation_batch.py`）。状态枚举：`pending` / `running` / `completed` / `failed`。
- 现有单删链路完整：`DELETE /api/creation/batch-automation/items/{item_id}`（`app/routes/creation.py:522`）→ `BatchAutomationService.delete_batch_item`（`app/services/creation_service/batch_automation_service.py:534`）→ 级联清理一键创作任务（含 beautify 产物、feedback 行、work_dir）+ Prompt 预生成任务（含 work_dir）+ 删除 item 行。悬空引用用 try/except 容忍。
- hydrated 列表接口（`GET /batch-automation/items-hydrated`）已按条内联 `feedbacks` 数组，前端 `buildBatchTaskFromHydrated`（`page/src/utils/batchAutomationDisplay.ts:172`）已将 feedback 映射进 `task.images[].userFeedback`。**因此弹窗的 feedback 计数纯前端计算，无需后端改动。**
- 后端唯一新增：批量删除端点。

## 设计

### 1. 前端交互（`BatchCreationPage.tsx` + `BatchTaskCard.tsx`）

- 列表头"N 条产线记录"旁新增 **"批量管理"** 按钮；点击进入批量模式（按钮变"退出批量"）。
- 批量模式工具栏：**已选 N 条 | 全选 | 取消全选 | 删除所选（红色，0 选中禁用）**。
  - "全选"只勾选可删项（跳过 `running` / `pending`）。
- 卡片在批量模式下：
  - 左上角显示复选框；`running` / `pending` 卡片复选框置灰禁用，提示"进行中的产线不可删除"。
  - 点击卡片主体 = 切换勾选；禁用卡片展开，避免误触。
- 选中状态用 `Set<string>`（item id）管理，参照 `CharaProfilePage.tsx` FanartSelector 与本页角色选择区的既有多选范式。
- **确认弹窗**（沿用单删弹窗视觉风格与固定文案——连带删除 Prompt 记录、美图记录）：
  - 显示"将删除 N 条产线记录"；
  - 显示"其中连带删除 M 条人工 feedback"，M = 选中项 `images` 中带 `userFeedback` 的图片数量之和；M > 0 时用醒目警示样式提示"建议先导出 Feedback JSON"。
- 删除中：确认按钮 loading、防重复提交。
- 完成后：toast 显示"成功删除 N 条（跳过 X 条进行中，失败 Y 条）"，刷新列表（`loadTasksFromApi()`），退出批量模式。

### 2. 后端 API

**端点**：`POST /api/creation/batch-automation/items/batch-delete`

- 用 POST 而非 DELETE：DELETE 带 body 兼容性差；项目已有 POST + `List[str]` 请求体先例（`app/schemas/material.py` 的 `selected_*_ids`）。
- 请求 schema（`app/schemas/creation.py`）：

```python
class BatchAutomationBatchDeleteRequest(BaseModel):
    item_ids: List[str]  # 1..200 条，后端去重、去空白
```

- 路由（`app/routes/creation.py`）：去重、去空白后若列表为空则返回 400；超过 200 条返回 422；否则调 service，恒返回 200 + `ApiResponse`，部分失败通过 data 表达。

**Service**：`BatchAutomationService.batch_delete_items(item_ids: List[str]) -> Dict`

逐条处理，互不阻断：

| 情况 | 归类 |
|---|---|
| item 查不到 | `not_found`（不报错，可能已被删） |
| `status` 为 `running` / `pending` | `skipped_running`（后端强制校验，不只靠前端禁选） |
| 删除成功（复用现有 `delete_batch_item`） | `deleted` |
| 删除抛异常 | `failed`（`{id, error}`），`logger.exception` 记录后继续 |

返回：

```json
{
  "deleted": ["id1", ...],
  "skipped_running": ["id2", ...],
  "not_found": ["id3", ...],
  "failed": [{"id": "id4", "error": "..."}]
}
```

- 清理逻辑零重复：全部经由现有 `delete_batch_item` → `QuickCreateService.delete_history` / `PromptPrecreationService.delete_history` 链路（work_dir、beautify 产物、feedback 行）。
- 每条删除独立提交（沿用现有 repo 逐条 commit 行为）；中途失败不回滚已删条目。

**前端 API**（`page/src/services/creationApi.ts`）：新增 `batchDeleteBatchAutomationItems(itemIds: string[])`，返回上述结果结构。

### 3. 错误处理

- 整个请求失败（网络 / 500）：前端弹错误提示并刷新列表（可能已删除一部分）。
- 单条失败：后端记日志，继续处理后续条目；结果计入 `failed` 返回前端展示。

### 4. 测试

- pytest 覆盖 service 编排逻辑：
  - 多条 `completed` / `failed` 正常删除；
  - `running` / `pending` 被跳过（归入 `skipped_running`，item 行未删）；
  - 不存在的 id 归入 `not_found`；
  - 部分失败：monkeypatch 使某条 `delete_batch_item` 抛异常，验证其余条目照常删除、失败条目进 `failed`。
- 级联清理（work_dir / beautify / feedback 行）由现有单删链路及其测试保障，批量测试聚焦编排逻辑。
- 前端过 `npm run type-check` + `npm run lint`。

## 不做的事（YAGNI）

- 不做条件式删除（按状态 / 日期）。
- 不做"全选失败""全选无 feedback"等状态快捷筛选按钮。
- 不做强制"先导出 feedback 才能删"的阻断。
- 不做软删除 / 回收站。
