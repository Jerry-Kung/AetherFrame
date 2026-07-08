# 生产工作流人工 Feedback 入口 + 一键结构化导出 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 首页灵感工坊每张产线出图可填写人工 feedback（文本 + 腿脚崩坏勾选），并一键全量导出结构化 JSON 供归档为实验 Case。

**Architecture:** 后端新增 `creation_image_feedbacks` 表（一行 = 一张图的已填 feedback，清空即删行），走 模型→repository→service→route 四层；`items-hydrated` 接口附带 feedbacks 回显；导出接口聚合全库已填记录。前端在 `BatchTaskCard` 图片网格加逐图入口弹窗，`BatchCreationPage` 加一键导出按钮（Blob 下载）。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite（后端）；React 19 + TypeScript + Vite（前端）；pytest。

**Spec:** `docs/superpowers/specs/2026-07-08-production-feedback-entry-design.md`（已批准，本计划所有约定以它为准）

## Global Constraints

- 导出 JSON 顶层 `"schema": "aetherframe_feedback_v1"`，字段名与 spec §2.3 完全一致（snake_case）。
- 表里只存「已填」记录：`feedback_text` 为空字符串（strip 后）且 `leg_foot_bad=False` 的保存请求 = 删除该行。
- 唯一约束 `(quick_create_task_id, prompt_id, image_index)`，保存即 upsert。
- 删除联动走**服务层显式删除**（`QuickCreateService.delete_history` 内清理 feedback 行），不依赖 SQLite FK PRAGMA；新表不建外键。
- API 全部走 `ApiResponse(success, data, message)` 包装，路由前缀 `/api/creation`。
- 前端 UI 文案为中文、玫瑰系视觉（`fontFamily: 'ZCOOL KuaiLe', cursive`、rose 色板），风格对齐 `BatchTaskCard.tsx` 现有弹窗。
- 前端自动导入：React hooks（`useState`/`useCallback` 等）由 unplugin-auto-import 提供，**新组件不要手写 `import { useState } from "react"`**。
- 禁止改动 `experiments/` 下任何冻结物；禁止提交 `app/tools/llm/config.py`。
- 所有后端命令从仓库根运行；pytest 用 `python -m pytest`。

---

## 文件结构总览

| 文件 | 动作 | 职责 |
|---|---|---|
| `app/models/creation_feedback.py` | 新建 | `CreationImageFeedback` 模型 |
| `app/models/database.py` | 修改 | `init_db` 导入新模型（create_all 注册） |
| `app/repositories/creation_feedback_repository.py` | 新建 | upsert / 删除 / 按任务批查 / 全量列表 |
| `app/services/creation_service/feedback_service.py` | 新建 | 保存语义（清空即删）+ 导出聚合 |
| `app/services/creation_service/quick_create_service.py` | 修改 | `delete_history` 联动清理 feedback |
| `app/services/creation_service/batch_automation_service.py` | 修改 | `list_items_hydrated` 附带 `feedbacks` |
| `app/schemas/creation.py` | 修改 | `ImageFeedbackSaveRequest` / `ImageFeedbackOut` |
| `app/routes/creation.py` | 修改 | PUT 保存路由 + GET 导出路由 |
| `tests/conftest.py` | 修改 | 清理新表 |
| `tests/test_creation_feedback.py` | 新建 | repo + service + 导出测试 |
| `tests/routes/test_creation_feedback_routes.py` | 新建 | 路由测试 |
| `page/src/services/creationApi.ts` | 修改 | 保存/导出 API + 类型 |
| `page/src/types/quickCreate.ts` | 修改 | `QuickCreateImage` 加 `imageIndex`/`userFeedback` |
| `page/src/utils/quickCreateReview.ts` | 修改 | 图片条目带 `imageIndex` |
| `page/src/utils/batchAutomationDisplay.ts` | 修改 | hydrated feedbacks 合并进图片 |
| `page/src/pages/home/components/ImageFeedbackModal.tsx` | 新建 | 填写弹窗 |
| `page/src/pages/home/components/BatchTaskCard.tsx` | 修改 | 逐图入口按钮 + 删除文案 |
| `page/src/pages/home/components/BatchCreationPage.tsx` | 修改 | 导出按钮 + 保存回调 patch state |

---

### Task 1: 数据模型 + Repository

**Files:**
- Create: `app/models/creation_feedback.py`
- Create: `app/repositories/creation_feedback_repository.py`
- Modify: `app/models/database.py`（`init_db` 内约 544-546 行的模型导入区）
- Modify: `tests/conftest.py`（`db_session` fixture 的模型导入与清理块）
- Test: `tests/test_creation_feedback.py`

**Interfaces:**
- Consumes: `app.models.database.Base`；`tests/conftest.py` 的 `db_session` fixture。
- Produces: `CreationImageFeedback`（列见下）；`CreationImageFeedbackRepository`，方法签名：
  - `get_for_image(quick_create_task_id: str, prompt_id: str, image_index: int) -> Optional[CreationImageFeedback]`
  - `upsert(*, quick_create_task_id: str, prompt_id: str, image_index: int, leg_foot_bad: bool, feedback_text: str) -> CreationImageFeedback`
  - `delete_for_image(quick_create_task_id: str, prompt_id: str, image_index: int) -> bool`
  - `list_for_task_ids(task_ids: List[str]) -> Dict[str, List[CreationImageFeedback]]`
  - `list_all() -> List[CreationImageFeedback]`
  - `delete_for_task(quick_create_task_id: str) -> int`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_creation_feedback.py`：

```python
"""生产出图人工 feedback：repository / service / 导出聚合测试"""

import uuid

from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.material_repository import MaterialCharacterRepository


def make_qc_task(db_session, *, results=None, seed_prompt="生产种子"):
    """建一条 completed 的一键创作任务（可带 result_json），返回 task。"""
    char = MaterialCharacterRepository(db_session).create(
        {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "fb-char"}
    )
    repo = CreationQuickCreateRepository(db_session)
    task = repo.create(
        character_id=char.id,
        seed_prompt=seed_prompt,
        n=2,
        aspect_ratio="1:1",
        selected_prompts=[],
        status="completed",
    )
    if results is not None:
        task = repo.update(task.id, {"result_json": results})
    return task


class TestFeedbackRepository:
    def test_upsert_creates_then_updates_single_row(self, db_session):
        task = make_qc_task(db_session)
        repo = CreationImageFeedbackRepository(db_session)
        row = repo.upsert(
            quick_create_task_id=task.id,
            prompt_id="p1",
            image_index=0,
            leg_foot_bad=True,
            feedback_text="脚趾夸张",
        )
        assert row.id
        row2 = repo.upsert(
            quick_create_task_id=task.id,
            prompt_id="p1",
            image_index=0,
            leg_foot_bad=False,
            feedback_text="修正：其实没问题",
        )
        assert row2.id == row.id
        assert repo.list_all() and len(repo.list_all()) == 1
        got = repo.get_for_image(task.id, "p1", 0)
        assert got is not None
        assert got.leg_foot_bad is False
        assert got.feedback_text == "修正：其实没问题"

    def test_delete_for_image(self, db_session):
        task = make_qc_task(db_session)
        repo = CreationImageFeedbackRepository(db_session)
        repo.upsert(
            quick_create_task_id=task.id, prompt_id="p1", image_index=1,
            leg_foot_bad=False, feedback_text="备注",
        )
        assert repo.delete_for_image(task.id, "p1", 1) is True
        assert repo.delete_for_image(task.id, "p1", 1) is False  # 幂等
        assert repo.get_for_image(task.id, "p1", 1) is None

    def test_list_for_task_ids_groups_by_task(self, db_session):
        t1 = make_qc_task(db_session)
        t2 = make_qc_task(db_session)
        repo = CreationImageFeedbackRepository(db_session)
        repo.upsert(quick_create_task_id=t1.id, prompt_id="p1", image_index=0,
                    leg_foot_bad=True, feedback_text="a")
        repo.upsert(quick_create_task_id=t1.id, prompt_id="p2", image_index=1,
                    leg_foot_bad=False, feedback_text="b")
        repo.upsert(quick_create_task_id=t2.id, prompt_id="p1", image_index=0,
                    leg_foot_bad=False, feedback_text="c")
        grouped = repo.list_for_task_ids([t1.id, t2.id, "qcreate_missing"])
        assert set(grouped.keys()) == {t1.id, t2.id}
        assert len(grouped[t1.id]) == 2
        assert len(grouped[t2.id]) == 1
        assert repo.list_for_task_ids([]) == {}

    def test_delete_for_task_removes_all_rows(self, db_session):
        task = make_qc_task(db_session)
        repo = CreationImageFeedbackRepository(db_session)
        for i in range(3):
            repo.upsert(quick_create_task_id=task.id, prompt_id="p1", image_index=i,
                        leg_foot_bad=False, feedback_text=f"n{i}")
        assert repo.delete_for_task(task.id) == 3
        assert repo.list_all() == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_creation_feedback.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.repositories.creation_feedback_repository'`

- [ ] **Step 3: 写模型**

创建 `app/models/creation_feedback.py`：

```python
"""创作模块 — 生产出图人工 feedback。

设计文档：docs/superpowers/specs/2026-07-08-production-feedback-entry-design.md
一行 = 一张图的已填 feedback；文本清空且未勾选时删行，表里只存「已填」记录。
"""

import logging

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.models.database import Base

logger = logging.getLogger(__name__)


class CreationImageFeedback(Base):
    __tablename__ = "creation_image_feedbacks"

    id = Column(String, primary_key=True, index=True)
    quick_create_task_id = Column(String(64), nullable=False, index=True)
    prompt_id = Column(String(128), nullable=False)
    image_index = Column(Integer, nullable=False)
    leg_foot_bad = Column(Boolean, nullable=False, default=False)
    feedback_text = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "quick_create_task_id",
            "prompt_id",
            "image_index",
            name="uq_creation_image_feedback_image",
        ),
    )

    def __repr__(self):
        return (
            f"<CreationImageFeedback(id={self.id!r}, task={self.quick_create_task_id!r}, "
            f"prompt={self.prompt_id!r}, index={self.image_index!r})>"
        )
```

- [ ] **Step 4: 写 Repository**

创建 `app/repositories/creation_feedback_repository.py`：

```python
import logging
import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.creation_feedback import CreationImageFeedback

logger = logging.getLogger(__name__)


class CreationImageFeedbackRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_image(
        self, quick_create_task_id: str, prompt_id: str, image_index: int
    ) -> Optional[CreationImageFeedback]:
        return (
            self.db.query(CreationImageFeedback)
            .filter(
                CreationImageFeedback.quick_create_task_id == quick_create_task_id,
                CreationImageFeedback.prompt_id == prompt_id,
                CreationImageFeedback.image_index == image_index,
            )
            .first()
        )

    def upsert(
        self,
        *,
        quick_create_task_id: str,
        prompt_id: str,
        image_index: int,
        leg_foot_bad: bool,
        feedback_text: str,
    ) -> CreationImageFeedback:
        row = self.get_for_image(quick_create_task_id, prompt_id, image_index)
        if row is None:
            row = CreationImageFeedback(
                id=f"imgfb_{uuid.uuid4().hex[:12]}",
                quick_create_task_id=quick_create_task_id,
                prompt_id=prompt_id,
                image_index=image_index,
            )
            self.db.add(row)
        row.leg_foot_bad = bool(leg_foot_bad)
        row.feedback_text = feedback_text or ""
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_for_image(
        self, quick_create_task_id: str, prompt_id: str, image_index: int
    ) -> bool:
        row = self.get_for_image(quick_create_task_id, prompt_id, image_index)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def list_for_task_ids(
        self, task_ids: List[str]
    ) -> Dict[str, List[CreationImageFeedback]]:
        """按 quick_create_task_id 分组返回，仅含有已填记录的任务。"""
        if not task_ids:
            return {}
        rows = (
            self.db.query(CreationImageFeedback)
            .filter(CreationImageFeedback.quick_create_task_id.in_(list(set(task_ids))))
            .order_by(
                CreationImageFeedback.quick_create_task_id,
                CreationImageFeedback.prompt_id,
                CreationImageFeedback.image_index,
            )
            .all()
        )
        out: Dict[str, List[CreationImageFeedback]] = {}
        for r in rows:
            out.setdefault(r.quick_create_task_id, []).append(r)
        return out

    def list_all(self) -> List[CreationImageFeedback]:
        return (
            self.db.query(CreationImageFeedback)
            .order_by(
                CreationImageFeedback.quick_create_task_id,
                CreationImageFeedback.prompt_id,
                CreationImageFeedback.image_index,
            )
            .all()
        )

    def delete_for_task(self, quick_create_task_id: str) -> int:
        n = (
            self.db.query(CreationImageFeedback)
            .filter(CreationImageFeedback.quick_create_task_id == quick_create_task_id)
            .delete()
        )
        self.db.commit()
        return int(n)
```

- [ ] **Step 5: 注册模型到 create_all 与测试 fixture**

修改 `app/models/database.py` 的 `init_db()`，在现有模型导入行之后（`from app.models.beautify import ImageBeautifyTask  # noqa: F401` 一行后）加：

```python
        from app.models.creation_feedback import CreationImageFeedback  # noqa: F401
```

修改 `tests/conftest.py` 的 `db_session` fixture：

1. 模型导入区（`from app.models.beautify import ImageBeautifyTask` 一行后）加：

```python
    from app.models.creation_feedback import CreationImageFeedback
```

2. 清理块第一行（`db.query(ImageBeautifyTask).delete()` 之前）加：

```python
        db.query(CreationImageFeedback).delete()
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_creation_feedback.py -v`
Expected: 4 个测试 PASS

- [ ] **Step 7: 提交**

```bash
git add app/models/creation_feedback.py app/repositories/creation_feedback_repository.py app/models/database.py tests/conftest.py tests/test_creation_feedback.py
git commit -m "feat(creation): 生产出图人工 feedback 数据模型与 repository"
```

---

### Task 2: ImageFeedbackService 保存语义 + 删除联动

**Files:**
- Create: `app/services/creation_service/feedback_service.py`
- Modify: `app/services/creation_service/quick_create_service.py`（`delete_history`，约 592-620 行）
- Test: `tests/test_creation_feedback.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `CreationImageFeedbackRepository`；`CreationQuickCreateRepository.get_by_id`。
- Produces: `ImageFeedbackService`（`app.services.creation_service.feedback_service`）：
  - `save_feedback(*, task_id: str, prompt_id: str, image_index: int, feedback_text: str, leg_foot_bad: bool) -> Optional[Dict]` — 任务不存在抛 `ValueError`；清空即删返回 `None`；否则返回 `serialize_feedback_row` 字典。
  - 模块级 `serialize_feedback_row(row) -> Dict`（Task 4 的 hydrated 装配也用它）：
    `{"prompt_id": str, "image_index": int, "leg_foot_bad": bool, "feedback_text": str}`
  - 注意：`build_export` 属 Task 3，本 Task **不要**创建它的任何占位。

- [ ] **Step 1: 写失败测试**

在 `tests/test_creation_feedback.py` 追加：

```python
from app.services.creation_service.feedback_service import ImageFeedbackService


class TestImageFeedbackService:
    def test_save_creates_row_and_returns_payload(self, db_session):
        task = make_qc_task(db_session)
        svc = ImageFeedbackService(db_session)
        data = svc.save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="袜口花边过重", leg_foot_bad=True,
        )
        assert data == {
            "prompt_id": "p1",
            "image_index": 0,
            "leg_foot_bad": True,
            "feedback_text": "袜口花边过重",
        }

    def test_save_empty_clears_row(self, db_session):
        task = make_qc_task(db_session)
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=0,
                          feedback_text="临时", leg_foot_bad=False)
        data = svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=0,
                                 feedback_text="   ", leg_foot_bad=False)
        assert data is None
        assert CreationImageFeedbackRepository(db_session).list_all() == []
        # 行本不存在时清空也幂等成功
        assert svc.save_feedback(task_id=task.id, prompt_id="p9", image_index=0,
                                 feedback_text="", leg_foot_bad=False) is None

    def test_save_only_checkbox_is_filled(self, db_session):
        task = make_qc_task(db_session)
        data = ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=2,
            feedback_text="", leg_foot_bad=True,
        )
        assert data is not None and data["leg_foot_bad"] is True

    def test_save_missing_task_raises(self, db_session):
        import pytest as _pytest
        with _pytest.raises(ValueError, match="任务不存在"):
            ImageFeedbackService(db_session).save_feedback(
                task_id="qcreate_missing0000", prompt_id="p1", image_index=0,
                feedback_text="x", leg_foot_bad=False,
            )

    def test_quick_create_delete_history_removes_feedback(self, db_session):
        from app.services.creation_service.quick_create_service import QuickCreateService

        task = make_qc_task(db_session)
        ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="将被联动删除", leg_foot_bad=True,
        )
        QuickCreateService(db_session).delete_history(task.id)
        assert CreationImageFeedbackRepository(db_session).list_all() == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_creation_feedback.py -v -k "Service or delete_history"`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.creation_service.feedback_service'`

- [ ] **Step 3: 写 Service**

创建 `app/services/creation_service/feedback_service.py`：

```python
"""生产出图人工 feedback：保存语义（清空即删）与全量导出聚合。

设计文档：docs/superpowers/specs/2026-07-08-production-feedback-entry-design.md §1/§2
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.creation_feedback import CreationImageFeedback
from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository
from app.repositories.creation_repository import CreationQuickCreateRepository

logger = logging.getLogger(__name__)


def serialize_feedback_row(row: CreationImageFeedback) -> Dict[str, Any]:
    return {
        "prompt_id": row.prompt_id,
        "image_index": int(row.image_index),
        "leg_foot_bad": bool(row.leg_foot_bad),
        "feedback_text": row.feedback_text or "",
    }


class ImageFeedbackService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CreationImageFeedbackRepository(db)
        self.quick_repo = CreationQuickCreateRepository(db)

    def save_feedback(
        self,
        *,
        task_id: str,
        prompt_id: str,
        image_index: int,
        feedback_text: str,
        leg_foot_bad: bool,
    ) -> Optional[Dict[str, Any]]:
        tid = (task_id or "").strip()
        pid = (prompt_id or "").strip()
        if not tid or not pid:
            raise ValueError("task_id / prompt_id 无效")
        if self.quick_repo.get_by_id(tid) is None:
            raise ValueError("一键创作任务不存在")

        text = (feedback_text or "").strip()
        bad = bool(leg_foot_bad)
        if not text and not bad:
            self.repo.delete_for_image(tid, pid, image_index)
            return None
        row = self.repo.upsert(
            quick_create_task_id=tid,
            prompt_id=pid,
            image_index=image_index,
            leg_foot_bad=bad,
            feedback_text=text,
        )
        return serialize_feedback_row(row)
```

- [ ] **Step 4: delete_history 联动清理**

修改 `app/services/creation_service/quick_create_service.py` 的 `delete_history`。在
`BeautifyService(self.db).cleanup_for_quick_create_task(hid)` 的 try/except 块之后、
`deleted = self.quick_repo.delete(hid)` 之前插入：

```python
        try:
            from app.repositories.creation_feedback_repository import (
                CreationImageFeedbackRepository,
            )

            CreationImageFeedbackRepository(self.db).delete_for_task(hid)
        except Exception:
            logger.warning("清理图片 feedback 失败: %s", hid, exc_info=True)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_creation_feedback.py -v`
Expected: 全部 PASS（Task 1 的 4 个 + 本 Task 的 5 个）

- [ ] **Step 6: 提交**

```bash
git add app/services/creation_service/feedback_service.py app/services/creation_service/quick_create_service.py tests/test_creation_feedback.py
git commit -m "feat(creation): feedback 保存服务（清空即删）与删除联动清理"
```

---

### Task 3: 全量导出聚合 `build_export`

**Files:**
- Modify: `app/services/creation_service/feedback_service.py`
- Test: `tests/test_creation_feedback.py`（追加）

**Interfaces:**
- Consumes: `CreationImageFeedbackRepository.list_all`；`CreationQuickCreateRepository.get_by_ids`；
  `CreationBatchRunItem`（按 `quick_create_task_id` 反查）；`MaterialCharacterRepository.get_by_ids`；
  `CreationPromptPrecreationRepository.get_by_ids` + `PromptPrecreationService._build_history_detail_from_parts`（取 Prompt 卡片标题，取不到回落 `prompt_id`）；
  `quick_create_service._parse_json_list`（解析 `result_json`）。
- Produces: `ImageFeedbackService.build_export() -> Dict`，结构 = spec §2.3（`schema` / `exported_at` / `records[]`，字段名逐一对应）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_creation_feedback.py` 追加：

```python
QC_RESULTS = [
    {
        "prompt_id": "p1",
        "full_prompt": "最终 Prompt 甲",
        "generated_images": [
            {"filename": "a0.png", "path": "images/a0.png"},
            {"filename": "a1.png", "path": "images/a1.png"},
            {"filename": "a2.png", "path": "images/a2.png"},
        ],
    },
    {
        "prompt_id": "p2",
        "full_prompt": "最终 Prompt 乙",
        "generated_images": [{"filename": "b0.png", "path": "images/b0.png"}],
    },
]


def make_batch_item_for_task(db_session, qc_task):
    from app.repositories.creation_batch_repository import CreationBatchRepository

    repo = CreationBatchRepository(db_session)
    run = repo.create_run(iterations_total=1, config_json="{}", status="completed")
    item = repo.create_item(
        run_id=run.id,
        step_index=0,
        character_id=qc_task.character_id,
        seed_prompt_id="seed-cs-0",
        seed_section="character_specific",
        seed_prompt_text="窗边坐姿，白色过膝袜",
        status="completed",
    )
    return repo.update_item(
        item.id, {"quick_create_task_id": qc_task.id, "status": "completed"}
    )


class TestBuildExport:
    def test_export_with_batch_item(self, db_session):
        task = make_qc_task(db_session, results=QC_RESULTS)
        item = make_batch_item_for_task(db_session, task)
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=0,
                          feedback_text="脚趾夸张", leg_foot_bad=True)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=2,
                          feedback_text="构图很好", leg_foot_bad=False)

        out = svc.build_export()
        assert out["schema"] == "aetherframe_feedback_v1"
        assert out["exported_at"]
        assert len(out["records"]) == 1
        rec = out["records"][0]
        assert rec["batch_item_id"] == item.id
        assert rec["quick_create_task_id"] == task.id
        assert rec["character_id"] == task.character_id
        assert rec["character_name"] == "fb-char"
        assert rec["seed_prompt_id"] == "seed-cs-0"
        assert rec["seed_section"] == "character_specific"
        assert rec["seed_prompt_text"] == "窗边坐姿，白色过膝袜"
        assert rec["created_at"]
        # 只含有已填 feedback 的 p1 组；p2 无 feedback 不导出
        assert len(rec["prompt_groups"]) == 1
        g = rec["prompt_groups"][0]
        assert g["prompt_id"] == "p1"
        assert g["prompt_title"] == "p1"  # 无预生成卡片时回落 prompt_id
        assert g["full_prompt"] == "最终 Prompt 甲"
        assert g["total_images"] == 3
        assert g["images"] == [
            {"image_index": 0, "image_path": "images/a0.png",
             "leg_foot_bad": True, "feedback_text": "脚趾夸张"},
            {"image_index": 2, "image_path": "images/a2.png",
             "leg_foot_bad": False, "feedback_text": "构图很好"},
        ]

    def test_export_without_batch_item_falls_back_to_task_seed(self, db_session):
        task = make_qc_task(db_session, results=QC_RESULTS, seed_prompt="手动种子")
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p2", image_index=0,
                          feedback_text="ok", leg_foot_bad=False)
        rec = svc.build_export()["records"][0]
        assert rec["batch_item_id"] is None
        assert rec["seed_prompt_id"] is None
        assert rec["seed_section"] is None
        assert rec["seed_prompt_text"] == "手动种子"

    def test_export_skips_dangling_rows_and_empty_is_ok(self, db_session):
        svc = ImageFeedbackService(db_session)
        assert svc.build_export()["records"] == []
        # 悬空 feedback（任务已不存在）跳过且不阻断
        CreationImageFeedbackRepository(db_session).upsert(
            quick_create_task_id="qcreate_gone00000000", prompt_id="p1",
            image_index=0, leg_foot_bad=True, feedback_text="悬空",
        )
        task = make_qc_task(db_session, results=QC_RESULTS)
        svc.save_feedback(task_id=task.id, prompt_id="p1", image_index=1,
                          feedback_text="正常", leg_foot_bad=False)
        out = svc.build_export()
        assert [r["quick_create_task_id"] for r in out["records"]] == [task.id]

    def test_export_image_index_out_of_range_keeps_row(self, db_session):
        task = make_qc_task(db_session, results=QC_RESULTS)
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(task_id=task.id, prompt_id="p2", image_index=5,
                          feedback_text="越界索引", leg_foot_bad=False)
        g = svc.build_export()["records"][0]["prompt_groups"][0]
        assert g["images"][0]["image_path"] == ""
        assert g["images"][0]["feedback_text"] == "越界索引"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_creation_feedback.py -v -k Export`
Expected: FAIL，`AttributeError: 'ImageFeedbackService' object has no attribute 'build_export'`

- [ ] **Step 3: 实现 build_export**

在 `app/services/creation_service/feedback_service.py` 顶部导入区补充：

```python
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.creation_batch import CreationBatchRunItem
from app.repositories.creation_repository import (
    CreationPromptPrecreationRepository,
    CreationQuickCreateRepository,
)
from app.repositories.material_repository import MaterialCharacterRepository
from app.services.creation_service.quick_create_service import _parse_json_list
```

在 `ImageFeedbackService` 类内追加：

```python
    def build_export(self) -> Dict[str, Any]:
        """全量导出所有已填 feedback（spec §2.3 aetherframe_feedback_v1）。"""
        rows = self.repo.list_all()
        by_task: Dict[str, List[Any]] = {}
        for r in rows:
            by_task.setdefault(r.quick_create_task_id, []).append(r)

        task_ids = list(by_task.keys())
        qc_map = self.quick_repo.get_by_ids(task_ids) if task_ids else {}

        items = (
            self.db.query(CreationBatchRunItem)
            .filter(CreationBatchRunItem.quick_create_task_id.in_(task_ids))
            .all()
            if task_ids
            else []
        )
        item_map = {it.quick_create_task_id: it for it in items}

        char_ids = list({t.character_id for t in qc_map.values() if t.character_id})
        char_map = (
            {c.id: c for c in MaterialCharacterRepository(self.db).get_by_ids(char_ids)}
            if char_ids
            else {}
        )

        title_maps = self._build_prompt_title_maps(items, char_map)

        records: List[Dict[str, Any]] = []
        for tid in sorted(by_task.keys()):
            task = qc_map.get(tid)
            if task is None:
                logger.warning("feedback 导出：一键创作任务已不存在，跳过 %s", tid)
                continue
            try:
                records.append(
                    self._build_record(
                        task, by_task[tid], item_map.get(tid), char_map,
                        title_maps.get(tid, {}),
                    )
                )
            except Exception:
                logger.exception("feedback 导出：装配记录失败，跳过 %s", tid)
        return {
            "schema": "aetherframe_feedback_v1",
            "exported_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "records": records,
        }

    def _build_prompt_title_maps(
        self, items: List[Any], char_map: Dict[str, Any]
    ) -> Dict[str, Dict[str, str]]:
        """{quick_create_task_id: {prompt_id: title}}；任何一步取不到都回落空 map。"""
        out: Dict[str, Dict[str, str]] = {}
        ppc_ids = [
            (it.prompt_precreation_task_id or "").strip()
            for it in items
            if (it.prompt_precreation_task_id or "").strip()
        ]
        if not ppc_ids:
            return out
        try:
            from app.services.creation_service.prompt_precreation_service import (
                PromptPrecreationService,
            )

            ppc_repo = CreationPromptPrecreationRepository(self.db)
            ppc_map = ppc_repo.get_by_ids(ppc_ids)
            ppc_service = PromptPrecreationService(self.db)
            for it in items:
                qc_id = (it.quick_create_task_id or "").strip()
                ppc_task = ppc_map.get((it.prompt_precreation_task_id or "").strip())
                if not qc_id or ppc_task is None:
                    continue
                detail = ppc_service._build_history_detail_from_parts(
                    ppc_task, char_map.get(ppc_task.character_id)
                )
                cards = (detail or {}).get("cards") or []
                out[qc_id] = {
                    str(c.get("id") or ""): str(c.get("title") or "").strip()
                    for c in cards
                    if isinstance(c, dict) and str(c.get("title") or "").strip()
                }
        except Exception:
            logger.warning("feedback 导出：Prompt 标题装配失败，回落 prompt_id", exc_info=True)
        return out

    @staticmethod
    def _image_path(entry: Any) -> str:
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            return str(entry.get("path") or "")
        return ""

    def _build_record(
        self,
        task: Any,
        fb_rows: List[Any],
        item: Optional[Any],
        char_map: Dict[str, Any],
        title_map: Dict[str, str],
    ) -> Dict[str, Any]:
        results = _parse_json_list(task.result_json)
        result_by_pid = {
            str(r.get("prompt_id") or ""): r for r in results if isinstance(r, dict)
        }

        fb_by_prompt: Dict[str, List[Any]] = {}
        for fb in sorted(fb_rows, key=lambda r: (r.prompt_id, r.image_index)):
            fb_by_prompt.setdefault(fb.prompt_id, []).append(fb)

        prompt_groups: List[Dict[str, Any]] = []
        for pid, fbs in fb_by_prompt.items():
            res = result_by_pid.get(pid) or {}
            gen = res.get("generated_images") or []
            images = [
                {
                    "image_index": int(fb.image_index),
                    "image_path": self._image_path(gen[fb.image_index])
                    if 0 <= fb.image_index < len(gen)
                    else "",
                    "leg_foot_bad": bool(fb.leg_foot_bad),
                    "feedback_text": fb.feedback_text or "",
                }
                for fb in fbs
            ]
            prompt_groups.append(
                {
                    "prompt_id": pid,
                    "prompt_title": title_map.get(pid) or pid,
                    "full_prompt": str(res.get("full_prompt") or ""),
                    "total_images": len(gen),
                    "images": images,
                }
            )

        ch = char_map.get(task.character_id)
        return {
            "batch_item_id": item.id if item is not None else None,
            "quick_create_task_id": task.id,
            "character_id": task.character_id,
            "character_name": ch.name if ch is not None else "未知角色",
            "seed_prompt_id": item.seed_prompt_id if item is not None else None,
            "seed_section": item.seed_section if item is not None else None,
            "seed_prompt_text": item.seed_prompt_text
            if item is not None
            else (task.seed_prompt or ""),
            "created_at": task.created_at.isoformat() if task.created_at else "",
            "prompt_groups": prompt_groups,
        }
```

注意：`typing` 导入行与 Task 2 已有的合并（最终一行 `from typing import Any, Dict, List, Optional`），`CreationQuickCreateRepository` 导入改为合并导入（如上），不要重复导入。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_creation_feedback.py -v`
Expected: 全部 PASS（累计 13 个）

- [ ] **Step 5: 提交**

```bash
git add app/services/creation_service/feedback_service.py tests/test_creation_feedback.py
git commit -m "feat(creation): feedback 全量导出聚合（aetherframe_feedback_v1）"
```

---

### Task 4: API 路由 + items-hydrated 回显

**Files:**
- Modify: `app/schemas/creation.py`（文件末尾追加）
- Modify: `app/routes/creation.py`（`get_quick_create_image` 路由之前追加两个路由；导入区补 schema）
- Modify: `app/services/creation_service/batch_automation_service.py`（`list_items_hydrated`）
- Test: `tests/routes/test_creation_feedback_routes.py`

**Interfaces:**
- Consumes: Task 2/3 的 `ImageFeedbackService.save_feedback` / `build_export`、`serialize_feedback_row`；Task 1 的 `CreationImageFeedbackRepository.list_for_task_ids`。
- Produces:
  - `PUT /api/creation/quick-create/tasks/{task_id}/feedback/{prompt_id}/{image_index}`，body `ImageFeedbackSaveRequest{feedback_text: str = "", leg_foot_bad: bool = False}`；404（任务不存在）/422（image_index<0）。
  - `GET /api/creation/feedback/export` → `ApiResponse(data=build_export())`。
  - `items-hydrated` 每个 item 增加 `"feedbacks": [...]`（无则空列表）。

- [ ] **Step 1: 写失败测试**

创建 `tests/routes/test_creation_feedback_routes.py`：

```python
"""feedback 保存 / 导出 / hydrated 回显路由测试"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.material_repository import MaterialCharacterRepository


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


QC_RESULTS = [
    {
        "prompt_id": "p1",
        "full_prompt": "最终 Prompt 甲",
        "generated_images": [{"filename": "a0.png", "path": "images/a0.png"}],
    }
]


def _make_qc_task(db_session):
    char = MaterialCharacterRepository(db_session).create(
        {"id": f"mchar_{uuid.uuid4().hex[:12]}", "name": "fb-route-char"}
    )
    repo = CreationQuickCreateRepository(db_session)
    task = repo.create(
        character_id=char.id, seed_prompt="种子", n=1, aspect_ratio="1:1",
        selected_prompts=[], status="completed",
    )
    return repo.update(task.id, {"result_json": QC_RESULTS})


def _fb_url(task_id, prompt_id="p1", index=0):
    return f"/api/creation/quick-create/tasks/{task_id}/feedback/{prompt_id}/{index}"


def test_save_and_clear_feedback(api_client, db_session):
    task = _make_qc_task(db_session)
    r = api_client.put(_fb_url(task.id), json={"feedback_text": "脚部简陋", "leg_foot_bad": True})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"] == {
        "prompt_id": "p1", "image_index": 0,
        "leg_foot_bad": True, "feedback_text": "脚部简陋",
    }
    # 清空即删
    r2 = api_client.put(_fb_url(task.id), json={"feedback_text": "", "leg_foot_bad": False})
    assert r2.status_code == 200
    assert r2.json()["data"] is None


def test_save_missing_task_404(api_client):
    r = api_client.put(_fb_url("qcreate_missing0000"), json={"feedback_text": "x", "leg_foot_bad": False})
    assert r.status_code == 404


def test_save_negative_index_422(api_client, db_session):
    task = _make_qc_task(db_session)
    r = api_client.put(_fb_url(task.id, index=-1), json={"feedback_text": "x", "leg_foot_bad": False})
    assert r.status_code == 422


def test_export_endpoint(api_client, db_session):
    task = _make_qc_task(db_session)
    api_client.put(_fb_url(task.id), json={"feedback_text": "备注", "leg_foot_bad": True})
    r = api_client.get("/api/creation/feedback/export")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["schema"] == "aetherframe_feedback_v1"
    assert len(data["records"]) == 1
    assert data["records"][0]["quick_create_task_id"] == task.id


def test_hydrated_items_include_feedbacks(api_client, db_session):
    from app.repositories.creation_batch_repository import CreationBatchRepository

    task = _make_qc_task(db_session)
    repo = CreationBatchRepository(db_session)
    run = repo.create_run(iterations_total=1, config_json="{}", status="completed")
    item = repo.create_item(
        run_id=run.id, step_index=0, character_id=task.character_id,
        seed_prompt_id="s1", seed_section="general", seed_prompt_text="seed",
        status="completed",
    )
    repo.update_item(item.id, {"quick_create_task_id": task.id})
    api_client.put(_fb_url(task.id), json={"feedback_text": "回显", "leg_foot_bad": False})

    r = api_client.get("/api/creation/batch-automation/items-hydrated")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    row = next(x for x in items if x["id"] == item.id)
    assert row["feedbacks"] == [
        {"prompt_id": "p1", "image_index": 0,
         "leg_foot_bad": False, "feedback_text": "回显"}
    ]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/routes/test_creation_feedback_routes.py -v`
Expected: FAIL（PUT 路由 405/404、export 404、hydrated 无 `feedbacks` 键）

- [ ] **Step 3: 加 schemas**

`app/schemas/creation.py` 文件末尾追加：

```python
class ImageFeedbackSaveRequest(BaseModel):
    feedback_text: str = ""
    leg_foot_bad: bool = False


class ImageFeedbackOut(BaseModel):
    prompt_id: str
    image_index: int
    leg_foot_bad: bool
    feedback_text: str
```

- [ ] **Step 4: 加路由**

`app/routes/creation.py`：

1. 导入区 `from app.schemas.creation import (...)` 里加 `ImageFeedbackSaveRequest,`；
   服务导入区加：

```python
from app.services.creation_service.feedback_service import ImageFeedbackService
```

2. 在 `@router.get("/quick-create/tasks/{task_id}/images/{image_path:path}")` 之前插入：

```python
@router.put(
    "/quick-create/tasks/{task_id}/feedback/{prompt_id}/{image_index}",
    response_model=ApiResponse,
)
def save_quick_create_image_feedback(
    task_id: str,
    prompt_id: str,
    image_index: int,
    body: ImageFeedbackSaveRequest,
    db: Session = Depends(get_db),
):
    tid = (task_id or "").strip()
    pid = (prompt_id or "").strip()
    if not tid or not pid:
        raise HTTPException(status_code=400, detail="task_id / prompt_id 无效")
    if image_index < 0:
        raise HTTPException(status_code=422, detail="image_index 无效")
    try:
        data = ImageFeedbackService(db).save_feedback(
            task_id=tid,
            prompt_id=pid,
            image_index=image_index,
            feedback_text=body.feedback_text,
            leg_foot_bad=body.leg_foot_bad,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ApiResponse(
        success=True,
        data=data,
        message="保存 feedback 成功" if data is not None else "已清除 feedback",
    )


@router.get("/feedback/export", response_model=ApiResponse)
def export_image_feedback(db: Session = Depends(get_db)):
    data = ImageFeedbackService(db).build_export()
    return ApiResponse(success=True, data=data, message="导出 feedback 成功")
```

- [ ] **Step 5: items-hydrated 附带 feedbacks**

修改 `app/services/creation_service/batch_automation_service.py` 的 `list_items_hydrated`：

1. 在 `beautify_groups = (...)` 语句之后加：

```python
        from app.repositories.creation_feedback_repository import (
            CreationImageFeedbackRepository,
        )
        from app.services.creation_service.feedback_service import serialize_feedback_row

        feedback_groups = (
            CreationImageFeedbackRepository(self.db).list_for_task_ids(list(qc_map.keys()))
            if qc_map
            else {}
        )
```

2. `item_data` 字典初始化里，在 `"quick_create_results": None,` 之后加：

```python
                "feedbacks": [],
```

3. completed 分支内 `if qc_id and qc_service is not None:` 块的末尾（与其同级、`items_payload.append(item_data)` 之前）加：

```python
                if qc_id:
                    item_data["feedbacks"] = [
                        serialize_feedback_row(f)
                        for f in feedback_groups.get(qc_id, [])
                    ]
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/routes/test_creation_feedback_routes.py tests/test_creation_feedback.py tests/test_batch_automation_hydrated_equivalence.py -v`
Expected: 全部 PASS（含既有 hydrated 等价性测试不回归）

- [ ] **Step 7: 提交**

```bash
git add app/schemas/creation.py app/routes/creation.py app/services/creation_service/batch_automation_service.py tests/routes/test_creation_feedback_routes.py
git commit -m "feat(creation): feedback 保存/导出路由与 items-hydrated 回显"
```

---

### Task 5: 前端 API 层与类型贯通

**Files:**
- Modify: `page/src/services/creationApi.ts`
- Modify: `page/src/types/quickCreate.ts`
- Modify: `page/src/utils/quickCreateReview.ts`
- Modify: `page/src/utils/batchAutomationDisplay.ts`

**Interfaces:**
- Consumes: Task 4 的两个后端接口与 hydrated `feedbacks` 字段。
- Produces（Task 6/7 依赖，签名务必一致）:
  - `creationApi.ImageFeedbackEntry`：`{ prompt_id: string; image_index: number; leg_foot_bad: boolean; feedback_text: string }`
  - `creationApi.saveImageFeedback(taskId: string, promptId: string, imageIndex: number, body: { feedback_text: string; leg_foot_bad: boolean }): Promise<ImageFeedbackEntry | null>`
  - `creationApi.exportImageFeedback(): Promise<FeedbackExportPayload>`
  - `QuickCreateImage.imageIndex?: number` 与 `QuickCreateImage.userFeedback?: { feedbackText: string; legFootBad: boolean } | null`
  - `HydratedBatchItem.feedbacks?: ImageFeedbackEntry[] | null`
  - `buildBatchTaskFromHydrated` 产出的 `task.images/groups` 内图片已带 `imageIndex` 与 `userFeedback`。

- [ ] **Step 1: types — `page/src/types/quickCreate.ts`**

`QuickCreateImage` 接口改为（新增两个可选字段，其余不动）：

```ts
export interface QuickCreateImage {
  id: string;
  url: string;
  promptId: string;
  /** 组内序号（generated_images 下标），人工 feedback 定位用 */
  imageIndex?: number;
  aiComment?: AiComment | null;
  /** 已填的人工 feedback（null/undefined = 未填） */
  userFeedback?: { feedbackText: string; legFootBad: boolean } | null;
  beautifiedUrl?: string | null;
  beautifyTaskId?: string | null;
  beautifyStatus?: BeautifyStatus | null;
}
```

- [ ] **Step 2: `page/src/utils/quickCreateReview.ts` — 图片条目带 imageIndex**

`quickCreateImageFromApiEntry` 内两处构造补 `imageIndex: index`：

字符串分支：

```ts
    return {
      id,
      promptId,
      imageIndex: index,
      url: creationApi.buildQuickCreateResultImageUrl(taskId, path),
    };
```

对象分支的 `base`：

```ts
  const base: QuickCreateImage = {
    id,
    promptId,
    imageIndex: index,
    url: creationApi.buildQuickCreateResultImageUrl(taskId, path),
  };
```

- [ ] **Step 3: `page/src/services/creationApi.ts` — 类型与两个 API**

1. `HydratedBatchItem` 接口内（`quick_create_selected_prompts` 之后）加：

```ts
  feedbacks?: ImageFeedbackEntry[] | null;
```

2. 文件末尾（`parseQuickCreateResultImagePath` 之后）追加：

```ts
export interface ImageFeedbackEntry {
  prompt_id: string;
  image_index: number;
  leg_foot_bad: boolean;
  feedback_text: string;
}

export async function saveImageFeedback(
  taskId: string,
  promptId: string,
  imageIndex: number,
  body: { feedback_text: string; leg_foot_bad: boolean }
): Promise<ImageFeedbackEntry | null> {
  const tid = String(taskId ?? "").trim();
  const pid = String(promptId ?? "").trim();
  if (!tid || !pid || !Number.isInteger(imageIndex) || imageIndex < 0) {
    throw new ApiError("feedback 定位参数无效", 400);
  }
  const url = `${API_BASE}/quick-create/tasks/${encodeURIComponent(tid)}/feedback/${encodeURIComponent(pid)}/${imageIndex}`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJson<ImageFeedbackEntry | null>(response);
    throwIfError(response, data);
    return (data.data ?? null) as ImageFeedbackEntry | null;
  } catch (e) {
    rethrow(e);
  }
}

export interface FeedbackExportImage {
  image_index: number;
  image_path: string;
  leg_foot_bad: boolean;
  feedback_text: string;
}

export interface FeedbackExportPromptGroup {
  prompt_id: string;
  prompt_title: string;
  full_prompt: string;
  total_images: number;
  images: FeedbackExportImage[];
}

export interface FeedbackExportRecord {
  batch_item_id: string | null;
  quick_create_task_id: string;
  character_id: string;
  character_name: string;
  seed_prompt_id: string | null;
  seed_section: string | null;
  seed_prompt_text: string;
  created_at: string;
  prompt_groups: FeedbackExportPromptGroup[];
}

export interface FeedbackExportPayload {
  schema: string;
  exported_at: string;
  records: FeedbackExportRecord[];
}

export async function exportImageFeedback(): Promise<FeedbackExportPayload> {
  const url = `${API_BASE}/feedback/export`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<FeedbackExportPayload>(response);
    throwIfError(response, data);
    return data.data as FeedbackExportPayload;
  } catch (e) {
    rethrow(e);
  }
}
```

注意 `throwIfError` 断言 `data: T` 非空，而保存接口清除时 `data` 为 `null` 合法——上面 `saveImageFeedback` 用 `data.data ?? null` 兜住即可（`throwIfError` 只检查 `success`，不检查 `data` 是否为 null；若 type-check 报错，把返回行改为 `return (data as { data?: ImageFeedbackEntry | null }).data ?? null;`）。

- [ ] **Step 4: `page/src/utils/batchAutomationDisplay.ts` — 合并 feedbacks**

`buildBatchTaskFromHydrated` 内，`if (row.quick_create_results && row.quick_create_task_id) {` 块开头（`const taskId = ...` 之后）加：

```ts
    const fbMap = new Map(
      (row.feedbacks ?? []).map((f) => [`${f.prompt_id}#${f.image_index}`, f] as const)
    );
```

同块内图片构造行改为：

```ts
      const imgs: QuickCreateImage[] = (r.generated_images ?? []).map((img, i) => {
        const base = quickCreateImageFromApiEntry(taskId, r.prompt_id, i, img);
        const fb = fbMap.get(`${r.prompt_id}#${i}`);
        return fb
          ? { ...base, userFeedback: { feedbackText: fb.feedback_text, legFootBad: fb.leg_foot_bad } }
          : base;
      });
```

- [ ] **Step 5: 类型检查**

Run: `cd page; npm run type-check`
Expected: 无错误

- [ ] **Step 6: 提交**

```bash
git add page/src/services/creationApi.ts page/src/types/quickCreate.ts page/src/utils/quickCreateReview.ts page/src/utils/batchAutomationDisplay.ts
git commit -m "feat(page): feedback 保存/导出 API 层与图片类型贯通"
```

---

### Task 6: ImageFeedbackModal + BatchTaskCard 逐图入口

**Files:**
- Create: `page/src/pages/home/components/ImageFeedbackModal.tsx`
- Modify: `page/src/pages/home/components/BatchTaskCard.tsx`

**Interfaces:**
- Consumes: Task 5 的 `QuickCreateImage.userFeedback` / `imageIndex`。
- Produces: `BatchTaskCardProps` 新增
  `onSaveFeedback: (taskId: string, img: QuickCreateImage, feedbackText: string, legFootBad: boolean) => Promise<void>`（Task 7 的页面实现它；抛错时弹窗内展示错误、不关闭）。

- [ ] **Step 1: 新建 `page/src/pages/home/components/ImageFeedbackModal.tsx`**

```tsx
import type { QuickCreateImage } from "@/types/quickCreate";

interface ImageFeedbackModalProps {
  image: QuickCreateImage;
  promptTitle: string;
  onSave: (feedbackText: string, legFootBad: boolean) => Promise<void>;
  onClose: () => void;
}

/** 单张产线出图的人工 feedback 填写弹窗（文本 + 腿脚崩坏勾选；清空保存 = 清除） */
export default function ImageFeedbackModal({
  image,
  promptTitle,
  onSave,
  onClose,
}: ImageFeedbackModalProps) {
  const [text, setText] = useState(image.userFeedback?.feedbackText ?? "");
  const [legFootBad, setLegFootBad] = useState(image.userFeedback?.legFootBad ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(text, legFootBad);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }, [onSave, onClose, text, legFootBad]);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
        onClick={saving ? undefined : onClose}
      />
      <div
        className="relative w-96 max-w-[calc(100vw-2rem)] rounded-3xl overflow-hidden mx-4"
        style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pt-6 pb-4 px-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-14 h-14 rounded-xl overflow-hidden shrink-0 border border-rose-100">
              <img src={image.url} alt="" className="w-full h-full object-cover object-top" />
            </div>
            <div className="min-w-0">
              <h3
                className="text-base font-bold text-rose-600"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                填写人工 Feedback
              </h3>
              <p className="text-xs text-rose-400/60 truncate">{promptTitle}</p>
            </div>
          </div>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            placeholder="记录这张图的问题或亮点（腿/脚/袜、画风、构图…）；留空且不勾选，保存即清除 feedback"
            className="w-full rounded-xl p-3 text-sm text-rose-700/80 resize-none focus:outline-none"
            style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.25)" }}
          />

          <label className="flex items-center gap-2 mt-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={legFootBad}
              onChange={(e) => setLegFootBad(e.target.checked)}
              className="w-4 h-4 accent-rose-400"
            />
            <span
              className="text-sm font-medium text-rose-600"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              腿脚崩坏
            </span>
            <span className="text-xs text-rose-300/60">（计入 Case 的 bad 计数）</span>
          </label>

          {error && (
            <p className="mt-2 text-xs text-rose-600" role="alert">
              {error}
            </p>
          )}
        </div>

        <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />
        <div className="flex gap-3 p-4">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="flex-1 py-2.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "rgba(253,164,175,0.08)",
              color: "#f472b6",
              border: "1px solid rgba(244,114,182,0.2)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              opacity: saving ? 0.5 : 1,
            }}
          >
            取消
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

（`useState`/`useCallback` 由 auto-import 提供，不手写 import。）

- [ ] **Step 2: BatchTaskCard 集成**

修改 `page/src/pages/home/components/BatchTaskCard.tsx`：

1. 导入区加：

```tsx
import ImageFeedbackModal from "./ImageFeedbackModal";
```

2. Props 接口加一项：

```tsx
interface BatchTaskCardProps {
  task: BatchTask;
  index: number;
  onDelete: (taskId: string) => void | Promise<void>;
  onMarkUsed: (taskId: string) => void | Promise<void>;
  onSaveFeedback: (
    taskId: string,
    img: QuickCreateImage,
    feedbackText: string,
    legFootBad: boolean
  ) => Promise<void>;
}
```

组件签名同步解构 `onSaveFeedback`。

3. 组件内加状态（`showDetail` 声明附近）：

```tsx
  const [feedbackTarget, setFeedbackTarget] = useState<QuickCreateImage | null>(null);
```

4. 展开区图片网格（`task.images.map((img, imgIdx) => (...))` 内），在「AI 评论」按钮
   `{img.aiComment && (...)}` 的**前面**（同层级）加左下角 feedback 按钮：

```tsx
                  {task.quickCreateRecordId && typeof img.imageIndex === "number" && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFeedbackTarget(img);
                      }}
                      className="absolute bottom-2 left-2 z-10 flex items-center gap-1 px-2.5 py-1 rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap hover:opacity-90 pointer-events-auto"
                      style={{
                        fontFamily: "'ZCOOL KuaiLe', cursive",
                        ...(img.userFeedback
                          ? {
                              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                              color: "white",
                              boxShadow: "0 2px 10px rgba(244,114,182,0.4)",
                            }
                          : {
                              background: "rgba(255,255,255,0.85)",
                              color: "#f472b6",
                              border: "1px solid rgba(244,114,182,0.35)",
                            }),
                      }}
                    >
                      <span className="w-3 h-3 flex items-center justify-center" aria-hidden>
                        <i className="ri-feedback-line text-xs"></i>
                      </span>
                      {img.userFeedback ? "已反馈" : "反馈"}
                    </button>
                  )}
```

5. 弹窗渲染，放在 `{showDetail && ...}` 一行之后：

```tsx
      {feedbackTarget && (
        <ImageFeedbackModal
          image={feedbackTarget}
          promptTitle={promptTitleForBatchImage(task, feedbackTarget)}
          onSave={(text, bad) => onSaveFeedback(task.id, feedbackTarget, text, bad)}
          onClose={() => setFeedbackTarget(null)}
        />
      )}
```

6. 删除确认弹窗文案（`这会同步删除对应的 Prompt 预生成记录和美图创作记录，不可恢复哦～`）改为：

```tsx
                这会同步删除对应的 Prompt 预生成记录、美图创作记录和已填写的人工 feedback，不可恢复哦～想保留 feedback 请先导出～
```

注意：`feedbackTarget` 持有的是打开弹窗时的图片快照；保存成功后弹窗即关闭（Task 7 的页面回调会 patch 任务 state），下次打开拿到的是新数据，无一致性问题。

- [ ] **Step 3: 类型检查（预期此时报错）**

Run: `cd page; npm run type-check`
Expected: FAIL — `BatchCreationPage.tsx` 中 `<BatchTaskCard>` 缺少 `onSaveFeedback` 属性。这是 Task 7 要补的接线；**除该错误外不应有其他错误**。若出现其他错误，先修复再进入 Task 7。

- [ ] **Step 4: 提交**

```bash
git add page/src/pages/home/components/ImageFeedbackModal.tsx page/src/pages/home/components/BatchTaskCard.tsx
git commit -m "feat(page): 产线出图逐图人工 feedback 填写弹窗与入口"
```

---

### Task 7: BatchCreationPage 接线（保存回调 + 一键导出）+ 全量验证

**Files:**
- Modify: `page/src/pages/home/components/BatchCreationPage.tsx`

**Interfaces:**
- Consumes: Task 5 的 `creationApi.saveImageFeedback` / `creationApi.exportImageFeedback`；Task 6 的 `onSaveFeedback` prop 契约。
- Produces: 完整可用的功能闭环。

- [ ] **Step 1: 保存回调 + patch 本地 state**

修改 `page/src/pages/home/components/BatchCreationPage.tsx`：

1. 导入区加：

```tsx
import type { QuickCreateImage } from "@/types/quickCreate";
```

（`creationApi`、`ApiError` 已有导入，无需重复。）

2. 在 `handleMarkUsed` 之后加：

```tsx
  const handleSaveFeedback = useCallback(
    async (taskId: string, img: QuickCreateImage, feedbackText: string, legFootBad: boolean) => {
      const task = tasks.find((t) => t.id === taskId);
      if (!task?.quickCreateRecordId) {
        throw new ApiError("该记录缺少美图创作任务，无法保存 feedback", 400);
      }
      if (typeof img.imageIndex !== "number") {
        throw new ApiError("图片索引缺失，无法保存 feedback", 400);
      }
      const text = feedbackText.trim();
      await creationApi.saveImageFeedback(task.quickCreateRecordId, img.promptId, img.imageIndex, {
        feedback_text: text,
        leg_foot_bad: legFootBad,
      });
      const filled = text.length > 0 || legFootBad;
      const nextFb = filled ? { feedbackText: text, legFootBad } : null;
      const patchImg = (im: QuickCreateImage) =>
        im.id === img.id ? { ...im, userFeedback: nextFb } : im;
      setTasks((prev) =>
        prev.map((t) =>
          t.id !== taskId
            ? t
            : {
                ...t,
                images: t.images.map(patchImg),
                groups: t.groups.map((g) => ({ ...g, images: g.images.map(patchImg) })),
              }
        )
      );
    },
    [tasks]
  );
```

3. `tasks.map((task, idx) => (<BatchTaskCard ...` 处传入新 prop：

```tsx
              <BatchTaskCard
                key={task.id}
                task={task}
                index={idx}
                onDelete={handleDeleteTask}
                onMarkUsed={handleMarkUsed}
                onSaveFeedback={handleSaveFeedback}
              />
```

- [ ] **Step 2: 一键导出按钮**

1. 状态区（`fixedSeedUsedFlags` 声明附近）加：

```tsx
  const [exportingFeedback, setExportingFeedback] = useState(false);
  const [exportHint, setExportHint] = useState<string | null>(null);
```

2. `handleSaveFeedback` 之后加：

```tsx
  const handleExportFeedback = useCallback(async () => {
    setExportingFeedback(true);
    setExportHint(null);
    try {
      const payload = await creationApi.exportImageFeedback();
      if (payload.records.length === 0) {
        setExportHint("还没有已填写的 feedback～");
        return;
      }
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const now = new Date();
      const pad = (n: number) => String(n).padStart(2, "0");
      a.href = url;
      a.download = `feedback_export_${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setExportHint(`已导出 ${payload.records.length} 条产线的 feedback 记录`);
    } catch (e) {
      setExportHint(e instanceof ApiError ? e.message : "导出失败，请重试");
    } finally {
      setExportingFeedback(false);
    }
  }, []);
```

3. 「产线产出」标题行（`{tasks.length} 条产线记录` 的 span 所在 `<div className="flex items-center gap-2">` 之后、外层 `flex items-center justify-between` 之内）加按钮与提示：

```tsx
              <div className="flex items-center gap-2">
                {exportHint && (
                  <span className="text-xs text-rose-400/70">{exportHint}</span>
                )}
                <button
                  type="button"
                  onClick={() => void handleExportFeedback()}
                  disabled={exportingFeedback}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
                  style={{
                    background: "rgba(253,164,175,0.1)",
                    border: "1px solid rgba(253,164,175,0.2)",
                    color: "#f472b6",
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    opacity: exportingFeedback ? 0.5 : 1,
                  }}
                >
                  <i className="ri-download-2-line text-xs"></i>
                  {exportingFeedback ? "导出中…" : "导出 Feedback JSON"}
                </button>
              </div>
```

- [ ] **Step 3: 前端验证**

Run: `cd page; npm run type-check; npm run lint`
Expected: 两者均通过、无错误

- [ ] **Step 4: 后端全量回归**

Run: `python -m pytest`
Expected: 全部 PASS（不允许任何既有测试回归）

- [ ] **Step 5: 提交**

```bash
git add page/src/pages/home/components/BatchCreationPage.tsx
git commit -m "feat(page): 灵感工坊 feedback 保存接线与一键导出 JSON"
```

---

## 验收对照（spec → task）

| Spec 条目 | Task |
|---|---|
| §1 数据模型/唯一约束/清空即删/create_all | 1, 2 |
| §1 删除联动（服务层显式）+ 弹窗文案 | 2, 6 |
| §2.1 PUT 保存（404/422/清除语义） | 4 |
| §2.2 items-hydrated 附 feedbacks | 4, 5 |
| §2.3 导出 JSON（schema/字段/回落/坏数据跳过/空 records） | 3, 4 |
| §3.1 逐图入口 + 弹窗 + 已填态 + 就地 patch | 5, 6, 7 |
| §3.2 导出按钮 + Blob 下载 + 文件名 + 空提示 + 防重复 | 7 |
| §5 错误处理（弹窗内报错不丢输入） | 6 |
| §6 测试（repo/service/导出/路由 + type-check/lint） | 1-4, 5, 7 |
| §4 Case 映射 | 无代码任务（归档时由 Claude 按 spec 执行） |
