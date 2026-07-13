# 灵感产线批量删除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 首页灵感产线列表增加"批量管理"模式，勾选多条产线记录一次性删除（含级联清理），运行中记录禁选，确认弹窗显示连带删除的人工 feedback 数。

**Architecture:** 后端新增 `POST /api/creation/batch-automation/items/batch-delete` 端点，service 层 `batch_delete_items` 逐条复用现有 `delete_batch_item`（级联清理零重复），跳过 `running`/`pending`。前端在 `BatchCreationPage` 增加批量模式状态与工具栏，`BatchTaskCard` 增加复选框 props；feedback 计数纯前端计算（hydrated 列表已内联 feedbacks 数据）。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2（后端）；React 19 + TypeScript + Tailwind（前端）；pytest。

**Spec:** `docs/superpowers/specs/2026-07-13-batch-delete-pipeline-design.md`

## Global Constraints

- API 响应一律包 `ApiResponse(success, data, message)`；creation 路由前缀 `/api/creation`。
- 批量删除端点恒返回 200，部分失败通过 `data` 表达；请求去重去空后为空返回 400，超 200 条返回 422（Pydantic `max_length`）。
- `running` / `pending` 状态的产线记录不可删除：前端禁选 + 后端强制跳过（归入 `skipped_running`）。
- 前端 React hooks 必须显式 import（`import { useState } from "react"`）——`npm run type-check` 不认 auto-imports。
- 前端样式沿用页面既有 inline style + Tailwind 混合风格（rose/pink 色系、`'ZCOOL KuaiLe'` 字体）。
- 测试命令：后端 `python -m pytest <file> -v`；前端 `cd page` 后 `npm run type-check` 与 `npm run lint`。
- 每个 Task 完成后单独 commit。

---

### Task 1: 后端 service `batch_delete_items`（TDD）

**Files:**
- Modify: `app/services/creation_service/batch_automation_service.py`（在 `delete_batch_item` 之后、类 `BatchAutomationService` 末尾新增方法，约 552 行处）
- Test: `tests/test_batch_automation.py`（文件末尾新增测试类）

**Interfaces:**
- Consumes: 现有 `BatchAutomationService.delete_batch_item(item_id: str) -> Dict[str, Any]`（`batch_automation_service.py:534`）、`CreationBatchRepository.get_item(item_id) -> Optional[CreationBatchRunItem]`。
- Produces: `BatchAutomationService.batch_delete_items(item_ids: List[str]) -> Dict[str, Any]`，返回 `{"deleted": List[str], "skipped_running": List[str], "not_found": List[str], "failed": List[{"id": str, "error": str}]}`。Task 2 的路由调用它。

- [ ] **Step 1: 写失败的测试**

在 `tests/test_batch_automation.py` 文件末尾追加（复用文件顶部已有的 import，无需新增 import）：

```python
class TestBatchAutomationBatchDelete:
    @staticmethod
    def _make_item(db_session, *, status="completed"):
        char = MaterialCharacterRepository(db_session).create(
            {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "batch-bulk-char"}
        )
        batch_repo = CreationBatchRepository(db_session)
        run = batch_repo.create_run(iterations_total=1, config_json="{}", status="completed")
        item = batch_repo.create_item(
            run_id=run.id,
            step_index=0,
            character_id=char.id,
            seed_prompt_id="s1",
            seed_section="general",
            seed_prompt_text="seed",
            status=status,
        )
        return batch_repo, item

    def test_batch_delete_mixed_statuses(self, db_session):
        """completed/failed 删除；running/pending 跳过；不存在的归入 not_found。"""
        batch_repo, done1 = self._make_item(db_session)
        _, done2 = self._make_item(db_session, status="failed")
        _, running = self._make_item(db_session, status="running")
        _, pending = self._make_item(db_session, status="pending")

        data = BatchAutomationService(db_session).batch_delete_items(
            [done1.id, done2.id, running.id, pending.id, "bb_item_missing0000"]
        )

        assert sorted(data["deleted"]) == sorted([done1.id, done2.id])
        assert sorted(data["skipped_running"]) == sorted([running.id, pending.id])
        assert data["not_found"] == ["bb_item_missing0000"]
        assert data["failed"] == []
        assert batch_repo.get_item(done1.id) is None
        assert batch_repo.get_item(done2.id) is None
        assert batch_repo.get_item(running.id) is not None
        assert batch_repo.get_item(pending.id) is not None

    def test_batch_delete_partial_failure_does_not_block_rest(self, db_session, monkeypatch):
        """某条删除抛异常时：该条进 failed，其余条目照常删除。"""
        batch_repo, ok = self._make_item(db_session)
        _, bad = self._make_item(db_session)

        original = BatchAutomationService.delete_batch_item

        def flaky(self, item_id):
            if item_id == bad.id:
                raise RuntimeError("boom")
            return original(self, item_id)

        monkeypatch.setattr(BatchAutomationService, "delete_batch_item", flaky)

        data = BatchAutomationService(db_session).batch_delete_items([ok.id, bad.id])

        assert data["deleted"] == [ok.id]
        assert data["skipped_running"] == []
        assert data["not_found"] == []
        assert [f["id"] for f in data["failed"]] == [bad.id]
        assert batch_repo.get_item(ok.id) is None
        assert batch_repo.get_item(bad.id) is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_batch_automation.py::TestBatchAutomationBatchDelete -v`
Expected: 2 个测试 FAIL，报 `AttributeError: 'BatchAutomationService' object has no attribute 'batch_delete_items'`

- [ ] **Step 3: 写最小实现**

在 `app/services/creation_service/batch_automation_service.py` 中 `delete_batch_item` 方法（约 552 行 `return {"deleted_id": item_id}` 之后、类结束处）追加方法。文件顶部已 import `Dict`/`Any`/`List` 与 `logger`，无需新增 import：

```python
    def batch_delete_items(self, item_ids: List[str]) -> Dict[str, Any]:
        """批量删除产线记录：逐条复用 delete_batch_item，互不阻断。

        running/pending 的条目后台任务仍在写入，强制跳过（不只靠前端禁选）。
        """
        deleted: List[str] = []
        skipped_running: List[str] = []
        not_found: List[str] = []
        failed: List[Dict[str, str]] = []
        for iid in item_ids:
            item = self.batch_repo.get_item(iid)
            if not item:
                not_found.append(iid)
                continue
            if item.status in ("running", "pending"):
                skipped_running.append(iid)
                continue
            try:
                self.delete_batch_item(iid)
                deleted.append(iid)
            except Exception as e:
                logger.exception("批量删除产线记录失败 item_id=%s", iid)
                failed.append({"id": iid, "error": str(e) or e.__class__.__name__})
        return {
            "deleted": deleted,
            "skipped_running": skipped_running,
            "not_found": not_found,
            "failed": failed,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_batch_automation.py -v`
Expected: 全部 PASS（含既有的 Plan / DeleteItem 测试，确认无回归）

- [ ] **Step 5: Commit**

```bash
git add tests/test_batch_automation.py app/services/creation_service/batch_automation_service.py
git commit -m "feat(creation): 批量删除产线记录 service（跳过运行中，部分失败不阻断）"
```

---

### Task 2: 后端 schema + 路由 + 路由测试

**Files:**
- Modify: `app/schemas/creation.py`（在 `BatchAutomationItemListResponse`（292-294 行）之后新增 schema）
- Modify: `app/routes/creation.py`（imports + 在 `batch_automation_delete_item` 路由（522-537 行）之后新增路由）
- Test: `tests/routes/test_batch_automation_batch_delete.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `BatchAutomationService.batch_delete_items(item_ids: List[str]) -> Dict[str, Any]`；现有 `get_batch_automation_service` Depends、`ApiResponse` schema。
- Produces: `POST /api/creation/batch-automation/items/batch-delete`，请求体 `{"item_ids": ["..."]}`（1–200 条），响应 `ApiResponse`，`data` 为 Task 1 的返回结构。Task 3 的前端 API 调用它。

- [ ] **Step 1: 写失败的路由测试**

新建 `tests/routes/test_batch_automation_batch_delete.py`：

```python
"""批量删除产线记录路由：请求校验与结果分类"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.repositories.creation_batch_repository import CreationBatchRepository
from app.repositories.material_repository import MaterialCharacterRepository

URL = "/api/creation/batch-automation/items/batch-delete"


@pytest.fixture
def api_client(db_session):
    from app.main import app
    from app.models.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _make_item(db_session, status="completed"):
    char = MaterialCharacterRepository(db_session).create(
        {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "route-bulk-char"}
    )
    batch_repo = CreationBatchRepository(db_session)
    run = batch_repo.create_run(iterations_total=1, config_json="{}", status="completed")
    return batch_repo.create_item(
        run_id=run.id,
        step_index=0,
        character_id=char.id,
        seed_prompt_id="s1",
        seed_section="general",
        seed_prompt_text="seed",
        status=status,
    )


def test_batch_delete_dedups_and_classifies(api_client, db_session):
    """去重去空白；completed 删除、running 跳过、不存在归 not_found；恒 200。"""
    done = _make_item(db_session)
    running = _make_item(db_session, status="running")

    r = api_client.post(
        URL,
        json={"item_ids": [done.id, f"  {done.id}  ", "", running.id, "bb_item_gone0000"]},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["deleted"] == [done.id]
    assert data["skipped_running"] == [running.id]
    assert data["not_found"] == ["bb_item_gone0000"]
    assert data["failed"] == []


def test_batch_delete_empty_after_clean_returns_400(api_client):
    r = api_client.post(URL, json={"item_ids": ["   ", ""]})
    assert r.status_code == 400


def test_batch_delete_empty_list_returns_422(api_client):
    r = api_client.post(URL, json={"item_ids": []})
    assert r.status_code == 422


def test_batch_delete_over_200_returns_422(api_client):
    r = api_client.post(URL, json={"item_ids": [f"id_{i}" for i in range(201)]})
    assert r.status_code == 422
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/routes/test_batch_automation_batch_delete.py -v`
Expected: FAIL，`assert r.status_code == 200` 处收到 404 / 405（路由不存在）

- [ ] **Step 3: 新增 schema**

在 `app/schemas/creation.py` 的 `BatchAutomationItemListResponse` 类（292-294 行）之后追加（文件已 import `Field`、`List`）：

```python
class BatchAutomationBatchDeleteRequest(BaseModel):
    """批量删除产线记录"""

    item_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="要删除的产线记录 ID 列表（去重去空白后为空则 400）",
    )
```

- [ ] **Step 4: 新增路由**

`app/routes/creation.py` 两处修改：

1. 第 6 行 `from typing import Optional` 改为 `from typing import List, Optional`；schema import 块（15-37 行）中 `BatchAutomationItemListResponse,` 之后加一行 `BatchAutomationBatchDeleteRequest,`（保持字母序邻近即可）。

2. 在 `batch_automation_delete_item` 路由（537 行 `return ApiResponse(...)` 之后）追加：

```python
@router.post(
    "/batch-automation/items/batch-delete",
    response_model=ApiResponse,
)
def batch_automation_batch_delete_items(
    body: BatchAutomationBatchDeleteRequest,
    service: BatchAutomationService = Depends(get_batch_automation_service),
):
    """批量删除产线记录。恒 200，部分失败通过 data 表达。"""
    ids: List[str] = []
    seen: set[str] = set()
    for raw in body.item_ids:
        iid = (raw or "").strip()
        if iid and iid not in seen:
            seen.add(iid)
            ids.append(iid)
    if not ids:
        raise HTTPException(status_code=400, detail="item_ids 无效")
    data = service.batch_delete_items(ids)
    return ApiResponse(success=True, data=data, message="批量删除产线记录完成")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/routes/test_batch_automation_batch_delete.py tests/test_batch_automation.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add app/schemas/creation.py app/routes/creation.py tests/routes/test_batch_automation_batch_delete.py
git commit -m "feat(creation): 批量删除产线记录端点 POST /batch-automation/items/batch-delete"
```

---

### Task 3: 前端 API 客户端 + BatchTaskCard 批量模式 props

**Files:**
- Modify: `page/src/services/creationApi.ts`（在 `deleteBatchAutomationItem`（589-601 行）之后新增）
- Modify: `page/src/pages/home/components/BatchTaskCard.tsx`

**Interfaces:**
- Consumes: Task 2 的端点；`creationApi.ts` 既有的 `API_BASE` / `fetchWithTimeout` / `parseJson` / `throwIfError` / `rethrow` / `ApiError`。
- Produces:
  - `batchDeleteBatchAutomationItems(itemIds: string[]): Promise<BatchDeleteItemsResult>`，其中 `BatchDeleteItemsResult = { deleted: string[]; skipped_running: string[]; not_found: string[]; failed: { id: string; error: string }[] }`（Task 4 调用）。
  - `BatchTaskCard` 新增可选 props：`batchMode?: boolean; selected?: boolean; selectable?: boolean; onToggleSelect?: (taskId: string) => void`（Task 4 传入；不传时行为与现状完全一致）。

- [ ] **Step 1: 新增前端 API 函数**

在 `page/src/services/creationApi.ts` 的 `deleteBatchAutomationItem` 函数之后（601 行 `}` 后）追加：

```typescript
export interface BatchDeleteItemsResult {
  deleted: string[];
  skipped_running: string[];
  not_found: string[];
  failed: { id: string; error: string }[];
}

export async function batchDeleteBatchAutomationItems(
  itemIds: string[]
): Promise<BatchDeleteItemsResult> {
  const ids = itemIds.map((x) => String(x ?? "").trim()).filter(Boolean);
  if (ids.length === 0) throw new ApiError("未选择要删除的产线记录", 400);
  const url = `${API_BASE}/batch-automation/items/batch-delete`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_ids: ids }),
    });
    const data = await parseJson<BatchDeleteItemsResult>(response);
    throwIfError(response, data);
    return data.data as BatchDeleteItemsResult;
  } catch (e) {
    rethrow(e);
  }
}
```

- [ ] **Step 2: BatchTaskCard 增加批量模式 props**

`page/src/pages/home/components/BatchTaskCard.tsx` 五处修改：

1. Props 接口（16-27 行）追加四个可选字段：

```typescript
interface BatchTaskCardProps {
  task: BatchTask;
  index: number;
  batchMode?: boolean;
  selected?: boolean;
  selectable?: boolean;
  onToggleSelect?: (taskId: string) => void;
  onDelete: (taskId: string) => void | Promise<void>;
  onMarkUsed: (taskId: string) => void | Promise<void>;
  onSaveFeedback: (
    taskId: string,
    image: QuickCreateImage,
    feedbackText: string,
    selectedTags: SelectedFeedbackTag[]
  ) => Promise<void>;
}
```

2. 组件签名（43 行）解构新 props：

```typescript
export default memo(function BatchTaskCard({
  task,
  index,
  batchMode = false,
  selected = false,
  selectable = true,
  onToggleSelect,
  onDelete,
  onMarkUsed,
  onSaveFeedback,
}: BatchTaskCardProps) {
```

3. 外层容器（105-111 行）选中态高亮：

```tsx
    <div
      className="rounded-2xl overflow-hidden transition-all duration-300"
      style={{
        background: batchMode && selected ? "rgba(255,241,246,0.9)" : "rgba(255,255,255,0.7)",
        border:
          batchMode && selected
            ? "1.5px solid rgba(244,114,182,0.55)"
            : "1px solid rgba(253,164,175,0.2)",
      }}
    >
```

4. 头部行（112-116 行）：批量模式下点击 = 切换勾选（禁用展开），不可选时 cursor 置为 not-allowed：

```tsx
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{
          borderBottom: expanded && !batchMode ? "1px solid rgba(253,164,175,0.15)" : "none",
          cursor: batchMode && !selectable ? "not-allowed" : "pointer",
        }}
        onClick={() => {
          if (batchMode) {
            if (selectable) onToggleSelect?.(task.id);
            return;
          }
          setExpanded((v) => !v);
        }}
      >
```

并在头部行内第一个子元素（编号圆块 `{index + 1}` 那个 div）之前插入复选框：

```tsx
          {batchMode && (
            <div
              className="w-5 h-5 flex items-center justify-center shrink-0"
              title={selectable ? undefined : "进行中的产线不可删除"}
            >
              <i
                className={
                  selected && selectable
                    ? "ri-checkbox-circle-fill text-base"
                    : "ri-checkbox-blank-circle-line text-base"
                }
                style={{
                  color: !selectable
                    ? "rgba(190,18,60,0.25)"
                    : selected
                      ? "#f472b6"
                      : "rgba(244,114,182,0.5)",
                }}
              ></i>
            </div>
          )}
```

注意：复选框要插在 `<div className="flex items-center gap-3 min-w-0">`（117 行）内部最前面。

5. 展开区与箭头在批量模式下隐藏：
   - 233 行 `{expanded && (` 改为 `{expanded && !batchMode && (`；
   - 193-198 行的箭头容器整体包一层 `{!batchMode && ( ... )}`。

- [ ] **Step 3: 类型检查 + lint**

Run: `cd page; npm run type-check; if ($?) { npm run lint }`
Expected: 两者均无错误（`BatchCreationPage` 尚未传新 props，均为可选，向后兼容）

- [ ] **Step 4: Commit**

```bash
git add page/src/services/creationApi.ts page/src/pages/home/components/BatchTaskCard.tsx
git commit -m "feat(page): 批量删除 API 客户端 + 产线卡片批量模式勾选态"
```

---

### Task 4: BatchCreationPage 批量模式（工具栏 + 确认弹窗 + 删除流程）

**Files:**
- Modify: `page/src/pages/home/components/BatchCreationPage.tsx`

**Interfaces:**
- Consumes: Task 3 的 `creationApi.batchDeleteBatchAutomationItems` 与 `BatchTaskCard` 新 props；既有 `loadTasksFromApi` / `setTasksError` / `ApiError`。
- Produces: 用户可见的批量管理模式（无对外接口）。

- [ ] **Step 1: 新增模块级辅助函数**

在 `BatchCreationPage.tsx` 顶部 `getAvailableSeedsCount`（26 行附近）之前追加：

```typescript
/** 运行中/排队中的产线记录禁止批量删除（后台任务仍在写入）。 */
function isTaskDeletable(t: BatchTask): boolean {
  return t.itemStatus !== "running" && t.itemStatus !== "pending";
}
```

- [ ] **Step 2: 新增批量模式 state 与回调**

在组件内 `exportHint` state（116 行）之后追加：

```typescript
  const [batchMode, setBatchMode] = useState(false);
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [showBatchDeleteConfirm, setShowBatchDeleteConfirm] = useState(false);
  const [batchResultHint, setBatchResultHint] = useState<string | null>(null);
```

在 `handleDeleteTask`（178-189 行）之后追加：

```typescript
  const deletableTaskIds = useMemo(
    () => tasks.filter(isTaskDeletable).map((t) => t.id),
    [tasks]
  );

  // 列表刷新后清掉已不存在/已变为不可删的选中项
  useEffect(() => {
    setSelectedTaskIds((prev) => {
      const valid = new Set(deletableTaskIds);
      const next = new Set(Array.from(prev).filter((id) => valid.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [deletableTaskIds]);

  const toggleTaskSelect = useCallback((taskId: string) => {
    setSelectedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }, []);

  const selectAllTasks = useCallback(() => {
    setSelectedTaskIds(new Set(deletableTaskIds));
  }, [deletableTaskIds]);

  const clearTaskSelection = useCallback(() => {
    setSelectedTaskIds(new Set());
  }, []);

  const exitBatchMode = useCallback(() => {
    setBatchMode(false);
    setSelectedTaskIds(new Set());
  }, []);

  const selectedFeedbackCount = useMemo(
    () =>
      tasks
        .filter((t) => selectedTaskIds.has(t.id))
        .reduce((acc, t) => acc + t.images.filter((im) => im.userFeedback).length, 0),
    [tasks, selectedTaskIds]
  );

  const handleBatchDelete = useCallback(async () => {
    if (selectedTaskIds.size === 0 || batchDeleting) return;
    setBatchDeleting(true);
    setBatchResultHint(null);
    try {
      const res = await creationApi.batchDeleteBatchAutomationItems(
        Array.from(selectedTaskIds)
      );
      const parts = [`成功删除 ${res.deleted.length} 条`];
      if (res.skipped_running.length > 0) parts.push(`跳过 ${res.skipped_running.length} 条进行中`);
      if (res.failed.length > 0) parts.push(`失败 ${res.failed.length} 条`);
      setBatchResultHint(parts.join("，"));
      exitBatchMode();
    } catch (e) {
      // 请求整体失败时可能已删除一部分，finally 里的刷新会拉到真实状态
      setTasksError(e instanceof ApiError ? e.message : "批量删除失败");
    } finally {
      setBatchDeleting(false);
      await loadTasksFromApi();
    }
  }, [selectedTaskIds, batchDeleting, exitBatchMode, loadTasksFromApi]);
```

- [ ] **Step 3: 列表头新增"批量管理"按钮与结果提示**

在"产线产出"头部行的右侧按钮组（578-598 行 `<div className="flex items-center gap-2">`）内，`{exportHint && ...}` 之前插入结果提示、"导出 Feedback JSON" 按钮之前插入批量管理按钮：

```tsx
                {batchResultHint && (
                  <span className="text-xs text-rose-400/70">{batchResultHint}</span>
                )}
                <button
                  type="button"
                  onClick={() => (batchMode ? exitBatchMode() : setBatchMode(true))}
                  disabled={batchDeleting}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
                  style={{
                    background: batchMode ? "rgba(244,114,182,0.15)" : "rgba(253,164,175,0.1)",
                    border: "1px solid rgba(253,164,175,0.2)",
                    color: "#f472b6",
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    opacity: batchDeleting ? 0.5 : 1,
                  }}
                >
                  <i className="ri-checkbox-multiple-line text-xs"></i>
                  {batchMode ? "退出批量" : "批量管理"}
                </button>
```

- [ ] **Step 4: 批量模式工具栏**

在头部行（565-599 行的 `<div className="flex items-center justify-between flex-wrap gap-2">...</div>`）之后、`{tasks.map(...)}`（600 行）之前插入：

```tsx
            {batchMode && (
              <div
                className="flex items-center gap-3 flex-wrap rounded-xl px-3 py-2"
                style={{
                  background: "rgba(253,164,175,0.08)",
                  border: "1px dashed rgba(244,114,182,0.3)",
                }}
              >
                <span
                  className="text-xs font-bold"
                  style={{ color: "#f472b6", fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  已选 {selectedTaskIds.size} 条
                </span>
                <button
                  type="button"
                  onClick={selectAllTasks}
                  className="text-xs cursor-pointer transition-colors duration-200 whitespace-nowrap"
                  style={{ color: "#f472b6" }}
                >
                  全选
                </button>
                <button
                  type="button"
                  onClick={clearTaskSelection}
                  className="text-xs cursor-pointer transition-colors duration-200 whitespace-nowrap"
                  style={{ color: "#f472b6" }}
                >
                  取消全选
                </button>
                <span className="text-xs text-rose-300/50">进行中/排队中的记录不可选</span>
                <button
                  type="button"
                  onClick={() => setShowBatchDeleteConfirm(true)}
                  disabled={selectedTaskIds.size === 0 || batchDeleting}
                  className="ml-auto flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-medium text-white transition-all duration-200 whitespace-nowrap"
                  style={{
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    background:
                      selectedTaskIds.size === 0 || batchDeleting
                        ? "rgba(251,113,133,0.35)"
                        : "linear-gradient(135deg, #fb7185 0%, #f472b6 100%)",
                    cursor:
                      selectedTaskIds.size === 0 || batchDeleting ? "not-allowed" : "pointer",
                  }}
                >
                  <i className="ri-delete-bin-line text-xs"></i>
                  {batchDeleting ? "删除中…" : "删除所选"}
                </button>
              </div>
            )}
```

- [ ] **Step 5: 给 BatchTaskCard 传批量 props**

600-609 行的 `tasks.map` 改为：

```tsx
            {tasks.map((task, idx) => (
              <BatchTaskCard
                key={task.id}
                task={task}
                index={idx}
                batchMode={batchMode}
                selected={selectedTaskIds.has(task.id)}
                selectable={isTaskDeletable(task)}
                onToggleSelect={toggleTaskSelect}
                onDelete={handleDeleteTask}
                onMarkUsed={handleMarkUsed}
                onSaveFeedback={handleSaveFeedback}
              />
            ))}
```

- [ ] **Step 6: 批量删除确认弹窗**

在组件 JSX 末尾、`<CuteConfirmModal ... />`（644 行）之前插入（视觉沿用 `BatchTaskCard` 单删弹窗 463-524 行的结构）：

```tsx
      {showBatchDeleteConfirm && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center">
          <div
            className="absolute inset-0"
            style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
            onClick={() => setShowBatchDeleteConfirm(false)}
          />
          <div
            className="relative w-80 rounded-3xl overflow-hidden mx-4"
            style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex flex-col items-center pt-7 pb-4 px-6">
              <div
                className="w-14 h-14 flex items-center justify-center rounded-2xl mb-4"
                style={{
                  background: "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
                  border: "1.5px solid rgba(244,114,182,0.2)",
                }}
              >
                <i className="ri-delete-bin-2-line text-rose-400 text-2xl"></i>
              </div>
              <h3
                className="text-base font-bold text-rose-600 mb-1.5"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                删除选中的 {selectedTaskIds.size} 条产线记录？
              </h3>
              <p className="text-sm text-rose-400/70 text-center leading-relaxed">
                这会同步删除对应的 Prompt 预生成记录和美图创作记录，不可恢复哦～
              </p>
              {selectedFeedbackCount > 0 && (
                <div
                  className="mt-3 rounded-xl px-3 py-2 text-xs font-medium text-center leading-relaxed"
                  style={{
                    background: "rgba(251,191,36,0.15)",
                    border: "1px solid rgba(217,119,6,0.35)",
                    color: "#b45309",
                  }}
                >
                  ⚠️ 其中将连带删除 {selectedFeedbackCount} 条人工 feedback，建议先「导出
                  Feedback JSON」再删除！
                </div>
              )}
            </div>
            <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />
            <div className="flex gap-3 p-4">
              <button
                type="button"
                onClick={() => setShowBatchDeleteConfirm(false)}
                className="flex-1 py-2.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                style={{
                  background: "rgba(253,164,175,0.08)",
                  color: "#f472b6",
                  border: "1px solid rgba(244,114,182,0.2)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                再想想
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowBatchDeleteConfirm(false);
                  void handleBatchDelete();
                }}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white"
                style={{
                  background: "linear-gradient(135deg, #fb7185 0%, #f472b6 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
```

- [ ] **Step 7: 类型检查 + lint + 全量后端测试**

Run: `cd page; npm run type-check; if ($?) { npm run lint }`
Expected: 无错误

Run（仓库根目录）: `python -m pytest`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add page/src/pages/home/components/BatchCreationPage.tsx
git commit -m "feat(page): 灵感产线批量管理模式（勾选/全选/批量删除/feedback 数警示）"
```

---

## 验收对照（spec → task）

| Spec 要求 | Task |
|---|---|
| 批量管理模式 + 逐卡勾选 + 全选/取消全选 | Task 3（卡片）、Task 4（页面） |
| running/pending 前端禁选 | Task 3 Step 2（selectable）、Task 4 Step 1（isTaskDeletable） |
| running/pending 后端强制跳过 | Task 1 |
| 确认弹窗显示 feedback 数 + 醒目警示 | Task 4 Step 6 |
| POST 批量端点、恒 200、结果四分类 | Task 2 |
| 去重去空→空 400、>200 → 422 | Task 2 |
| 复用 delete_batch_item 级联清理 | Task 1 |
| 部分失败不阻断 + 日志 | Task 1 |
| toast 结果提示 + 刷新列表 + 退出批量模式 | Task 4 Step 2（handleBatchDelete） |
| pytest 编排逻辑测试 | Task 1、Task 2 |
| type-check + lint | Task 3、Task 4 |
