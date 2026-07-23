# 视频创作模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增第四大模块「视频创作」：以灵感产线美图为基底，编排居家风格文生视频 Prompt，调用 Seedance 2.0 生成 4–15 秒角色居家动态写真短视频，落盘保存并提供作品库。

**Architecture:** 独立模块，完整复刻现有分层（route → service → repository → model + schema）。后台串行任务：TOS 上传参考图 → Seedance 提交轮询 → 下载视频落盘 → finally 清理 TOS。复用 `TosStorageClient`（云存储）与 `yibu_gemini_infer`（LLM 文本推理）。Seedance 配置独立于 yibu，走 `.env`。

**Tech Stack:** FastAPI + SQLAlchemy(SQLite/WAL) + Pydantic 后端；React 19 + TypeScript + Vite + Tailwind 前端；`volcengine-python-sdk[ark]`（Seedance）、`python-dotenv`（配置加载）。

## Global Constraints

- 所有 API 响应包 `ApiResponse(success, data, message)`；路由前缀 `/api/video`。
- 数据库无 Alembic：新表靠 `Base.metadata.create_all` + `init_db()` 内 inline migration 幂等确保；新增列靠 `migrate_*` 函数检查列存在后 `ALTER TABLE`。
- 后台任务用 `BackgroundSessionLocal`（NullPool），绝不用请求作用域 session。
- 数据目录：`data/video/tasks/{task_id}/`，删任务连目录删。
- 视频内容纲领（约束 LLM Prompt）：两大核心主题=居家高级动态瞬间 + 自然展示腿脚/袜子；4–15 秒；高审美镜头感；拒绝长剧情/复杂分镜/复杂动作/唱跳/做饭家务。腿脚/袜子自然展示是核心竞争力，不得违反。
- 并发：串行单任务。存在 in-flight（`pending`/`uploading`/`generating`/`downloading`）视频任务时，新 `submit` 返回 HTTP 409。
- Seedance 配置（`app/tools/llm/seedance.py` 内 `os.environ.get(key, default)` 读取）：`SEEDANCE_BASE_URL` 默认 `https://ark.cn-beijing.volces.com/api/v3`；`SEEDANCE_MODEL` 默认 `doubao-seedance-2-0-260128`；`SEEDANCE_API_KEY` 无默认、必填、缺失时提交报明确错误。
- 原有 yibu 配置（`app/tools/llm/config.py`、`app/tools/beautify/config.py`）保持原样，不迁移。
- 任务 ID 前缀：`vid_` + `uuid4().hex[:12]`。
- 前端：`npm run type-check` 需显式 import React hooks（仓库惯例）。

---

## File Structure

**后端新建：**
- `app/models/video.py` — `VideoCreationTask` 模型
- `app/repositories/video_repository.py` — `VideoRepository(BaseRepository[VideoCreationTask])`
- `app/schemas/video.py` — Pydantic 请求/响应
- `app/tools/llm/seedance.py` — Ark SDK 封装（提交/轮询/下载 + ratio 常量表）
- `app/services/video_service/__init__.py`
- `app/services/video_service/exceptions.py` — `VideoConflictError` / `VideoNotFoundError` / `VideoError`
- `app/services/video_service/prompt_service.py` — LLM Prompt 编排（recommend/optimize）
- `app/services/video_service/runner.py` — 后台任务全链路
- `app/services/video_service/video_service.py` — 任务编排（import/submit/status/list/delete）
- `app/prompts/video/__init__.py`
- `app/prompts/video/recommend.py` — 模式 A 模板
- `app/prompts/video/optimize.py` — 模式 B 模板
- `.env.example` — Seedance 键占位

**后端修改：**
- `requirements.txt` — 加 `volcengine-python-sdk[ark]`、`python-dotenv`
- `app/services/directory_service.py` — 加 `get_video_dir()` / `get_video_task_dir()` + 初始化
- `app/models/database.py` — `init_db()` 导入 `VideoCreationTask` + 加 migration 调用
- `app/services/startup_image_tasks.py` — 重启时把 in-flight 视频任务置 failed
- `app/main.py` — 注册 `video.router`（前缀 `/api/video`）+ 轮询日志抑制
- `app/routes/video.py` — 新建路由

**前端新建：**
- `page/src/types/video.ts`
- `page/src/services/videoApi.ts`
- `page/src/pages/video/page.tsx` + `components/`（参考图区/Prompt 工作台/参数提交/历史列表）

**前端修改：**
- `page/src/router/config.tsx` — 加 `/video` 路由
- 首页导航组件 — 加第四模块入口
- `page/src/pages/home/components/BatchTaskCard.tsx` — 产出图加「去创作视频」按钮

**测试新建：**
- `tests/test_seedance_tool.py`
- `tests/test_video_repository.py`
- `tests/test_video_service.py`
- `tests/test_video_runner.py`
- `tests/test_video_routes.py`

---

## Task 1: Seedance 工具封装（`seedance.py`）

**Files:**
- Create: `app/tools/llm/seedance.py`
- Test: `tests/test_seedance_tool.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces:
  - `SUPPORTED_RATIOS: list[str]`（如 `["16:9","4:3","1:1","3:4","9:16","21:9"]`，实现时以官方文档核对）
  - `pick_closest_ratio(width: int, height: int) -> str`
  - `class SeedanceResult` — 字段 `status: str`（`"running"|"succeeded"|"failed"`）、`video_url: str | None`、`error: str | None`
  - `class SeedanceClient` — `submit(prompt: str, image_url: str, *, image_role: str, duration: int, generate_audio: bool, ratio: str) -> str`（返回 seedance task id）、`poll(task_id: str) -> SeedanceResult`
  - `get_default_seedance_client() -> SeedanceClient`
  - `download_video(video_url: str, dest_path: str) -> None`

- [ ] **Step 1: 写失败测试 — ratio 选择**

创建 `tests/test_seedance_tool.py`：

```python
import pytest

from app.tools.llm.seedance import pick_closest_ratio, SUPPORTED_RATIOS


def test_supported_ratios_nonempty():
    assert "3:4" in SUPPORTED_RATIOS
    assert "16:9" in SUPPORTED_RATIOS


@pytest.mark.parametrize(
    "w,h,expected",
    [
        (1080, 1440, "3:4"),   # 竖图
        (1920, 1080, "16:9"),  # 横图
        (1000, 1000, "1:1"),   # 方图
        (1080, 1920, "9:16"),  # 长竖
    ],
)
def test_pick_closest_ratio(w, h, expected):
    assert pick_closest_ratio(w, h) == expected


def test_pick_closest_ratio_zero_height_falls_back():
    assert pick_closest_ratio(100, 0) == "1:1"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_seedance_tool.py -v`
Expected: FAIL（`ModuleNotFoundError` 或 `ImportError: cannot import name`）

- [ ] **Step 3: 加依赖**

在 `requirements.txt` 末尾追加两行：

```
volcengine-python-sdk[ark]
python-dotenv
```

- [ ] **Step 4: 实现 `seedance.py`**

创建 `app/tools/llm/seedance.py`：

```python
import logging
import os
import threading
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedance-2-0-260128"

# 模型支持的长宽比（实现时以火山引擎官方文档核对增删）
SUPPORTED_RATIOS = ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9"]


def _ratio_value(ratio: str) -> float:
    w, h = ratio.split(":")
    return int(w) / int(h)


def pick_closest_ratio(width: int, height: int) -> str:
    if not width or not height:
        return "1:1"
    target = width / height
    return min(SUPPORTED_RATIOS, key=lambda r: abs(_ratio_value(r) - target))


@dataclass
class SeedanceResult:
    status: str  # "running" | "succeeded" | "failed"
    video_url: str | None = None
    error: str | None = None


def _get_config() -> tuple[str, str, str]:
    base_url = os.environ.get("SEEDANCE_BASE_URL", DEFAULT_BASE_URL)
    model = os.environ.get("SEEDANCE_MODEL", DEFAULT_MODEL)
    api_key = os.environ.get("SEEDANCE_API_KEY", "")
    return base_url, model, api_key


class SeedanceClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None):
        cfg_base, cfg_model, cfg_key = _get_config()
        self._base_url = base_url or cfg_base
        self._model = model or cfg_model
        self._api_key = api_key or cfg_key
        self._client = None

    def _ark(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("SEEDANCE_API_KEY 未配置，无法调用视频生成模型")
            from volcenginesdkarkruntime import Ark

            self._client = Ark(base_url=self._base_url, api_key=self._api_key)
        return self._client

    def submit(
        self,
        prompt: str,
        image_url: str,
        *,
        image_role: str,
        duration: int,
        generate_audio: bool,
        ratio: str,
    ) -> str:
        image_item = {"type": "image_url", "image_url": {"url": image_url}}
        if image_role == "reference_image":
            image_item["role"] = "reference_image"
        # image_role == "first_frame" 时不带 role，图片作为视频首帧
        result = self._ark().content_generation.tasks.create(
            model=self._model,
            content=[{"type": "text", "text": prompt}, image_item],
            generate_audio=generate_audio,
            ratio=ratio,
            duration=duration,
        )
        return result.id

    def poll(self, task_id: str) -> SeedanceResult:
        res = self._ark().content_generation.tasks.get(task_id=task_id)
        status = res.status
        if status == "succeeded":
            video_url = getattr(res.content, "video_url", None) if res.content else None
            return SeedanceResult(status="succeeded", video_url=video_url)
        if status == "failed":
            return SeedanceResult(status="failed", error=str(res.error))
        return SeedanceResult(status="running")


_default_lock = threading.Lock()
_default_client: SeedanceClient | None = None


def get_default_seedance_client() -> SeedanceClient:
    global _default_client
    if _default_client is None:
        with _default_lock:
            if _default_client is None:
                _default_client = SeedanceClient()
    return _default_client


def download_video(video_url: str, dest_path: str) -> None:
    with requests.get(video_url, stream=True, timeout=120) as resp:
        if not resp.ok:
            body = (resp.text or "")[:500]
            raise RuntimeError(f"视频下载失败 HTTP {resp.status_code}: {body}")
        with open(dest_path, "wb") as out:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    out.write(chunk)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_seedance_tool.py -v`
Expected: PASS（全部）

- [ ] **Step 6: 提交**

```bash
git add app/tools/llm/seedance.py tests/test_seedance_tool.py requirements.txt
git commit -m "feat(video): Seedance 2.0 工具封装（提交/轮询/下载 + ratio 选择）"
```

---

## Task 2: 数据模型 + Repository

**Files:**
- Create: `app/models/video.py`, `app/repositories/video_repository.py`
- Test: `tests/test_video_repository.py`
- Modify: `app/models/database.py`

**Interfaces:**
- Produces:
  - `VideoCreationTask`（表 `video_creation_tasks`），列见下方。
  - `VideoRepository(db)` 继承 `BaseRepository[VideoCreationTask]`；新增 `get_inflight() -> Optional[VideoCreationTask]`（status 在 `pending/uploading/generating/downloading`）。
- Consumes: `BaseRepository`（`get_by_id`/`create`/`update`/`delete`/`list_all`）。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_video_repository.py`：

```python
from app.models.database import SessionLocal, init_db
from app.repositories.video_repository import VideoRepository


def _make_task(repo, task_id, status="draft"):
    return repo.create(
        {
            "id": task_id,
            "source_kind": "upload",
            "ref_image_path": f"data/video/tasks/{task_id}/ref.png",
            "image_role": "first_frame",
            "duration": 8,
            "generate_audio": False,
            "ratio": "3:4",
            "status": status,
        }
    )


def test_create_and_get():
    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _make_task(repo, "vid_repo_a")
        row = repo.get_by_id("vid_repo_a")
        assert row is not None
        assert row.source_kind == "upload"
        assert row.status == "draft"
        assert row.generate_audio is False
    finally:
        repo.delete("vid_repo_a")
        db.close()


def test_get_inflight_only_matches_running_states():
    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _make_task(repo, "vid_repo_b", status="generating")
        assert repo.get_inflight() is not None
        repo.update("vid_repo_b", {"status": "completed"})
        assert repo.get_inflight() is None
    finally:
        repo.delete("vid_repo_b")
        db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_video_repository.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.video`）

- [ ] **Step 3: 实现模型**

创建 `app/models/video.py`：

```python
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.models.database import Base


class VideoCreationTask(Base):
    __tablename__ = "video_creation_tasks"

    id = Column(String(40), primary_key=True)

    source_kind = Column(String(20), nullable=False)  # upload | quick_create
    source_task_id = Column(String(64), nullable=True, index=True)
    source_image_path = Column(Text, nullable=True)

    ref_image_path = Column(Text, nullable=False)
    ref_prompt_text = Column(Text, nullable=True)
    video_prompt_text = Column(Text, nullable=True)
    prompt_mode = Column(String(20), nullable=True)  # llm | manual

    image_role = Column(String(20), nullable=False, default="first_frame")
    duration = Column(Integer, nullable=False, default=8)
    generate_audio = Column(Boolean, nullable=False, default=False)
    ratio = Column(String(16), nullable=False, default="1:1")

    status = Column(String(20), nullable=False, default="draft", index=True)

    prompt_job_status = Column(String(20), nullable=True)  # pending|running|completed|failed
    prompt_job_result = Column(Text, nullable=True)
    prompt_job_error = Column(Text, nullable=True)

    seedance_task_id = Column(String(64), nullable=True, index=True)
    video_filename = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_video_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<VideoCreationTask(id={self.id!r}, status={self.status!r})>"
```

- [ ] **Step 4: 实现 Repository**

创建 `app/repositories/video_repository.py`：

```python
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.video import VideoCreationTask
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

_INFLIGHT_STATES = ("pending", "uploading", "generating", "downloading")


class VideoRepository(BaseRepository[VideoCreationTask]):
    def __init__(self, db: Session):
        super().__init__(db, VideoCreationTask)

    def get_inflight(self) -> Optional[VideoCreationTask]:
        return (
            self.db.query(VideoCreationTask)
            .filter(VideoCreationTask.status.in_(_INFLIGHT_STATES))
            .order_by(VideoCreationTask.created_at.desc())
            .first()
        )
```

- [ ] **Step 5: 注册建表 + migration**

在 `app/models/database.py` 的 `init_db()` 中，模型导入区（`from app.models.creation_feedback import ...` 之后）加：

```python
        from app.models.video import VideoCreationTask  # noqa: F401
```

并在 `migrate_creation_image_feedbacks_recompute_leg_foot_bad()` 调用之后加：

```python
        migrate_create_video_creation_tasks()
```

在 `migrate_create_material_seed_prompt_tasks` 附近（其他 create-table migration 旁）定义：

```python
def migrate_create_video_creation_tasks() -> None:
    """创建 video_creation_tasks 表（幂等：依赖 create_all）。"""
    from app.models.video import VideoCreationTask  # noqa: F401

    logger.info("migrate: video_creation_tasks ensured")
```

- [ ] **Step 6: 运行确认通过**

Run: `pytest tests/test_video_repository.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add app/models/video.py app/repositories/video_repository.py app/models/database.py tests/test_video_repository.py
git commit -m "feat(video): VideoCreationTask 模型 + Repository + 建表迁移"
```

---

## Task 3: Schemas + 目录服务

**Files:**
- Create: `app/schemas/video.py`
- Modify: `app/services/directory_service.py`
- Test: `tests/test_video_service.py`（本任务只加目录测试；service 测试在 Task 5 补）

**Interfaces:**
- Produces（`app/schemas/video.py`）:
  - `ApiResponse(success: bool, data: object|None, message: str|None)`
  - `VideoImportBody`（JSON 导入）: `source_kind: Literal["quick_create"]`、`source_task_id: str`、`source_image_path: str`、`ref_prompt_text: str | None`
  - `PromptJobBody`: `mode: Literal["recommend","optimize"]`、`manual_prompt: str | None`
  - `VideoSubmitBody`: `video_prompt_text: str`、`image_role: Literal["first_frame","reference_image"]`、`duration: int (Field ge=4, le=15)`、`generate_audio: bool`、`ratio: str`
  - `VideoTaskData`（响应 DTO，见下）
- Produces（`directory_service.py`）:
  - `get_video_dir() -> str` → `data/video`
  - `get_video_tasks_dir() -> str` → `data/video/tasks`
  - `get_video_task_dir(task_id: str) -> str` → `data/video/tasks/{task_id}`

- [ ] **Step 1: 写失败测试（目录）**

创建 `tests/test_video_service.py`（先只放目录测试）：

```python
import os

from app.services import directory_service


def test_video_task_dir_layout():
    d = directory_service.get_video_task_dir("vid_dir_x")
    assert d.replace("\\", "/").endswith("data/video/tasks/vid_dir_x")


def test_video_dirs_created_on_init(tmp_path, monkeypatch):
    monkeypatch.setattr(directory_service, "DATA_DIR", str(tmp_path))
    directory_service.initialize_data_directory()
    assert os.path.isdir(directory_service.get_video_tasks_dir())
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_video_service.py -v`
Expected: FAIL（`AttributeError: module ... has no attribute 'get_video_task_dir'`）

- [ ] **Step 3: 实现目录服务**

在 `app/services/directory_service.py` 的 `get_beautify_dir()` 之后加：

```python
def get_video_dir() -> str:
    """获取视频创作模块目录（data/video）"""
    return os.path.join(get_data_dir(), "video")


def get_video_tasks_dir() -> str:
    """获取视频任务根目录（data/video/tasks）"""
    return os.path.join(get_video_dir(), "tasks")


def get_video_task_dir(task_id: str) -> str:
    """单个视频任务工作目录（data/video/tasks/{task_id}）"""
    return os.path.join(get_video_tasks_dir(), task_id)
```

在 `initialize_data_directory()` 中，`ensure_dir_exists(get_beautify_dir())` 一行之后加：

```python
    ensure_dir_exists(get_video_tasks_dir())
```

- [ ] **Step 4: 实现 schemas**

创建 `app/schemas/video.py`：

```python
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool
    data: Optional[object] = None
    message: Optional[str] = None


class VideoImportBody(BaseModel):
    source_kind: Literal["quick_create"]
    source_task_id: str
    source_image_path: str
    ref_prompt_text: Optional[str] = None


class PromptJobBody(BaseModel):
    mode: Literal["recommend", "optimize"]
    manual_prompt: Optional[str] = None


class VideoSubmitBody(BaseModel):
    video_prompt_text: str
    image_role: Literal["first_frame", "reference_image"] = "first_frame"
    duration: int = Field(default=8, ge=4, le=15)
    generate_audio: bool = False
    ratio: str


class VideoTaskData(BaseModel):
    task_id: str
    source_kind: str
    status: str
    image_role: str
    duration: int
    generate_audio: bool
    ratio: str
    ref_prompt_text: Optional[str] = None
    video_prompt_text: Optional[str] = None
    prompt_mode: Optional[str] = None
    prompt_job_status: Optional[str] = None
    prompt_job_result: Optional[str] = None
    prompt_job_error: Optional[str] = None
    video_filename: Optional[str] = None
    error_message: Optional[str] = None
    recommended_ratio: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/test_video_service.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add app/schemas/video.py app/services/directory_service.py tests/test_video_service.py
git commit -m "feat(video): schemas + 视频数据目录服务"
```

---

## Task 4: LLM Prompt 编排（模板 + prompt_service）

**Files:**
- Create: `app/prompts/video/__init__.py`, `app/prompts/video/recommend.py`, `app/prompts/video/optimize.py`, `app/services/video_service/__init__.py`, `app/services/video_service/prompt_service.py`
- Test: `tests/test_video_service.py`（追加）

**Interfaces:**
- Produces:
  - `recommend.RECOMMEND_PROMPT: str`（含 `{ref_prompt}` 占位）
  - `optimize.OPTIMIZE_PROMPT: str`（含 `{manual_prompt}` 占位）
  - `VideoPromptService(db)`:
    - `start_job(task_id: str, mode: str, manual_prompt: str | None, background_tasks) -> dict`
    - `run_prompt_job_sync(task_id: str, mode: str, manual_prompt: str | None, session_factory, *, infer=None) -> None`（`infer` 默认 `yibu_gemini_infer`，可注入 mock）
- Consumes: `VideoRepository`、`yibu_gemini_infer(prompt, image_path=..., thinking_level=...)`、`get_video_task_dir`。

- [ ] **Step 1: 写失败测试（注入 fake infer）**

在 `tests/test_video_service.py` 追加：

```python
from app.models.database import SessionLocal, init_db
from app.repositories.video_repository import VideoRepository


def _seed_draft(repo, task_id):
    return repo.create(
        {
            "id": task_id,
            "source_kind": "upload",
            "ref_image_path": f"data/video/tasks/{task_id}/ref.png",
            "image_role": "first_frame",
            "duration": 8,
            "generate_audio": False,
            "ratio": "3:4",
            "status": "draft",
        }
    )


def test_prompt_job_recommend_writes_result():
    from app.services.video_service.prompt_service import VideoPromptService

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed_draft(repo, "vid_pj_a")
        svc = VideoPromptService(db)
        svc.run_prompt_job_sync(
            "vid_pj_a", "recommend", None, SessionLocal,
            infer=lambda *a, **k: "温暖居家的动态镜头，脚尖轻点。",
        )
        row = repo.get_by_id("vid_pj_a")
        assert row.prompt_job_status == "completed"
        assert "脚尖" in row.prompt_job_result
    finally:
        repo.delete("vid_pj_a")
        db.close()


def test_prompt_job_optimize_uses_manual_prompt():
    from app.services.video_service.prompt_service import VideoPromptService

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed_draft(repo, "vid_pj_b")
        seen = {}
        def fake_infer(prompt, **k):
            seen["prompt"] = prompt
            return "优化后的 prompt"
        svc = VideoPromptService(db)
        svc.run_prompt_job_sync(
            "vid_pj_b", "optimize", "我的原始想法", SessionLocal, infer=fake_infer
        )
        assert "我的原始想法" in seen["prompt"]
        assert repo.get_by_id("vid_pj_b").prompt_job_status == "completed"
    finally:
        repo.delete("vid_pj_b")
        db.close()


def test_prompt_job_failure_records_error():
    from app.services.video_service.prompt_service import VideoPromptService

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed_draft(repo, "vid_pj_c")
        def boom(*a, **k):
            raise RuntimeError("LLM 挂了")
        svc = VideoPromptService(db)
        svc.run_prompt_job_sync("vid_pj_c", "recommend", None, SessionLocal, infer=boom)
        row = repo.get_by_id("vid_pj_c")
        assert row.prompt_job_status == "failed"
        assert "LLM 挂了" in row.prompt_job_error
    finally:
        repo.delete("vid_pj_c")
        db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_video_service.py -k prompt_job -v`
Expected: FAIL（`ModuleNotFoundError: app.services.video_service.prompt_service`）

- [ ] **Step 3: 实现模板**

创建 `app/prompts/video/__init__.py`（空文件）。

创建 `app/prompts/video/recommend.py`：

```python
RECOMMEND_PROMPT = """你是一位擅长「居家动态写真」文生视频提示词的导演。请根据我提供的角色参考图（以及可能的生图提示词），创作一套用于 Seedance 文生视频模型的中文提示词。

【两大核心主题】（必须同时满足）
1. 角色居家高级动态瞬间：温馨、有氛围、有生活质感的居家场景。
2. 自然展示角色的腿脚 / 袜子：这是核心竞争力，构图与镜头必须自然地让腿脚/袜子处于画面中，但不得刻意、不得低俗。

【硬性要求】
- 时长感 4–15 秒的单一连续片段，高审美、有镜头感。
- 只写一个简洁的动态瞬间，不要故事化长剧情、不要复杂分镜、不要复杂动作。
- 明确禁止：唱歌、跳舞、做饭、家务等低质俗套内容。

【推荐创作方向（任选贴合参考图的一种）】
- 自然动态展示：呼吸、眨眼、发丝浮动、简单动作、与场景的轻互动。
- 场景氛围：镜头推拉环绕、环境动态（光影/窗帘/尘埃）、真实世界感。
- 服装美学展示：轻微转身、衣摆飘动、细节扫镜。
- 镜头微互动：观众视角在角色面前与角色的轻微互动。

【生图提示词参考（可能为空）】
{ref_prompt}

请只输出最终的视频提示词正文，中文，一段连续文字，不要标题、不要解释、不要分点。"""
```

创建 `app/prompts/video/optimize.py`：

```python
OPTIMIZE_PROMPT = """你是一位擅长「居家动态写真」文生视频提示词的导演。下面是用户手写的视频提示词草稿，请在**保留其核心意图与画面要素**的前提下，按下述纲领润色其镜头语言与动态描述，使其更适合 Seedance 文生视频模型。

【两大核心主题】（必须保持）
1. 角色居家高级动态瞬间。
2. 自然展示角色的腿脚 / 袜子（核心竞争力，自然而非低俗）。

【硬性要求】
- 时长感 4–15 秒的单一连续片段，高审美、有镜头感。
- 简洁的动态瞬间，不要故事化长剧情、复杂分镜、复杂动作。
- 明确禁止：唱歌、跳舞、做饭、家务等低质俗套内容。

【用户草稿】
{manual_prompt}

请只输出润色后的视频提示词正文，中文，一段连续文字，不要标题、不要解释、不要分点。"""
```

- [ ] **Step 4: 实现 prompt_service**

创建 `app/services/video_service/__init__.py`（空文件）。

创建 `app/services/video_service/prompt_service.py`：

```python
import asyncio
import logging
import os
from typing import Any, Callable, Dict, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import BackgroundSessionLocal
from app.prompts.video.optimize import OPTIMIZE_PROMPT
from app.prompts.video.recommend import RECOMMEND_PROMPT
from app.repositories.video_repository import VideoRepository
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

logger = logging.getLogger(__name__)


class VideoPromptService:
    def __init__(self, db: Session, *, session_factory=BackgroundSessionLocal):
        self.db = db
        self.repo = VideoRepository(db)
        self._session_factory = session_factory

    def start_job(
        self,
        task_id: str,
        mode: str,
        manual_prompt: Optional[str],
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        task = self.repo.get_by_id(task_id)
        if not task:
            raise FileNotFoundError("视频任务不存在")
        if task.prompt_job_status == "running":
            raise ValueError("已有 Prompt 作业进行中")
        if mode == "optimize" and not (manual_prompt and manual_prompt.strip()):
            raise ValueError("优化模式需要提供手写 Prompt")

        self.repo.update(
            task_id,
            {"prompt_job_status": "pending", "prompt_job_result": None, "prompt_job_error": None},
        )
        if background_tasks:
            background_tasks.add_task(self._run_async, task_id, mode, manual_prompt)
        else:
            self.run_prompt_job_sync(task_id, mode, manual_prompt, self._session_factory)
        return {"task_id": task_id, "prompt_job_status": "pending"}

    async def _run_async(self, task_id: str, mode: str, manual_prompt: Optional[str]) -> None:
        await asyncio.to_thread(
            self.run_prompt_job_sync, task_id, mode, manual_prompt, self._session_factory
        )

    def run_prompt_job_sync(
        self,
        task_id: str,
        mode: str,
        manual_prompt: Optional[str],
        session_factory,
        *,
        infer: Callable[..., str] | None = None,
    ) -> None:
        infer = infer or yibu_gemini_infer
        db = session_factory()
        try:
            repo = VideoRepository(db)
            task = repo.get_by_id(task_id)
            if not task:
                return
            repo.update(task_id, {"prompt_job_status": "running"})

            if mode == "optimize":
                prompt = OPTIMIZE_PROMPT.format(manual_prompt=manual_prompt or "")
                image_path = None
            else:
                prompt = RECOMMEND_PROMPT.format(ref_prompt=task.ref_prompt_text or "（无）")
                image_path = (
                    [task.ref_image_path]
                    if task.ref_image_path and os.path.exists(task.ref_image_path)
                    else None
                )

            result = infer(prompt, image_path=image_path, thinking_level="high")
            repo.update(
                task_id,
                {"prompt_job_status": "completed", "prompt_job_result": (result or "").strip()},
            )
        except Exception as exc:
            db.rollback()
            db2 = session_factory()
            try:
                VideoRepository(db2).update(
                    task_id,
                    {"prompt_job_status": "failed", "prompt_job_error": str(exc)[:500]},
                )
            finally:
                db2.close()
            logger.exception("video prompt job failed task_id=%s", task_id)
        finally:
            db.close()
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/test_video_service.py -k prompt_job -v`
Expected: PASS（3 个）

- [ ] **Step 6: 提交**

```bash
git add app/prompts/video/ app/services/video_service/__init__.py app/services/video_service/prompt_service.py tests/test_video_service.py
git commit -m "feat(video): LLM Prompt 编排模板 + prompt_service（recommend/optimize）"
```

---

## Task 5: 后台 Runner + 异常类

**Files:**
- Create: `app/services/video_service/exceptions.py`, `app/services/video_service/runner.py`
- Test: `tests/test_video_runner.py`

**Interfaces:**
- Produces:
  - `exceptions.py`: `VideoError`、`VideoConflictError(VideoError)`、`VideoNotFoundError(VideoError)`
  - `runner.run_video_task_sync(task_id: str, session_factory, *, storage=None, client=None, downloader=None) -> None`
    - `storage` 默认 `get_default_client()`（TOS）；`client` 默认 `get_default_seedance_client()`；`downloader` 默认 `download_video`。
    - 流程：`uploading`(TOS 上传) → `generating`(提交+30s 轮询, 超时 ~20min) → `downloading`(下载到 `data/video/tasks/{id}/output.mp4`) → `completed`；finally 删 TOS 对象。
- Consumes: `VideoRepository`、`TosStorageClient.upload_and_presign/delete`、`SeedanceClient.submit/poll`、`get_video_task_dir`。

- [ ] **Step 1: 写失败测试（全 fake 依赖）**

创建 `tests/test_video_runner.py`：

```python
import os

from app.models.database import SessionLocal, init_db
from app.repositories.video_repository import VideoRepository


class FakeStorage:
    def __init__(self):
        self.deleted = []
    def upload_and_presign(self, local_path, object_key=None):
        return ("obj/key.png", "https://signed.example/ref.png")
    def delete(self, object_key):
        self.deleted.append(object_key)


class FakeClient:
    def __init__(self, statuses):
        self._statuses = list(statuses)
        self.submitted = None
    def submit(self, prompt, image_url, *, image_role, duration, generate_audio, ratio):
        self.submitted = {"image_role": image_role, "ratio": ratio, "duration": duration}
        return "seed-123"
    def poll(self, task_id):
        from app.tools.llm.seedance import SeedanceResult
        return self._statuses.pop(0)


def _seed(repo, task_id, tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"x")
    return repo.create({
        "id": task_id, "source_kind": "upload", "ref_image_path": str(ref),
        "video_prompt_text": "温暖居家", "image_role": "first_frame",
        "duration": 8, "generate_audio": False, "ratio": "3:4", "status": "pending",
    })


def test_runner_success_downloads_and_cleans_tos(tmp_path, monkeypatch):
    from app.services.video_service import runner
    from app.services import directory_service
    from app.tools.llm.seedance import SeedanceResult

    monkeypatch.setattr(directory_service, "DATA_DIR", str(tmp_path))
    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed(repo, "vid_run_a", tmp_path)
        storage = FakeStorage()
        client = FakeClient([
            SeedanceResult(status="running"),
            SeedanceResult(status="succeeded", video_url="https://v.example/out.mp4"),
        ])
        downloaded = {}
        def fake_download(url, dest):
            downloaded["dest"] = dest
            with open(dest, "wb") as f:
                f.write(b"mp4")
        runner.run_video_task_sync(
            "vid_run_a", SessionLocal, storage=storage, client=client,
            downloader=fake_download, poll_interval=0,
        )
        row = repo.get_by_id("vid_run_a")
        assert row.status == "completed"
        assert row.video_filename == "output.mp4"
        assert storage.deleted == ["obj/key.png"]
        assert os.path.basename(downloaded["dest"]) == "output.mp4"
    finally:
        repo.delete("vid_run_a")
        db.close()


def test_runner_failure_records_error_and_cleans(tmp_path, monkeypatch):
    from app.services.video_service import runner
    from app.services import directory_service
    from app.tools.llm.seedance import SeedanceResult

    monkeypatch.setattr(directory_service, "DATA_DIR", str(tmp_path))
    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed(repo, "vid_run_b", tmp_path)
        storage = FakeStorage()
        client = FakeClient([SeedanceResult(status="failed", error="模型拒绝")])
        runner.run_video_task_sync(
            "vid_run_b", SessionLocal, storage=storage, client=client,
            downloader=lambda u, d: None, poll_interval=0,
        )
        row = repo.get_by_id("vid_run_b")
        assert row.status == "failed"
        assert "模型拒绝" in row.error_message
        assert storage.deleted == ["obj/key.png"]
    finally:
        repo.delete("vid_run_b")
        db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_video_runner.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.video_service.runner`）

- [ ] **Step 3: 实现异常类**

创建 `app/services/video_service/exceptions.py`：

```python
class VideoError(Exception):
    """视频创作模块通用异常"""


class VideoConflictError(VideoError):
    """存在冲突（如已有任务进行中）"""


class VideoNotFoundError(VideoError):
    """任务或资源不存在"""
```

- [ ] **Step 4: 实现 runner**

创建 `app/services/video_service/runner.py`：

```python
import logging
import os
import time

from app.repositories.video_repository import VideoRepository
from app.services import directory_service
from app.tools.beautify.storage import CloudStorageClient, get_default_client
from app.tools.llm.seedance import (
    SeedanceClient,
    download_video,
    get_default_seedance_client,
)

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 30
_TIMEOUT_SECONDS = 20 * 60
_OUTPUT_FILENAME = "output.mp4"


def run_video_task_sync(
    task_id: str,
    session_factory,
    *,
    storage: CloudStorageClient | None = None,
    client: SeedanceClient | None = None,
    downloader=None,
    poll_interval: int = _POLL_INTERVAL_SECONDS,
) -> None:
    storage = storage or get_default_client()
    client = client or get_default_seedance_client()
    downloader = downloader or download_video
    db = session_factory()
    cloud_object_key: str | None = None
    try:
        repo = VideoRepository(db)
        task = repo.get_by_id(task_id)
        if not task:
            return

        # 1) 上传参考图到 TOS
        repo.update(task_id, {"status": "uploading", "error_message": None})
        cloud_object_key, signed_url = storage.upload_and_presign(task.ref_image_path)

        # 2) 提交 Seedance + 轮询
        repo.update(task_id, {"status": "generating"})
        seed_id = client.submit(
            task.video_prompt_text or "",
            signed_url,
            image_role=task.image_role,
            duration=task.duration,
            generate_audio=task.generate_audio,
            ratio=task.ratio,
        )
        repo.update(task_id, {"seedance_task_id": seed_id})
        video_url = _poll_until_done(client, seed_id, poll_interval)

        # 3) 下载落盘
        repo.update(task_id, {"status": "downloading"})
        task_dir = directory_service.get_video_task_dir(task_id)
        os.makedirs(task_dir, exist_ok=True)
        dest = os.path.join(task_dir, _OUTPUT_FILENAME)
        downloader(video_url, dest)

        repo.update(
            task_id,
            {"status": "completed", "video_filename": _OUTPUT_FILENAME, "error_message": None},
        )
        logger.info("video completed task_id=%s", task_id)
    except Exception as exc:
        db.rollback()
        db2 = session_factory()
        try:
            VideoRepository(db2).update(
                task_id, {"status": "failed", "error_message": str(exc)[:500]}
            )
        finally:
            db2.close()
        logger.exception("video task failed task_id=%s err=%s", task_id, exc)
    finally:
        db.close()
        if cloud_object_key:
            try:
                storage.delete(cloud_object_key)
                logger.info("video cleanup: deleted TOS object %s", cloud_object_key)
            except Exception as cleanup_err:
                logger.warning(
                    "video cleanup failed object_key=%s err=%s", cloud_object_key, cleanup_err
                )


def _poll_until_done(client: SeedanceClient, seed_id: str, poll_interval: int) -> str:
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        result = client.poll(seed_id)
        if result.status == "running":
            if poll_interval:
                time.sleep(poll_interval)
            continue
        if result.status == "succeeded":
            if not result.video_url:
                raise RuntimeError("视频生成成功但缺少 video_url")
            return result.video_url
        raise RuntimeError(result.error or "视频生成任务失败")
    raise TimeoutError("视频生成超时")
```

- [ ] **Step 5: 运行确认通过**

Run: `pytest tests/test_video_runner.py -v`
Expected: PASS（2 个）

- [ ] **Step 6: 提交**

```bash
git add app/services/video_service/exceptions.py app/services/video_service/runner.py tests/test_video_runner.py
git commit -m "feat(video): 后台 Runner（TOS 上传→Seedance 轮询→下载→清理）+ 异常类"
```

---

## Task 6: VideoService 编排（import/submit/status/list/delete）

**Files:**
- Create: `app/services/video_service/video_service.py`
- Test: `tests/test_video_service.py`（追加）

**Interfaces:**
- Produces `VideoService(db, *, session_factory=BackgroundSessionLocal)`:
  - `import_from_quick_create(source_task_id, source_image_path, ref_prompt_text) -> dict`（复制产线图到任务目录，建 draft，返回含 `recommended_ratio`）
  - `import_from_upload(filename, content: bytes) -> dict`（保存上传图，建 draft）
  - `submit(task_id, *, video_prompt_text, image_role, duration, generate_audio, ratio, prompt_mode, background_tasks) -> dict`（串行校验，in-flight → `VideoConflictError`）
  - `get_status(task_id) -> dict | None`
  - `list_tasks() -> list[dict]`
  - `delete_task(task_id) -> None`（运行中 → `VideoConflictError`；删目录 + 删行）
  - `to_data(task) -> dict`（模型 → `VideoTaskData` dict）
- Consumes: `VideoRepository`、`CreationQuickCreateRepository`（校验源任务 + 定位产线图）、`get_video_task_dir`、`pick_closest_ratio`、`run_video_task_sync`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_video_service.py` 追加：

```python
def test_submit_conflict_when_inflight():
    from app.services.video_service.video_service import VideoService
    from app.services.video_service.exceptions import VideoConflictError
    import pytest as _pytest

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        # 一个占位 in-flight 任务
        repo.create({
            "id": "vid_inflight", "source_kind": "upload",
            "ref_image_path": "x", "image_role": "first_frame",
            "duration": 8, "generate_audio": False, "ratio": "3:4",
            "status": "generating",
        })
        # 另一个 draft，尝试提交应 409
        repo.create({
            "id": "vid_draft", "source_kind": "upload",
            "ref_image_path": "x", "image_role": "first_frame",
            "duration": 8, "generate_audio": False, "ratio": "3:4",
            "status": "draft",
        })
        svc = VideoService(db)
        with _pytest.raises(VideoConflictError):
            svc.submit(
                "vid_draft", video_prompt_text="p", image_role="first_frame",
                duration=8, generate_audio=False, ratio="3:4", prompt_mode="manual",
                background_tasks=None,
            )
    finally:
        repo.delete("vid_inflight")
        repo.delete("vid_draft")
        db.close()


def test_delete_running_task_rejected():
    from app.services.video_service.video_service import VideoService
    from app.services.video_service.exceptions import VideoConflictError
    import pytest as _pytest

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        repo.create({
            "id": "vid_del_run", "source_kind": "upload",
            "ref_image_path": "x", "image_role": "first_frame",
            "duration": 8, "generate_audio": False, "ratio": "3:4",
            "status": "downloading",
        })
        svc = VideoService(db)
        with _pytest.raises(VideoConflictError):
            svc.delete_task("vid_del_run")
    finally:
        repo.delete("vid_del_run")
        db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_video_service.py -k "conflict or delete_running" -v`
Expected: FAIL（`ModuleNotFoundError: app.services.video_service.video_service`）

- [ ] **Step 3: 实现 VideoService**

创建 `app/services/video_service/video_service.py`：

```python
import asyncio
import logging
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks
from PIL import Image
from sqlalchemy.orm import Session

from app.models.database import BackgroundSessionLocal
from app.repositories.creation_repository import CreationQuickCreateRepository
from app.repositories.video_repository import VideoRepository
from app.services import directory_service
from app.services.video_service.exceptions import VideoConflictError, VideoNotFoundError
from app.services.video_service.runner import run_video_task_sync
from app.tools.llm.seedance import pick_closest_ratio

logger = logging.getLogger(__name__)

_RUNNING_STATES = ("pending", "uploading", "generating", "downloading")


class VideoService:
    def __init__(self, db: Session, *, session_factory=BackgroundSessionLocal):
        self.db = db
        self.repo = VideoRepository(db)
        self.quick_repo = CreationQuickCreateRepository(db)
        self._session_factory = session_factory

    # ---------- import ----------
    def _new_task_id(self) -> str:
        return f"vid_{uuid.uuid4().hex[:12]}"

    def _recommended_ratio(self, image_path: str) -> str:
        try:
            with Image.open(image_path) as im:
                return pick_closest_ratio(im.width, im.height)
        except Exception:
            return "1:1"

    def import_from_quick_create(
        self, source_task_id: str, source_image_path: str, ref_prompt_text: Optional[str]
    ) -> Dict[str, Any]:
        source_task = self.quick_repo.get_by_id(source_task_id)
        if not source_task:
            raise VideoNotFoundError("源产线任务不存在")
        abs_src = os.path.join(source_task.work_dir, source_image_path)
        if not os.path.exists(abs_src):
            raise VideoNotFoundError("源图片不存在")

        task_id = self._new_task_id()
        task_dir = directory_service.get_video_task_dir(task_id)
        os.makedirs(task_dir, exist_ok=True)
        ext = os.path.splitext(abs_src)[1] or ".png"
        ref_path = os.path.join(task_dir, f"ref{ext}")
        shutil.copyfile(abs_src, ref_path)

        ratio = self._recommended_ratio(ref_path)
        task = self.repo.create({
            "id": task_id, "source_kind": "quick_create",
            "source_task_id": source_task_id, "source_image_path": source_image_path,
            "ref_image_path": ref_path, "ref_prompt_text": ref_prompt_text,
            "image_role": "first_frame", "duration": 8, "generate_audio": False,
            "ratio": ratio, "status": "draft",
        })
        data = self.to_data(task)
        data["recommended_ratio"] = ratio
        return data

    def import_from_upload(self, filename: str, content: bytes) -> Dict[str, Any]:
        task_id = self._new_task_id()
        task_dir = directory_service.get_video_task_dir(task_id)
        os.makedirs(task_dir, exist_ok=True)
        ext = os.path.splitext(filename)[1].lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError("仅支持 png/jpg/jpeg/webp 图片")
        ref_path = os.path.join(task_dir, f"ref{ext}")
        with open(ref_path, "wb") as f:
            f.write(content)

        ratio = self._recommended_ratio(ref_path)
        task = self.repo.create({
            "id": task_id, "source_kind": "upload",
            "ref_image_path": ref_path, "image_role": "first_frame",
            "duration": 8, "generate_audio": False, "ratio": ratio, "status": "draft",
        })
        data = self.to_data(task)
        data["recommended_ratio"] = ratio
        return data

    # ---------- submit ----------
    def submit(
        self,
        task_id: str,
        *,
        video_prompt_text: str,
        image_role: str,
        duration: int,
        generate_audio: bool,
        ratio: str,
        prompt_mode: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        task = self.repo.get_by_id(task_id)
        if not task:
            raise VideoNotFoundError("视频任务不存在")
        if task.status in _RUNNING_STATES:
            raise VideoConflictError("该任务已在生成中")
        if task.status == "completed":
            raise VideoConflictError("该任务已完成，请重新导入以创作新视频")

        inflight = self.repo.get_inflight()
        if inflight and inflight.id != task_id:
            raise VideoConflictError("已有视频任务进行中，请等待其完成")

        self.repo.update(task_id, {
            "video_prompt_text": video_prompt_text, "image_role": image_role,
            "duration": duration, "generate_audio": generate_audio, "ratio": ratio,
            "prompt_mode": prompt_mode, "status": "pending", "error_message": None,
        })
        if background_tasks:
            background_tasks.add_task(self._run_async, task_id)
        else:
            run_video_task_sync(task_id, self._session_factory)
        return self.get_status(task_id)

    async def _run_async(self, task_id: str) -> None:
        await asyncio.to_thread(run_video_task_sync, task_id, self._session_factory)

    # ---------- query / delete ----------
    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.repo.get_by_id(task_id)
        return self.to_data(task) if task else None

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [self.to_data(t) for t in self.repo.list_all(limit=200)]

    def delete_task(self, task_id: str) -> None:
        task = self.repo.get_by_id(task_id)
        if not task:
            raise VideoNotFoundError("视频任务不存在")
        if task.status in _RUNNING_STATES:
            raise VideoConflictError("任务生成中，无法删除")
        task_dir = directory_service.get_video_task_dir(task_id)
        if os.path.isdir(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
        self.repo.delete(task_id)

    def to_data(self, task) -> Dict[str, Any]:
        return {
            "task_id": task.id, "source_kind": task.source_kind, "status": task.status,
            "image_role": task.image_role, "duration": task.duration,
            "generate_audio": task.generate_audio, "ratio": task.ratio,
            "ref_prompt_text": task.ref_prompt_text, "video_prompt_text": task.video_prompt_text,
            "prompt_mode": task.prompt_mode, "prompt_job_status": task.prompt_job_status,
            "prompt_job_result": task.prompt_job_result, "prompt_job_error": task.prompt_job_error,
            "video_filename": task.video_filename, "error_message": task.error_message,
            "created_at": task.created_at, "updated_at": task.updated_at,
        }
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/test_video_service.py -k "conflict or delete_running" -v`
Expected: PASS（2 个）

- [ ] **Step 5: 全模块回归**

Run: `pytest tests/test_video_service.py tests/test_video_repository.py tests/test_video_runner.py -v`
Expected: PASS（全部）

- [ ] **Step 6: 提交**

```bash
git add app/services/video_service/video_service.py tests/test_video_service.py
git commit -m "feat(video): VideoService 编排（导入/提交/状态/列表/删除 + 串行校验）"
```

---

## Task 7: 路由 + 应用集成（注册/日志抑制/重启恢复）

**Files:**
- Create: `app/routes/video.py`
- Modify: `app/main.py`, `app/services/startup_image_tasks.py`
- Test: `tests/test_video_routes.py`

**Interfaces:**
- Produces 路由（前缀 `/api/video`）:
  - `POST /tasks/import`（JSON `VideoImportBody`）/ `POST /tasks/upload`（multipart 本地图）
  - `POST /tasks/{id}/prompt-job/start`（`PromptJobBody`）/ `GET /tasks/{id}/prompt-job/status`
  - `POST /tasks/{id}/submit`（`VideoSubmitBody`）/ `GET /tasks/{id}/status`
  - `GET /tasks` / `GET /tasks/{id}/video` / `GET /tasks/{id}/image` / `DELETE /tasks/{id}`
- Consumes: `VideoService`、`VideoPromptService`、`get_video_task_dir`、`get_or_create_thumbnail`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_video_routes.py`：

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_tasks_ok():
    r = client.get("/api/video/tasks")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_status_404_for_unknown():
    r = client.get("/api/video/tasks/vid_nope/status")
    assert r.status_code == 404


def test_upload_creates_draft(tmp_path):
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (300, 400), "pink").save(buf, format="PNG")
    buf.seek(0)
    r = client.post(
        "/api/video/tasks/upload",
        files={"file": ("ref.png", buf, "image/png")},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "draft"
    assert data["recommended_ratio"] == "3:4"
    # 清理
    client.delete(f"/api/video/tasks/{data['task_id']}")
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_video_routes.py -v`
Expected: FAIL（404，因路由未注册）

- [ ] **Step 3: 实现路由**

创建 `app/routes/video.py`：

```python
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.video import (
    ApiResponse,
    PromptJobBody,
    VideoImportBody,
    VideoSubmitBody,
)
from app.services import directory_service
from app.services.video_service.exceptions import VideoConflictError, VideoNotFoundError
from app.services.video_service.prompt_service import VideoPromptService
from app.services.video_service.video_service import VideoService
from app.utils.thumbnails import get_or_create_thumbnail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["video"])


def _svc(db: Session) -> VideoService:
    return VideoService(db)


@router.post("/tasks/import", response_model=ApiResponse)
def import_task(body: VideoImportBody, db: Session = Depends(get_db)):
    try:
        data = _svc(db).import_from_quick_create(
            body.source_task_id, body.source_image_path, body.ref_prompt_text
        )
        return ApiResponse(success=True, data=data, message="已导入")
    except VideoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/upload", response_model=ApiResponse)
def upload_task(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = file.file.read()
    try:
        data = _svc(db).import_from_upload(file.filename or "ref.png", content)
        return ApiResponse(success=True, data=data, message="已上传")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/prompt-job/start", response_model=ApiResponse)
def start_prompt_job(
    task_id: str, body: PromptJobBody, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        data = VideoPromptService(db).start_job(
            task_id, body.mode, body.manual_prompt, background_tasks
        )
        return ApiResponse(success=True, data=data, message="Prompt 作业已启动")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/prompt-job/status", response_model=ApiResponse)
def prompt_job_status(task_id: str, db: Session = Depends(get_db)):
    data = _svc(db).get_status(task_id)
    if not data:
        raise HTTPException(status_code=404, detail="视频任务不存在")
    return ApiResponse(success=True, data=data, message="ok")


@router.post("/tasks/{task_id}/submit", response_model=ApiResponse)
def submit_task(
    task_id: str, body: VideoSubmitBody, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        data = _svc(db).submit(
            task_id, video_prompt_text=body.video_prompt_text, image_role=body.image_role,
            duration=body.duration, generate_audio=body.generate_audio, ratio=body.ratio,
            prompt_mode="manual", background_tasks=background_tasks,
        )
        return ApiResponse(success=True, data=data, message="已提交生成")
    except VideoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VideoConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/status", response_model=ApiResponse)
def task_status(task_id: str, db: Session = Depends(get_db)):
    data = _svc(db).get_status(task_id)
    if not data:
        raise HTTPException(status_code=404, detail="视频任务不存在")
    return ApiResponse(success=True, data=data, message="ok")


@router.get("/tasks", response_model=ApiResponse)
def list_tasks(db: Session = Depends(get_db)):
    return ApiResponse(success=True, data=_svc(db).list_tasks(), message="ok")


@router.get("/tasks/{task_id}/video")
def get_video(task_id: str, db: Session = Depends(get_db)):
    task = _svc(db).repo.get_by_id(task_id)
    if not task or not task.video_filename:
        raise HTTPException(status_code=404, detail="视频不存在")
    path = os.path.join(directory_service.get_video_task_dir(task_id), task.video_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="视频文件缺失")
    return FileResponse(path, media_type="video/mp4", filename=f"{task_id}.mp4")


@router.get("/tasks/{task_id}/image")
def get_image(task_id: str, db: Session = Depends(get_db)):
    task = _svc(db).repo.get_by_id(task_id)
    if not task or not task.ref_image_path or not os.path.exists(task.ref_image_path):
        raise HTTPException(status_code=404, detail="参考图不存在")
    thumb = get_or_create_thumbnail(task.ref_image_path)
    return FileResponse(thumb)


@router.delete("/tasks/{task_id}", response_model=ApiResponse)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    try:
        _svc(db).delete_task(task_id)
        return ApiResponse(success=True, data={"deleted_id": task_id}, message="已删除")
    except VideoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VideoConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

> 注：`get_or_create_thumbnail` 的真实签名以 `app/utils/thumbnails.py` 为准；若其需要额外参数，按现有调用方（如 `creation.py`）的用法对齐。

- [ ] **Step 4: 注册路由 + 日志抑制**

在 `app/main.py`：
- 顶部 import 改为 `from app.routes import pages, api, repair, material, creation, beautify, video`
- 在 `app.include_router(beautify.router, prefix="/api/beautify")` 之后加：`app.include_router(video.router)`
- 在 `_SuppressPollAccessLog.filter` 的 `return True` 之前加：

```python
        if "/api/video/tasks/" in msg and "/status HTTP" in msg:
            return False
```

- [ ] **Step 5: 重启恢复 in-flight 视频任务**

在 `app/services/startup_image_tasks.py`：
- import 区加：`from app.models.video import VideoCreationTask` 与 `from app.repositories.video_repository import VideoRepository`
- `counts` 字典加 `"video": 0`（两处：SKIP 分支的返回值 + 主 counts 初始化）
- 在 `beautify` 处理块之后加：

```python
        vrepo = VideoRepository(db)
        video_tasks = (
            db.query(VideoCreationTask)
            .filter(VideoCreationTask.status.in_(
                ("pending", "uploading", "generating", "downloading")
            ))
            .all()
        )
        for t in video_tasks:
            updated = vrepo.update(
                t.id,
                {"status": "failed", "error_message": "服务重启，任务已中断，请重新提交"},
            )
            if updated:
                counts["video"] += 1
```

- 更新末尾 `logger.info(...)` 格式串，追加 `video=%s` 与 `counts["video"]`。

- [ ] **Step 6: 运行确认通过**

Run: `pytest tests/test_video_routes.py -v`
Expected: PASS（3 个）

- [ ] **Step 7: 后端全量回归**

Run: `pytest tests/test_video_routes.py tests/test_video_service.py tests/test_video_repository.py tests/test_video_runner.py tests/test_seedance_tool.py -v`
Expected: PASS（全部）

- [ ] **Step 8: 提交**

```bash
git add app/routes/video.py app/main.py app/services/startup_image_tasks.py tests/test_video_routes.py
git commit -m "feat(video): 路由 + 应用注册 + 轮询日志抑制 + 重启恢复"
```

---

## Task 8: `.env.example` + docker-compose 注入

**Files:**
- Create: `.env.example`
- Modify: `docker-compose.yml`, `app/main.py`

- [ ] **Step 1: 创建 `.env.example`**

```dotenv
# Seedance 2.0 文生视频模型（火山引擎 Ark）
# base_url / model 已有默认值，通常无需修改；api_key 必填
SEEDANCE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
SEEDANCE_MODEL=doubao-seedance-2-0-260128
SEEDANCE_API_KEY=
```

- [ ] **Step 2: 启动时加载 `.env`**

在 `app/main.py` 顶部（`import os` 之后、其他 app import 之前）加：

```python
from dotenv import load_dotenv

load_dotenv()
```

- [ ] **Step 3: docker-compose 注入 env**

在 `docker-compose.yml` 后端服务定义下加 `env_file`（若已有 `environment` 块则并存）：

```yaml
    env_file:
      - .env
```

（实现时以 `docker-compose.yml` 实际服务名与缩进为准。）

- [ ] **Step 4: 验证加载不报错**

Run: `python -c "from dotenv import load_dotenv; load_dotenv(); import app.main"`
Expected: 无 `ImportError`，正常退出。

- [ ] **Step 5: 提交**

```bash
git add .env.example docker-compose.yml app/main.py
git commit -m "feat(video): Seedance .env 配置入口 + docker env_file 注入"
```

---

## Task 9: 前端类型 + API 客户端

**Files:**
- Create: `page/src/types/video.ts`, `page/src/services/videoApi.ts`

**Interfaces:**
- Produces（`video.ts`）: `VideoTask`、`VideoStatus`、`PromptJobStatus`、`ImageRole`。
- Produces（`videoApi.ts`）: `importFromQuickCreate`、`uploadImage`、`startPromptJob`、`getPromptJobStatus`、`submitVideo`、`getStatus`、`listTasks`、`deleteTask`、`videoUrl(id)`、`imageUrl(id)`。
- Consumes: `page/src/services/api.ts`（`parseResponseBodyAsJson`、`ApiError`）——参考 `beautifyApi.ts` 写法。

- [ ] **Step 1: 定义类型**

创建 `page/src/types/video.ts`：

```typescript
export type VideoStatus =
  | "draft" | "pending" | "uploading" | "generating" | "downloading"
  | "completed" | "failed";

export type PromptJobStatus = "pending" | "running" | "completed" | "failed";

export type ImageRole = "first_frame" | "reference_image";

export interface VideoTask {
  task_id: string;
  source_kind: string;
  status: VideoStatus;
  image_role: ImageRole;
  duration: number;
  generate_audio: boolean;
  ratio: string;
  ref_prompt_text?: string | null;
  video_prompt_text?: string | null;
  prompt_mode?: string | null;
  prompt_job_status?: PromptJobStatus | null;
  prompt_job_result?: string | null;
  prompt_job_error?: string | null;
  video_filename?: string | null;
  error_message?: string | null;
  recommended_ratio?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}
```

- [ ] **Step 2: 实现 API 客户端**

创建 `page/src/services/videoApi.ts`（沿用 `beautifyApi.ts` 的 envelope 解析与超时约定）：

```typescript
import { ApiError, parseResponseBodyAsJson } from "@/services/api";
import type { ImageRole, VideoTask } from "@/types/video";

const API_BASE = "/api/video";
const DEFAULT_TIMEOUT = 30000;

interface ApiEnvelope<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  detail?: unknown;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), DEFAULT_TIMEOUT);
  try {
    const resp = await fetch(`${API_BASE}${path}`, { ...init, signal: ctrl.signal });
    const body = (await parseResponseBodyAsJson(resp)) as ApiEnvelope<T>;
    if (!resp.ok || !body.success) {
      throw new ApiError(body.message || `请求失败 (${resp.status})`, resp.status);
    }
    return body.data as T;
  } finally {
    clearTimeout(timer);
  }
}

export function importFromQuickCreate(payload: {
  source_task_id: string;
  source_image_path: string;
  ref_prompt_text?: string | null;
}): Promise<VideoTask> {
  return call<VideoTask>("/tasks/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_kind: "quick_create", ...payload }),
  });
}

export function uploadImage(file: File): Promise<VideoTask> {
  const form = new FormData();
  form.append("file", file);
  return call<VideoTask>("/tasks/upload", { method: "POST", body: form });
}

export function startPromptJob(
  taskId: string, mode: "recommend" | "optimize", manualPrompt?: string,
): Promise<{ task_id: string; prompt_job_status: string }> {
  return call("/tasks/" + taskId + "/prompt-job/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, manual_prompt: manualPrompt ?? null }),
  });
}

export function getPromptJobStatus(taskId: string): Promise<VideoTask> {
  return call<VideoTask>(`/tasks/${taskId}/prompt-job/status`);
}

export function submitVideo(taskId: string, payload: {
  video_prompt_text: string; image_role: ImageRole;
  duration: number; generate_audio: boolean; ratio: string;
}): Promise<VideoTask> {
  return call<VideoTask>(`/tasks/${taskId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getStatus(taskId: string): Promise<VideoTask> {
  return call<VideoTask>(`/tasks/${taskId}/status`);
}

export function listTasks(): Promise<VideoTask[]> {
  return call<VideoTask[]>("/tasks");
}

export function deleteTask(taskId: string): Promise<{ deleted_id: string }> {
  return call(`/tasks/${taskId}`, { method: "DELETE" });
}

export const videoUrl = (taskId: string) => `${API_BASE}/tasks/${taskId}/video`;
export const imageUrl = (taskId: string) => `${API_BASE}/tasks/${taskId}/image`;
```

- [ ] **Step 3: 类型检查**

Run: `cd page && npm run type-check`
Expected: 无 video.ts / videoApi.ts 相关错误。

> 若 `parseResponseBodyAsJson` / `ApiError` 的导出名与 `api.ts` 不一致，以 `beautifyApi.ts` 的实际 import 为准对齐。

- [ ] **Step 4: 提交**

```bash
git add page/src/types/video.ts page/src/services/videoApi.ts
git commit -m "feat(video): 前端类型定义 + API 客户端"
```

---

## Task 10: 视频创作页 + 路由 + 导航入口

**Files:**
- Create: `page/src/pages/video/page.tsx` + `page/src/pages/video/components/*`
- Modify: `page/src/router/config.tsx`、首页导航组件

**Interfaces:**
- Consumes: `videoApi`、`@/types/video`。
- Produces: 默认导出 `VideoPage`（供 router lazy import）。

- [ ] **Step 1: 实现页面骨架**

创建 `page/src/pages/video/page.tsx`：三区布局（参考图区 / Prompt 工作台 / 参数提交）+ 底部历史列表。要点：
- 显式 `import { useState, useEffect, useCallback, useRef } from "react";` 与 `import { useSearchParams } from "react-router-dom";`（仓库惯例）。
- 读 `?task=` query 参数：存在则 `getStatus(id)` 载入草稿进入编辑态。
- 本地上传：`<input type="file">` → `uploadImage(file)`。
- Prompt 工作台：模式 A「AI 推荐」按钮 → `startPromptJob(id,"recommend")` 后轮询 `getPromptJobStatus`；模式 B textarea +「AI 优化」→ `startPromptJob(id,"optimize",text)`；结果写入同一可编辑 textarea。
- 参数：`image_role` 切换（默认 first_frame）、时长 `<input type="range" min=4 max=15>`（默认 8）、音频 checkbox（默认关）、ratio 下拉（默认 `recommended_ratio`）。
- 提交 → `submitVideo` → 轮询 `getStatus` 显示 uploading/generating/downloading；`completed` 时 `<video controls src={videoUrl(id)}>` + 下载链接；`failed` 显示 `error_message` + 重新提交按钮。
- 提交返回 409 → toast「已有视频任务进行中」。

按项目现有页面（如 `beautify` 相关 UI 或 `creation` 页）的视觉与交互风格实现，具体 JSX 由实现者按 Tailwind 约定编写；历史列表可拆分到 `components/VideoHistoryList.tsx`。

- [ ] **Step 2: 注册路由**

在 `page/src/router/config.tsx`：
- 加 `const VideoPage = lazy(() => import("../pages/video/page"));`
- 在 `/creation` 路由对象之后加：

```tsx
  {
    path: "/video",
    element: (
      <Suspense fallback={<PageFallback />}>
        <VideoPage />
      </Suspense>
    ),
  },
```

- [ ] **Step 3: 首页导航入口**

在首页导航组件（与「素材加工 / 美图创作 / 图片修补」并列处）加第四个入口「视频创作」，`to="/video"`，沿用现有卡片/按钮样式与图标风格。

- [ ] **Step 4: 类型检查 + lint**

Run: `cd page && npm run type-check && npm run lint`
Expected: 无 video 相关错误。

- [ ] **Step 5: 提交**

```bash
git add page/src/pages/video/ page/src/router/config.tsx
git commit -m "feat(video): 视频创作页（三区 + 历史）+ 路由 + 导航入口"
```

---

## Task 11: 灵感产线卡片「去创作视频」跳转

**Files:**
- Modify: `page/src/pages/home/components/BatchTaskCard.tsx`

**Interfaces:**
- Consumes: `videoApi.importFromQuickCreate`、`useNavigate`。

- [ ] **Step 1: 加按钮 + 跳转逻辑**

在 `BatchTaskCard.tsx` 每张产出图操作区（现有「去美化」/评论等按钮附近）加「去创作视频」按钮。点击处理：

```tsx
const navigate = useNavigate();  // 显式 import { useNavigate } from "react-router-dom";

const handleCreateVideo = useCallback(async (img: QuickCreateImage) => {
  try {
    // source_task_id 取该卡片对应的产线任务 ID；source_image_path 取该图相对 work_dir 路径；
    // ref_prompt_text 取该图所在组的完整 Prompt。三者的具体取值以本组件已有的 img/task 字段为准。
    const task = await importFromQuickCreate({
      source_task_id: sourceTaskId,
      source_image_path: img.sourceImagePath,
      ref_prompt_text: groupFullPrompt,
    });
    navigate(`/video?task=${task.task_id}`);
  } catch (e) {
    // 复用组件现有的错误提示机制（toast/setError）
  }
}, [navigate, sourceTaskId, groupFullPrompt]);
```

> 关键映射（实现者按组件内既有数据结构对齐）：
> - `source_task_id`：产出图所属的一键创作任务 ID（`QuickCreateRecord.taskId` / `task.quickCreateRecordId` 一线）。
> - `source_image_path`：后端 `import_from_quick_create` 用 `os.path.join(work_dir, source_image_path)` 定位，故传相对 `work_dir` 的路径，与「去美化」用的 `source_image_path` 同源。
> - `ref_prompt_text`：该图所在 `QuickCreateGroup` 的完整 Prompt（`group` 的 fullPrompt/promptPreview 一线）。

- [ ] **Step 2: 类型检查 + lint**

Run: `cd page && npm run type-check && npm run lint`
Expected: 无 BatchTaskCard 相关错误。

- [ ] **Step 3: 提交**

```bash
git add page/src/pages/home/components/BatchTaskCard.tsx
git commit -m "feat(video): 灵感产线产出图卡片增加「去创作视频」跳转"
```

---

## Task 12: 集成回归 + 前端构建 + 文档

**Files:**
- Modify: `CLAUDE.md`（模块清单加视频创作）

- [ ] **Step 1: 后端全量测试**

Run: `pytest`
Expected: 全绿（含既有测试无回归）。

- [ ] **Step 2: 前端构建验证**

Run: `cd page && npm run type-check && npm run lint && npm run build`
Expected: 构建成功，产物输出 `app/static/`。

- [ ] **Step 3: 更新 CLAUDE.md**

在「Project Overview」的三模块描述处补充第四模块「Video Creation（视频创作）」一句话说明（Seedance 2.0，居家动态写真），并在 Architecture 的 Route/Service 列表补 `video.py` / `video_service/`。

- [ ] **Step 4: 提交**

```bash
git add CLAUDE.md
git commit -m "docs(video): CLAUDE.md 补充视频创作模块说明"
```

- [ ] **Step 5: 人工验收（非自动化，记录结果）**

真实环境跑通一次全链路：产线图卡片「去创作视频」→ AI 推荐 Prompt → 提交生成 → 轮询完成 → 播放 + 下载 → 删除。确认 TOS 无残留对象、`data/video/tasks/{id}/` 目录随删除清理。

---

## Self-Review

**Spec 覆盖核对：**
- §1.1 视频纲领 → Task 4 模板内置 ✅
- §2 产品决策（作品库/双导入/双 role/双 Prompt 模式/参数/串行）→ Task 6 + Task 7 + Task 10 ✅
- §3.1–3.3 文件骨架与复用 → Task 1–7 ✅
- §3.4 Seedance `.env` 配置 → Task 1（读取）+ Task 8（`.env.example`/加载/docker）✅
- §4 数据模型/目录/迁移 → Task 2 + Task 3 ✅
- §5 状态机 + 重启恢复 → Task 6（状态流转）+ Task 7 Step 5（重启）✅
- §6 API 一览 → Task 7 全端点 ✅
- §7 Runner（含 finally 清理、ratio 策略）→ Task 5 + Task 1 ✅
- §8 Prompt 编排 → Task 4 ✅
- §9 前端（三区/历史/卡片跳转）→ Task 10 + Task 11 ✅
- §10 错误处理（409/失败落库/重启/配置缺失）→ Task 6/7/8 ✅
- §11 测试 → 各 Task TDD + Task 12 回归 ✅

**Placeholder 扫描：** 代码步骤均含完整实现；仅前端 JSX 细节（Task 10 Step 1、Task 11）按「遵循现有页面风格」描述——因视觉实现依赖既有 Tailwind 组件约定，属合理的实现者裁量，非占位。`get_or_create_thumbnail` 与 `parseResponseBodyAsJson` 签名标注了「以现有调用方为准」核对点。

**类型一致性：** `VideoCreationTask` 列名、`VideoService` 方法名、`videoApi` 函数名、状态字符串（draft/pending/uploading/generating/downloading/completed/failed）跨 Task 一致；`SeedanceResult.video_url`、`SeedanceClient.submit/poll` 签名在 Task 1 定义、Task 5 消费一致。

**Scope：** 单一模块，聚焦一份计划。
