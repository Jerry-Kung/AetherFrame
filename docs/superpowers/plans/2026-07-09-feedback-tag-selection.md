# 生产 Feedback 标签化（点选标签 + 等级）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 首页灵感产线的图片 feedback 从「纯文本 + 腿脚崩坏勾选」升级为「点选标签（负面标签带轻微/中等/严重等级）为主、自由文本为辅」，导出 schema 升 aetherframe_feedback_v2。

**Architecture:** 后端新增标签配置文件（YAML）+ 加载模块，通过新 API 下发前端；`creation_image_feedbacks` 表加 `selected_tags_json` 列存选中标签；保存接口后端统一推导 `leg_foot_bad`；导出附带 `tag_config` 快照实现自包含。前端改造 `ImageFeedbackModal` 为三组胶囊标签（负面标签点击循环四态）。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite（无 Alembic，inline ALTER TABLE 迁移）、PyYAML（requirements.txt 已有 `pyyaml>=6.0`）、React 19 + TypeScript + Tailwind。

**Spec:** `docs/superpowers/specs/2026-07-09-feedback-tag-selection-design.md`（首版词表、四态交互、v2 导出结构均以 spec 为准）。

## Global Constraints

- 所有 API 响应包 `ApiResponse(success, data, message)`，路由前缀 `/api/creation`。
- 前端 React hooks 必须显式 import（`import { useState } from "react"`）——`npm run type-check` 不含 auto-imports.d.ts。
- 数据库迁移走 `app/models/database.py` 的 `migrate_*` 内联模式（检查列存在 → ALTER TABLE），并在 `init_db()` 中调用。
- 导出 schema 值：改版后必须为 `aetherframe_feedback_v2`。
- severity 枚举值固定：`minor` / `moderate` / `severe`；缺省兜底 `moderate`；中文映射 轻微/中等/严重（导出用）、轻/中/重（UI 胶囊后缀用）。
- 标签 key 一经启用不得改含义；配置文件路径固定 `app/config/feedback_tags.yaml`。
- 保存接口对未知标签 key **剔除并告警，不报错**。
- 「清空即删」三条件：文本空 且 未勾兜底 且 无选中标签 → 删行。
- `leg_foot_bad` 落库值 = `(任一选中负面标签的 leg_foot_bad=true) OR body.leg_foot_bad`，由后端推导。
- 不改盲评页；不做标签管理 UI；不回填历史数据（生产库旧行 `selected_tags_json` 由迁移默认 `'[]'`）。
- 测试命令：后端 `python -m pytest tests/<file> -v`；前端 `cd page; npm run type-check; npm run lint`。
- 永不 stage/提交 `.claude/settings.local.json`；experiments/ 冻结物不触碰。
- 提交信息末尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `app/config/feedback_tags.yaml` | Create | 标签词表配置（key/label/polarity/leg_foot_bad/taxonomy） |
| `app/services/creation_service/feedback_tags.py` | Create | 配置加载、校验归一化、bad 推导、API 视图、导出快照 |
| `app/models/creation_feedback.py` | Modify | 加 `selected_tags_json` 列 |
| `app/models/database.py` | Modify | 加迁移函数并在 `init_db()` 调用 |
| `app/repositories/creation_feedback_repository.py` | Modify | upsert 透传 `selected_tags_json` |
| `app/schemas/creation.py` | Modify | SaveRequest 加 `selected_tags`；Out 模型同步 |
| `app/services/creation_service/feedback_service.py` | Modify | 保存语义扩展、serialize 加字段、导出升 v2 |
| `app/routes/creation.py` | Modify | 新增 `GET /feedback/tags`；保存路由透传 selected_tags |
| `tests/test_feedback_tags_config.py` | Create | 配置模块单测 |
| `tests/test_migrate_feedback_selected_tags.py` | Create | 迁移单测 |
| `tests/test_creation_feedback.py` | Modify | service/导出测试扩展 |
| `tests/routes/test_creation_feedback_routes.py` | Modify | 路由测试扩展（tags API、selected_tags 透传） |
| `page/src/services/creationApi.ts` | Modify | 类型扩展、`getFeedbackTags`（模块级缓存） |
| `page/src/types/quickCreate.ts` | Modify | `userFeedback` 加 `selectedTags` |
| `page/src/utils/batchAutomationDisplay.ts` | Modify | hydrate 映射 selected_tags |
| `page/src/pages/home/components/ImageFeedbackModal.tsx` | Modify | 标签区 + 四态循环 + 兜底勾选改版 |
| `page/src/pages/home/components/BatchTaskCard.tsx` | Modify | onSave 签名扩展 |
| `page/src/pages/home/components/BatchCreationPage.tsx` | Modify | 保存回调传标签、用响应回填本地 state |

---

### Task 1: 标签配置文件 + 加载模块 + GET /feedback/tags API

**Files:**
- Create: `app/config/feedback_tags.yaml`
- Create: `app/services/creation_service/feedback_tags.py`
- Modify: `app/routes/creation.py`（`export_image_feedback` 附近加路由）
- Test: `tests/test_feedback_tags_config.py`
- Test: `tests/routes/test_creation_feedback_routes.py`（追加 tags API 测试）

**Interfaces:**
- Consumes: 无（首任务）。
- Produces（后续任务依赖，签名固定）：
  - `feedback_tags.get_tag_config() -> Dict[str, Any]`——`{"version": int, "tags": [ {key,label,polarity,leg_foot_bad,taxonomy} ]}`；加载失败返回 `{"version": 0, "tags": []}`。lru_cache 缓存（重启生效语义）。
  - `feedback_tags.load_tag_config(path: str) -> Dict[str, Any]`——无缓存版，供测试注入临时文件。
  - `feedback_tags.normalize_selected_tags(raw: Optional[List[Dict]], config: Dict) -> List[Dict]`——剔未知 key（告警）、按 key 去重保序、负面标签 severity 非法/缺失兜底 `"moderate"`、正/中立剥离 severity。元素形如 `{"key": "..."}` 或 `{"key": "...", "severity": "..."}`。
  - `feedback_tags.derive_leg_foot_bad(normalized: List[Dict], checkbox: bool, config: Dict) -> bool`。
  - `feedback_tags.tags_for_api(config: Dict) -> Dict`——剥掉 taxonomy 字段的下发视图。
  - `feedback_tags.tag_config_snapshot(config: Dict) -> Dict`——含 taxonomy 的深拷贝（导出快照用）。
  - `feedback_tags.SEVERITIES = ("minor", "moderate", "severe")`、`DEFAULT_SEVERITY = "moderate"`、`SEVERITY_LABELS = {"minor": "轻微", "moderate": "中等", "severe": "严重"}`。
  - API：`GET /api/creation/feedback/tags` → `ApiResponse(data={"version": ..., "tags": [{key,label,polarity,leg_foot_bad}]})`。

- [ ] **Step 1: 写配置文件**

创建 `app/config/feedback_tags.yaml`（词表与 spec §1 逐字一致）：

```yaml
# 生产 feedback 标签词表（设计文档 docs/superpowers/specs/2026-07-09-feedback-tag-selection-design.md §1）
# key 一经启用不得复用为其他含义；改 label 措辞 / taxonomy 映射 / 增删标签只改本文件，重启生效。
# polarity: positive | negative | neutral；leg_foot_bad / taxonomy 仅 negative 有意义。
version: 1
tags:
  # ---- 负面 · 腿脚类（选中即计 bad）----
  - { key: foot_crude,          label: 脚部简陋,                     polarity: negative, leg_foot_bad: true,  taxonomy: 脚部/简陋 }
  - { key: foot_exaggerated,    label: 脚部细节夸张,                 polarity: negative, leg_foot_bad: true,  taxonomy: 脚部/夸张 }
  - { key: foot_proportion,     label: 脚部比例结构异常,             polarity: negative, leg_foot_bad: true,  taxonomy: 脚部/比例结构 }
  - { key: foot_tip_discolor,   label: 脚尖变色,                     polarity: negative, leg_foot_bad: true,  taxonomy: 脚部/脚尖变色 }
  - { key: leg_multi_missing,   label: 多肢/缺肢,                    polarity: negative, leg_foot_bad: true,  taxonomy: 腿部/结构错误 }
  - { key: leg_twist,           label: 腿部异常扭曲（含脚尖反向）,   polarity: negative, leg_foot_bad: true,  taxonomy: 腿部/结构错误 }
  - { key: pose_weird,          label: 姿势诡异（不符合人类正常姿势）, polarity: negative, leg_foot_bad: true,  taxonomy: 其他/未分类 }
  - { key: leg_proportion,      label: 腿部比例失调（过粗/过细）,    polarity: negative, leg_foot_bad: true,  taxonomy: 身体比例/整体不协调 }
  - { key: sock_painted,        label: 袜子上色感,                   polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/上色感 }
  - { key: sock_toe_separation, label: 脚趾分离感,                   polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/上色感 }
  - { key: sock_plastic,        label: 袜子塑料袋感,                 polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/塑料袋感 }
  - { key: sock_wrinkle_heavy,  label: 袜子皱褶过于夸张,             polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/皱褶夸张 }
  - { key: sock_missing,        label: 袜子缺失,                     polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/缺失 }
  - { key: sock_shoes,          label: 错误穿鞋,                     polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/穿鞋 }
  # ---- 负面 · 非腿脚类（不计 bad）----
  - { key: style_realistic,     label: 画风写实化,                   polarity: negative, leg_foot_bad: false, taxonomy: 画风/写实化 }
  - { key: style_flat2d,        label: 画风平面2D,                   polarity: negative, leg_foot_bad: false, taxonomy: 画风/平面2D }
  - { key: style_doll3d,        label: 3D玩偶感,                     polarity: negative, leg_foot_bad: false, taxonomy: 画风/3D玩偶感 }
  - { key: body_proportion,     label: 身体比例不协调,               polarity: negative, leg_foot_bad: false, taxonomy: 身体比例/整体不协调 }
  - { key: face_collapse,       label: 脸部细节崩坏,                 polarity: negative, leg_foot_bad: false, taxonomy: 其他/未分类 }
  - { key: face_anchor_lost,    label: 视觉锚点丢失,                 polarity: negative, leg_foot_bad: false, taxonomy: 其他/未分类 }
  - { key: face_expression,     label: 表情诡异,                     polarity: negative, leg_foot_bad: false, taxonomy: 其他/未分类 }
  # ---- 正面 ----
  - { key: pos_sock_style,      label: 袜子样式好看,                 polarity: positive }
  - { key: pos_leg_natural,     label: 腿脚自然,                     polarity: positive }
  - { key: pos_overall_good,    label: 整体效果好,                   polarity: positive }
  # ---- 中立 ----
  - { key: neutral_normal,      label: 正常,                         polarity: neutral }
```

- [ ] **Step 2: 写加载模块的失败测试**

创建 `tests/test_feedback_tags_config.py`：

```python
"""feedback 标签配置：加载 / 归一化 / bad 推导 / 视图"""

import textwrap

from app.services.creation_service.feedback_tags import (
    DEFAULT_SEVERITY,
    SEVERITIES,
    derive_leg_foot_bad,
    get_tag_config,
    load_tag_config,
    normalize_selected_tags,
    tag_config_snapshot,
    tags_for_api,
)


def _write_config(tmp_path, content: str) -> str:
    p = tmp_path / "feedback_tags.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return str(p)


SMALL_CONFIG = """
    version: 7
    tags:
      - { key: sock_wrinkle_heavy, label: 袜子皱褶过于夸张, polarity: negative, leg_foot_bad: true, taxonomy: 袜子/皱褶夸张 }
      - { key: style_doll3d, label: 3D玩偶感, polarity: negative, leg_foot_bad: false, taxonomy: 画风/3D玩偶感 }
      - { key: pos_overall_good, label: 整体效果好, polarity: positive }
      - { key: neutral_normal, label: 正常, polarity: neutral }
"""


class TestLoad:
    def test_load_valid_config(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, SMALL_CONFIG))
        assert cfg["version"] == 7
        assert [t["key"] for t in cfg["tags"]] == [
            "sock_wrinkle_heavy", "style_doll3d", "pos_overall_good", "neutral_normal",
        ]
        neg = cfg["tags"][0]
        assert neg["polarity"] == "negative"
        assert neg["leg_foot_bad"] is True
        assert neg["taxonomy"] == "袜子/皱褶夸张"

    def test_load_missing_file_degrades_empty(self, tmp_path):
        cfg = load_tag_config(str(tmp_path / "nope.yaml"))
        assert cfg == {"version": 0, "tags": []}

    def test_load_broken_yaml_degrades_empty(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, "tags: [key: {{"))
        assert cfg == {"version": 0, "tags": []}

    def test_get_tag_config_reads_repo_file(self):
        get_tag_config.cache_clear()
        cfg = get_tag_config()
        keys = {t["key"] for t in cfg["tags"]}
        assert cfg["version"] >= 1
        assert {"sock_wrinkle_heavy", "leg_multi_missing", "sock_toe_separation",
                "pos_sock_style", "neutral_normal"} <= keys


class TestNormalize:
    def _cfg(self, tmp_path):
        return load_tag_config(_write_config(tmp_path, SMALL_CONFIG))

    def test_unknown_key_dropped(self, tmp_path):
        out = normalize_selected_tags(
            [{"key": "ghost_tag"}, {"key": "neutral_normal"}], self._cfg(tmp_path)
        )
        assert out == [{"key": "neutral_normal"}]

    def test_negative_missing_or_bad_severity_defaults_moderate(self, tmp_path):
        cfg = self._cfg(tmp_path)
        assert normalize_selected_tags([{"key": "sock_wrinkle_heavy"}], cfg) == [
            {"key": "sock_wrinkle_heavy", "severity": DEFAULT_SEVERITY}
        ]
        assert normalize_selected_tags(
            [{"key": "sock_wrinkle_heavy", "severity": "MAX"}], cfg
        ) == [{"key": "sock_wrinkle_heavy", "severity": "moderate"}]

    def test_negative_valid_severity_kept(self, tmp_path):
        cfg = self._cfg(tmp_path)
        for sev in SEVERITIES:
            out = normalize_selected_tags(
                [{"key": "sock_wrinkle_heavy", "severity": sev}], cfg
            )
            assert out == [{"key": "sock_wrinkle_heavy", "severity": sev}]

    def test_positive_and_neutral_strip_severity(self, tmp_path):
        out = normalize_selected_tags(
            [{"key": "pos_overall_good", "severity": "severe"}, {"key": "neutral_normal"}],
            self._cfg(tmp_path),
        )
        assert out == [{"key": "pos_overall_good"}, {"key": "neutral_normal"}]

    def test_dedup_keeps_first_and_none_input_ok(self, tmp_path):
        cfg = self._cfg(tmp_path)
        out = normalize_selected_tags(
            [{"key": "sock_wrinkle_heavy", "severity": "minor"},
             {"key": "sock_wrinkle_heavy", "severity": "severe"}],
            cfg,
        )
        assert out == [{"key": "sock_wrinkle_heavy", "severity": "minor"}]
        assert normalize_selected_tags(None, cfg) == []
        assert normalize_selected_tags([], cfg) == []


class TestDeriveBad:
    def _cfg(self, tmp_path):
        return load_tag_config(_write_config(tmp_path, SMALL_CONFIG))

    def test_legfoot_negative_tag_implies_bad(self, tmp_path):
        assert derive_leg_foot_bad(
            [{"key": "sock_wrinkle_heavy", "severity": "minor"}], False, self._cfg(tmp_path)
        ) is True

    def test_non_legfoot_negative_does_not_imply(self, tmp_path):
        assert derive_leg_foot_bad(
            [{"key": "style_doll3d", "severity": "severe"}], False, self._cfg(tmp_path)
        ) is False

    def test_checkbox_fallback_and_positive_only(self, tmp_path):
        cfg = self._cfg(tmp_path)
        assert derive_leg_foot_bad([], True, cfg) is True
        assert derive_leg_foot_bad([{"key": "pos_overall_good"}], False, cfg) is False


class TestViews:
    def test_tags_for_api_strips_taxonomy(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, SMALL_CONFIG))
        view = tags_for_api(cfg)
        assert view["version"] == 7
        assert view["tags"][0] == {
            "key": "sock_wrinkle_heavy", "label": "袜子皱褶过于夸张",
            "polarity": "negative", "leg_foot_bad": True,
        }
        assert view["tags"][2] == {
            "key": "pos_overall_good", "label": "整体效果好",
            "polarity": "positive", "leg_foot_bad": False,
        }

    def test_snapshot_keeps_taxonomy_and_is_copy(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, SMALL_CONFIG))
        snap = tag_config_snapshot(cfg)
        assert snap["tags"][0]["taxonomy"] == "袜子/皱褶夸张"
        snap["tags"][0]["label"] = "篡改"
        assert cfg["tags"][0]["label"] == "袜子皱褶过于夸张"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python -m pytest tests/test_feedback_tags_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.creation_service.feedback_tags'`

- [ ] **Step 4: 实现加载模块**

创建 `app/services/creation_service/feedback_tags.py`：

```python
"""生产 feedback 标签配置：加载 app/config/feedback_tags.yaml 并提供校验/推导/视图。

设计文档：docs/superpowers/specs/2026-07-09-feedback-tag-selection-design.md §1/§3
配置加载失败一律降级 {"version": 0, "tags": []}（前端退化纯文本模式），不阻断反馈链路。
"""

import copy
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(_APP_DIR, "config", "feedback_tags.yaml")

SEVERITIES = ("minor", "moderate", "severe")
DEFAULT_SEVERITY = "moderate"
SEVERITY_LABELS = {"minor": "轻微", "moderate": "中等", "severe": "严重"}

_EMPTY_CONFIG: Dict[str, Any] = {"version": 0, "tags": []}
_POLARITIES = ("positive", "negative", "neutral")


def load_tag_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    """读取并规整标签配置；任何失败降级空配置并告警。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception:
        logger.warning("feedback 标签配置加载失败，降级空词表: %s", path, exc_info=True)
        return dict(_EMPTY_CONFIG)
    if not isinstance(raw, dict) or not isinstance(raw.get("tags"), list):
        logger.warning("feedback 标签配置结构非法，降级空词表: %s", path)
        return dict(_EMPTY_CONFIG)

    tags: List[Dict[str, Any]] = []
    for t in raw["tags"]:
        if not isinstance(t, dict):
            continue
        key = str(t.get("key") or "").strip()
        label = str(t.get("label") or "").strip()
        polarity = str(t.get("polarity") or "").strip()
        if not key or not label or polarity not in _POLARITIES:
            logger.warning("feedback 标签条目非法，跳过: %r", t)
            continue
        entry: Dict[str, Any] = {"key": key, "label": label, "polarity": polarity}
        if polarity == "negative":
            entry["leg_foot_bad"] = bool(t.get("leg_foot_bad", False))
            entry["taxonomy"] = str(t.get("taxonomy") or "其他/未分类").strip()
        tags.append(entry)
    try:
        version = int(raw.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    return {"version": version, "tags": tags}


@lru_cache(maxsize=1)
def get_tag_config() -> Dict[str, Any]:
    """进程级缓存的仓库配置（改配置文件后重启生效）。"""
    return load_tag_config()


def _tag_map(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {t["key"]: t for t in config.get("tags", [])}


def normalize_selected_tags(
    raw: Optional[List[Dict[str, Any]]], config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """校验归一化选中标签：剔未知 key（告警）、去重保序、severity 兜底/剥离。"""
    known = _tag_map(config)
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key in seen:
            continue
        tag = known.get(key)
        if tag is None:
            logger.warning("feedback 保存：未知标签 key 已剔除: %r", key)
            continue
        seen.add(key)
        if tag["polarity"] == "negative":
            sev = str(item.get("severity") or "").strip()
            if sev not in SEVERITIES:
                sev = DEFAULT_SEVERITY
            out.append({"key": key, "severity": sev})
        else:
            out.append({"key": key})
    return out


def derive_leg_foot_bad(
    normalized: List[Dict[str, Any]], checkbox: bool, config: Dict[str, Any]
) -> bool:
    """落库 leg_foot_bad = 任一选中负面标签 leg_foot_bad=true OR 兜底勾选。"""
    known = _tag_map(config)
    for item in normalized:
        tag = known.get(item.get("key"))
        if tag is not None and tag.get("leg_foot_bad"):
            return True
    return bool(checkbox)


def tags_for_api(config: Dict[str, Any]) -> Dict[str, Any]:
    """前端下发视图：剥离 taxonomy（前端用不到），leg_foot_bad 统一补齐布尔。"""
    return {
        "version": config.get("version", 0),
        "tags": [
            {
                "key": t["key"],
                "label": t["label"],
                "polarity": t["polarity"],
                "leg_foot_bad": bool(t.get("leg_foot_bad", False)),
            }
            for t in config.get("tags", [])
        ],
    }


def tag_config_snapshot(config: Dict[str, Any]) -> Dict[str, Any]:
    """导出快照：含 taxonomy 的深拷贝，保证导出文件自包含。"""
    return copy.deepcopy(config)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_feedback_tags_config.py -v`
Expected: PASS（12 个测试全绿）

- [ ] **Step 6: 写 tags API 的失败测试**

在 `tests/routes/test_creation_feedback_routes.py` 末尾追加（该文件已有 `api_client` fixture，直接复用）：

```python
def test_feedback_tags_api(api_client):
    r = api_client.get("/api/creation/feedback/tags")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["version"] >= 1
    by_key = {t["key"]: t for t in data["tags"]}
    assert by_key["sock_wrinkle_heavy"] == {
        "key": "sock_wrinkle_heavy", "label": "袜子皱褶过于夸张",
        "polarity": "negative", "leg_foot_bad": True,
    }
    assert by_key["neutral_normal"]["polarity"] == "neutral"
    # taxonomy 不下发
    assert all("taxonomy" not in t for t in data["tags"])


def test_feedback_tags_api_degrades_when_config_missing(api_client, monkeypatch):
    from app.services.creation_service import feedback_tags

    monkeypatch.setattr(
        feedback_tags, "get_tag_config", lambda: {"version": 0, "tags": []}
    )
    r = api_client.get("/api/creation/feedback/tags")
    assert r.status_code == 200
    assert r.json()["data"] == {"version": 0, "tags": []}
```

- [ ] **Step 7: 跑测试确认失败**

Run: `python -m pytest tests/routes/test_creation_feedback_routes.py::test_feedback_tags_api -v`
Expected: FAIL — 404 Not Found（路由不存在）

- [ ] **Step 8: 实现路由**

在 `app/routes/creation.py` 中 `export_image_feedback`（约 574 行）后追加：

```python
@router.get("/feedback/tags", response_model=ApiResponse)
def get_feedback_tags():
    from app.services.creation_service import feedback_tags

    data = feedback_tags.tags_for_api(feedback_tags.get_tag_config())
    return ApiResponse(success=True, data=data, message="获取 feedback 标签成功")
```

注意：`monkeypatch.setattr(feedback_tags, "get_tag_config", ...)` 要求路由内通过模块属性调用（`feedback_tags.get_tag_config()`），不要 `from ... import get_tag_config` 直接引名。

- [ ] **Step 9: 跑路由测试确认通过**

Run: `python -m pytest tests/routes/test_creation_feedback_routes.py -v`
Expected: PASS（原有 5 个 + 新 2 个全绿）

- [ ] **Step 10: Commit**

```bash
git add app/config/feedback_tags.yaml app/services/creation_service/feedback_tags.py app/routes/creation.py tests/test_feedback_tags_config.py tests/routes/test_creation_feedback_routes.py
git commit -m "feat(feedback): 标签配置文件 + 加载模块 + GET /feedback/tags API

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 数据模型加列 + 迁移 + repository 透传

**Files:**
- Modify: `app/models/creation_feedback.py`
- Modify: `app/models/database.py`（迁移函数 + `init_db()` 调用）
- Modify: `app/repositories/creation_feedback_repository.py:29-51`（upsert）
- Test: `tests/test_migrate_feedback_selected_tags.py`

**Interfaces:**
- Consumes: 无。
- Produces:
  - `CreationImageFeedback.selected_tags_json`：`Column(Text, nullable=False, default="[]")`。
  - `migrate_creation_image_feedbacks_add_selected_tags() -> None`（database.py，init_db 内调用）。
  - `CreationImageFeedbackRepository.upsert(..., selected_tags_json: str = "[]")`——新增关键字参数，其余签名不变。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_migrate_feedback_selected_tags.py`：

```python
"""creation_image_feedbacks.selected_tags_json 迁移 + repo 透传"""

import uuid

from sqlalchemy import text

from app.models.database import engine, migrate_creation_image_feedbacks_add_selected_tags
from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository


def _column_names() -> set[str]:
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info(creation_image_feedbacks)")).fetchall()
        return {c[1] for c in cols}


def test_migrate_adds_column_and_idempotent(db_session):
    migrate_creation_image_feedbacks_add_selected_tags()
    assert "selected_tags_json" in _column_names()
    migrate_creation_image_feedbacks_add_selected_tags()  # 幂等重跑不抛


def test_new_row_defaults_empty_list(db_session):
    repo = CreationImageFeedbackRepository(db_session)
    row = repo.upsert(
        quick_create_task_id=f"qcreate_{uuid.uuid4().hex[:12]}",
        prompt_id="p1", image_index=0,
        leg_foot_bad=False, feedback_text="旧调用不传标签",
    )
    assert row.selected_tags_json == "[]"


def test_upsert_roundtrips_selected_tags_json(db_session):
    repo = CreationImageFeedbackRepository(db_session)
    tid = f"qcreate_{uuid.uuid4().hex[:12]}"
    payload = '[{"key": "sock_wrinkle_heavy", "severity": "severe"}]'
    row = repo.upsert(
        quick_create_task_id=tid, prompt_id="p1", image_index=0,
        leg_foot_bad=True, feedback_text="", selected_tags_json=payload,
    )
    assert row.selected_tags_json == payload
    # upsert 覆盖更新
    row2 = repo.upsert(
        quick_create_task_id=tid, prompt_id="p1", image_index=0,
        leg_foot_bad=False, feedback_text="", selected_tags_json="[]",
    )
    assert row2.id == row.id
    assert row2.selected_tags_json == "[]"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_migrate_feedback_selected_tags.py -v`
Expected: FAIL — `ImportError: cannot import name 'migrate_creation_image_feedbacks_add_selected_tags'`

- [ ] **Step 3: 实现模型列**

`app/models/creation_feedback.py` 在 `feedback_text` 列之后加：

```python
    selected_tags_json = Column(Text, nullable=False, default="[]")
```

- [ ] **Step 4: 实现迁移函数**

`app/models/database.py` 在 `migrate_material_creative_directions_add_home_settings` 之后加（照抄 `migrate_creation_quick_create_tasks_add_seed_prompt` 模式）：

```python
def migrate_creation_image_feedbacks_add_selected_tags() -> None:
    """为 creation_image_feedbacks 补充 selected_tags_json 列（feedback 标签化）。"""
    if not os.path.exists(DB_PATH):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='creation_image_feedbacks'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(
                text("PRAGMA table_info(creation_image_feedbacks)")
            ).fetchall()
            names = {c[1] for c in cols}
            if "selected_tags_json" in names:
                return
            conn.execute(
                text(
                    "ALTER TABLE creation_image_feedbacks ADD COLUMN selected_tags_json TEXT NOT NULL DEFAULT '[]'"
                )
            )
        logger.info("已迁移: creation_image_feedbacks 增加 selected_tags_json 列")
    except Exception as e:
        logger.error(
            f"迁移 creation_image_feedbacks.selected_tags_json 失败: {e}", exc_info=True
        )
        raise
```

并在 `init_db()` 的迁移调用列表末尾（`migrate_material_creative_directions_add_home_settings()` 之后）加：

```python
        migrate_creation_image_feedbacks_add_selected_tags()
```

- [ ] **Step 5: 实现 repo 透传**

`app/repositories/creation_feedback_repository.py` 的 `upsert` 改为：

```python
    def upsert(
        self,
        *,
        quick_create_task_id: str,
        prompt_id: str,
        image_index: int,
        leg_foot_bad: bool,
        feedback_text: str,
        selected_tags_json: str = "[]",
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
        row.selected_tags_json = selected_tags_json or "[]"
        self.db.commit()
        self.db.refresh(row)
        return row
```

- [ ] **Step 6: 跑测试确认通过（含回归）**

Run: `python -m pytest tests/test_migrate_feedback_selected_tags.py tests/test_creation_feedback.py -v`
Expected: PASS（新 3 个 + 原 test_creation_feedback.py 全绿——旧调用不传新参数，默认值兜底）

- [ ] **Step 7: Commit**

```bash
git add app/models/creation_feedback.py app/models/database.py app/repositories/creation_feedback_repository.py tests/test_migrate_feedback_selected_tags.py
git commit -m "feat(feedback): creation_image_feedbacks 加 selected_tags_json 列（迁移 + repo）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 保存链路（schema + service + route + 回显）

**Files:**
- Modify: `app/schemas/creation.py:297-306`
- Modify: `app/services/creation_service/feedback_service.py`（`save_feedback`、`serialize_feedback_row`）
- Modify: `app/routes/creation.py:544-571`（保存路由）
- Test: `tests/test_creation_feedback.py`（改 + 增）
- Test: `tests/routes/test_creation_feedback_routes.py`（改 + 增）

**Interfaces:**
- Consumes: Task 1 的 `normalize_selected_tags` / `derive_leg_foot_bad` / `get_tag_config`；Task 2 的 `upsert(..., selected_tags_json=...)`。
- Produces:
  - `ImageFeedbackSaveRequest.selected_tags: List[ImageFeedbackTagIn]`（默认 `[]`；`ImageFeedbackTagIn = {key: str, severity: Optional[str]}`）。
  - `ImageFeedbackService.save_feedback(..., selected_tags: Optional[List[Dict[str, Any]]] = None)`。
  - `serialize_feedback_row` 返回 dict 新增 `"selected_tags": List[Dict]`（items-hydrated 回显经 `batch_automation_service` 复用此函数自动带上，无需改该文件）。

- [ ] **Step 1: 更新既有断言 + 写新失败测试**

`tests/test_creation_feedback.py`：

(a) `test_save_creates_row_and_returns_payload` 的期望 dict 加一行：

```python
        assert data == {
            "prompt_id": "p1",
            "image_index": 0,
            "leg_foot_bad": True,
            "feedback_text": "袜口花边过重",
            "selected_tags": [],
        }
```

(b) 在 `TestImageFeedbackService` 类末尾追加：

```python
    def test_save_with_tags_normalizes_and_derives_bad(self, db_session):
        task = make_qc_task(db_session)
        data = ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="", leg_foot_bad=False,
            selected_tags=[
                {"key": "sock_wrinkle_heavy", "severity": "severe"},
                {"key": "ghost_tag"},                      # 未知 → 剔除
                {"key": "leg_twist"},                      # 缺 severity → moderate
                {"key": "pos_overall_good", "severity": "minor"},  # 正面 → 剥 severity
            ],
        )
        assert data is not None
        assert data["selected_tags"] == [
            {"key": "sock_wrinkle_heavy", "severity": "severe"},
            {"key": "leg_twist", "severity": "moderate"},
            {"key": "pos_overall_good"},
        ]
        assert data["leg_foot_bad"] is True  # 腿脚负面标签自动推导

    def test_save_non_legfoot_tag_does_not_set_bad(self, db_session):
        task = make_qc_task(db_session)
        data = ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="", leg_foot_bad=False,
            selected_tags=[{"key": "style_doll3d", "severity": "minor"}],
        )
        assert data is not None
        assert data["leg_foot_bad"] is False

    def test_save_checkbox_fallback_with_text_only(self, db_session):
        task = make_qc_task(db_session)
        data = ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="标签覆盖不了的新问题", leg_foot_bad=True, selected_tags=[],
        )
        assert data is not None and data["leg_foot_bad"] is True

    def test_tags_only_counts_as_filled_and_clear_needs_all_empty(self, db_session):
        task = make_qc_task(db_session)
        svc = ImageFeedbackService(db_session)
        # 只有标签也算已填
        data = svc.save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="", leg_foot_bad=False,
            selected_tags=[{"key": "neutral_normal"}],
        )
        assert data is not None
        # 三条件全空 → 删行
        assert svc.save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="  ", leg_foot_bad=False, selected_tags=[],
        ) is None
        assert CreationImageFeedbackRepository(db_session).list_all() == []

    def test_unknown_tags_only_treated_as_empty(self, db_session):
        # 选中的标签全被剔除且无文本无勾选 → 等价清空
        task = make_qc_task(db_session)
        data = ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="", leg_foot_bad=False,
            selected_tags=[{"key": "ghost_tag"}],
        )
        assert data is None
```

`tests/routes/test_creation_feedback_routes.py`：

(c) `test_save_and_clear_feedback` 期望 data 加 `"selected_tags": []`；`test_hydrated_items_include_feedbacks` 期望 feedbacks 元素加 `"selected_tags": []`。

(d) 文件末尾追加：

```python
def test_save_with_selected_tags_roundtrip(api_client, db_session):
    task = _make_qc_task(db_session)
    r = api_client.put(_fb_url(task.id), json={
        "feedback_text": "",
        "leg_foot_bad": False,
        "selected_tags": [
            {"key": "sock_toe_separation", "severity": "minor"},
            {"key": "pos_sock_style"},
        ],
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["selected_tags"] == [
        {"key": "sock_toe_separation", "severity": "minor"},
        {"key": "pos_sock_style"},
    ]
    assert data["leg_foot_bad"] is True  # sock_toe_separation 计 bad

    # 回显同样带标签
    from app.repositories.creation_batch_repository import CreationBatchRepository
    repo = CreationBatchRepository(db_session)
    run = repo.create_run(iterations_total=1, config_json="{}", status="completed")
    item = repo.create_item(
        run_id=run.id, step_index=0, character_id=task.character_id,
        seed_prompt_id="s1", seed_section="general", seed_prompt_text="seed",
        status="completed",
    )
    repo.update_item(item.id, {"quick_create_task_id": task.id})
    r2 = api_client.get("/api/creation/batch-automation/items-hydrated")
    row = next(x for x in r2.json()["data"]["items"] if x["id"] == item.id)
    assert row["feedbacks"][0]["selected_tags"] == [
        {"key": "sock_toe_separation", "severity": "minor"},
        {"key": "pos_sock_style"},
    ]


def test_save_body_without_selected_tags_still_works(api_client, db_session):
    # 向后兼容：旧 body 不带 selected_tags
    task = _make_qc_task(db_session)
    r = api_client.put(_fb_url(task.id), json={"feedback_text": "老格式", "leg_foot_bad": False})
    assert r.status_code == 200
    assert r.json()["data"]["selected_tags"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_creation_feedback.py tests/routes/test_creation_feedback_routes.py -v`
Expected: FAIL — 新增测试报 `TypeError: save_feedback() got an unexpected keyword argument 'selected_tags'`；既有改动断言报 KeyError/AssertionError（缺 `selected_tags` 字段）

- [ ] **Step 3: 实现 schema**

`app/schemas/creation.py` 把 297-306 行改为（`Field`、`List`、`Optional` 该文件顶部已有导入则复用，缺则补）：

```python
class ImageFeedbackTagIn(BaseModel):
    key: str
    severity: Optional[str] = None


class ImageFeedbackSaveRequest(BaseModel):
    feedback_text: str = ""
    leg_foot_bad: bool = False
    selected_tags: List[ImageFeedbackTagIn] = Field(default_factory=list)


class ImageFeedbackOut(BaseModel):
    prompt_id: str
    image_index: int
    leg_foot_bad: bool
    feedback_text: str
    selected_tags: List[Dict[str, Any]] = Field(default_factory=list)
```

（`Dict`/`Any` 如未导入则在文件顶部 typing import 中补上。）

- [ ] **Step 4: 实现 service**

`app/services/creation_service/feedback_service.py`：

(a) 文件顶部加 `import json`，并加导入：

```python
from app.services.creation_service import feedback_tags
```

(b) `serialize_feedback_row` 改为：

```python
def serialize_feedback_row(row: CreationImageFeedback) -> Dict[str, Any]:
    try:
        selected = json.loads(row.selected_tags_json or "[]")
    except (TypeError, ValueError):
        selected = []
    return {
        "prompt_id": row.prompt_id,
        "image_index": int(row.image_index),
        "leg_foot_bad": bool(row.leg_foot_bad),
        "feedback_text": row.feedback_text or "",
        "selected_tags": selected if isinstance(selected, list) else [],
    }
```

(c) `save_feedback` 改为：

```python
    def save_feedback(
        self,
        *,
        task_id: str,
        prompt_id: str,
        image_index: int,
        feedback_text: str,
        leg_foot_bad: bool,
        selected_tags: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        tid = (task_id or "").strip()
        pid = (prompt_id or "").strip()
        if not tid or not pid:
            raise ValueError("task_id / prompt_id 无效")
        if self.quick_repo.get_by_id(tid) is None:
            raise ValueError("一键创作任务不存在")

        config = feedback_tags.get_tag_config()
        normalized = feedback_tags.normalize_selected_tags(selected_tags, config)
        text = (feedback_text or "").strip()
        bad = feedback_tags.derive_leg_foot_bad(normalized, bool(leg_foot_bad), config)
        # 清空即删三条件：文本空 且 推导后未标 bad 且 无选中标签
        if not text and not bad and not normalized:
            self.repo.delete_for_image(tid, pid, image_index)
            return None
        row = self.repo.upsert(
            quick_create_task_id=tid,
            prompt_id=pid,
            image_index=image_index,
            leg_foot_bad=bad,
            feedback_text=text,
            selected_tags_json=json.dumps(normalized, ensure_ascii=False),
        )
        return serialize_feedback_row(row)
```

- [ ] **Step 5: 实现路由透传**

`app/routes/creation.py` 的 `save_quick_create_image_feedback` 中 service 调用改为：

```python
        data = ImageFeedbackService(db).save_feedback(
            task_id=tid,
            prompt_id=pid,
            image_index=image_index,
            feedback_text=body.feedback_text,
            leg_foot_bad=body.leg_foot_bad,
            selected_tags=[t.model_dump() for t in body.selected_tags],
        )
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_creation_feedback.py tests/routes/test_creation_feedback_routes.py -v`
Expected: 除 `TestBuildExport` 中断言 images 精确相等的 2 个测试（`test_export_with_batch_item` 因 images dict 现多出 selected_tags 相关字段——Task 4 一并处理）外全绿。若该测试此时尚未受影响（导出未改），则全绿。

注：此时导出尚未动，`build_export` 里 images 是手工组装的 dict（不走 serialize_feedback_row），所以导出测试应全绿。确认：

Run: `python -m pytest tests/test_creation_feedback.py::TestBuildExport -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/schemas/creation.py app/services/creation_service/feedback_service.py app/routes/creation.py tests/test_creation_feedback.py tests/routes/test_creation_feedback_routes.py
git commit -m "feat(feedback): 保存链路支持 selected_tags（校验/severity 兜底/bad 推导/回显）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 导出升 aetherframe_feedback_v2

**Files:**
- Modify: `app/services/creation_service/feedback_service.py`（`build_export`、`_build_record`）
- Test: `tests/test_creation_feedback.py`（TestBuildExport 改 + 增）
- Test: `tests/routes/test_creation_feedback_routes.py`（export 断言改）

**Interfaces:**
- Consumes: Task 1 的 `tag_config_snapshot` / `get_tag_config` / `SEVERITY_LABELS`；Task 3 的 selected_tags 落库数据。
- Produces: 导出 payload——顶层 `schema="aetherframe_feedback_v2"`、顶层 `tag_config`（快照）、每张图 `selected_tags`（对象数组）与 `selected_tag_labels`（`["袜子皱褶过于夸张（严重）", ...]`）。

- [ ] **Step 1: 更新既有断言 + 写新失败测试**

`tests/test_creation_feedback.py`：

(a) `test_export_with_batch_item`：`assert out["schema"] == "aetherframe_feedback_v1"` 改为 `"aetherframe_feedback_v2"`；images 期望改为：

```python
        assert g["images"] == [
            {"image_index": 0, "image_path": "images/a0.png",
             "leg_foot_bad": True, "feedback_text": "脚趾夸张",
             "selected_tags": [], "selected_tag_labels": []},
            {"image_index": 2, "image_path": "images/a2.png",
             "leg_foot_bad": False, "feedback_text": "构图很好",
             "selected_tags": [], "selected_tag_labels": []},
        ]
```

(b) `TestBuildExport` 类末尾追加：

```python
    def test_export_v2_tags_labels_and_config_snapshot(self, db_session):
        task = make_qc_task(db_session, results=QC_RESULTS)
        svc = ImageFeedbackService(db_session)
        svc.save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="", leg_foot_bad=False,
            selected_tags=[
                {"key": "sock_wrinkle_heavy", "severity": "severe"},
                {"key": "pos_sock_style"},
                {"key": "neutral_normal"},
            ],
        )
        out = svc.build_export()
        assert out["schema"] == "aetherframe_feedback_v2"
        # tag_config 快照自包含：含 taxonomy 映射与 leg_foot_bad
        snap = out["tag_config"]
        assert snap["version"] >= 1
        by_key = {t["key"]: t for t in snap["tags"]}
        assert by_key["sock_wrinkle_heavy"]["taxonomy"] == "袜子/皱褶夸张"
        assert by_key["sock_wrinkle_heavy"]["leg_foot_bad"] is True

        img = out["records"][0]["prompt_groups"][0]["images"][0]
        assert img["selected_tags"] == [
            {"key": "sock_wrinkle_heavy", "severity": "severe"},
            {"key": "pos_sock_style"},
            {"key": "neutral_normal"},
        ]
        assert img["selected_tag_labels"] == [
            "袜子皱褶过于夸张（严重）", "袜子样式好看", "正常",
        ]
        assert img["leg_foot_bad"] is True

    def test_export_label_falls_back_to_key_for_removed_tag(self, db_session):
        # 存量数据里的 key 已从配置移除 → label 回落 key，不阻断导出
        from app.repositories.creation_feedback_repository import (
            CreationImageFeedbackRepository,
        )
        task = make_qc_task(db_session, results=QC_RESULTS)
        CreationImageFeedbackRepository(db_session).upsert(
            quick_create_task_id=task.id, prompt_id="p1", image_index=0,
            leg_foot_bad=True, feedback_text="",
            selected_tags_json='[{"key": "retired_tag", "severity": "minor"}]',
        )
        img = ImageFeedbackService(db_session).build_export()[
            "records"][0]["prompt_groups"][0]["images"][0]
        assert img["selected_tag_labels"] == ["retired_tag"]
```

`tests/routes/test_creation_feedback_routes.py`：`test_export_endpoint` 中 schema 断言改 `"aetherframe_feedback_v2"`，并追加一行 `assert "tag_config" in data`。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_creation_feedback.py::TestBuildExport tests/routes/test_creation_feedback_routes.py::test_export_endpoint -v`
Expected: FAIL — schema 仍为 v1、images 缺新字段

- [ ] **Step 3: 实现导出 v2**

`app/services/creation_service/feedback_service.py`：

(a) 新增模块级辅助（放 `serialize_feedback_row` 之后）：

```python
def _selected_tag_labels(
    selected: List[Dict[str, Any]], tag_by_key: Dict[str, Dict[str, Any]]
) -> List[str]:
    """人读标签名：负面带等级后缀「（严重）」；配置里已移除的 key 回落 key。"""
    labels: List[str] = []
    for item in selected:
        key = str(item.get("key") or "")
        tag = tag_by_key.get(key)
        if tag is None:
            labels.append(key)
            continue
        sev = item.get("severity")
        if tag["polarity"] == "negative" and sev in feedback_tags.SEVERITY_LABELS:
            labels.append(f"{tag['label']}（{feedback_tags.SEVERITY_LABELS[sev]}）")
        else:
            labels.append(tag["label"])
    return labels
```

(b) `build_export` 中 `title_maps = ...` 之后、records 循环之前加：

```python
        config = feedback_tags.get_tag_config()
        tag_by_key = {t["key"]: t for t in config.get("tags", [])}
```

records 循环里 `self._build_record(...)` 调用追加参数 `tag_by_key`；return 改为：

```python
        try:
            tag_config = feedback_tags.tag_config_snapshot(config)
        except Exception:
            logger.warning("feedback 导出：tag_config 快照装配失败，输出空快照", exc_info=True)
            tag_config = {"version": 0, "tags": []}
        return {
            "schema": "aetherframe_feedback_v2",
            "exported_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "tag_config": tag_config,
            "records": records,
        }
```

(c) `_build_record` 签名加 `tag_by_key: Dict[str, Dict[str, Any]]`，images 组装改为：

```python
            images = []
            for fb in fbs:
                selected = serialize_feedback_row(fb)["selected_tags"]
                images.append(
                    {
                        "image_index": int(fb.image_index),
                        "image_path": self._image_path(gen[fb.image_index])
                        if 0 <= fb.image_index < len(gen)
                        else "",
                        "leg_foot_bad": bool(fb.leg_foot_bad),
                        "feedback_text": fb.feedback_text or "",
                        "selected_tags": selected,
                        "selected_tag_labels": _selected_tag_labels(selected, tag_by_key),
                    }
                )
```

- [ ] **Step 4: 跑全部后端 feedback 测试确认通过**

Run: `python -m pytest tests/test_creation_feedback.py tests/routes/test_creation_feedback_routes.py tests/test_feedback_tags_config.py tests/test_migrate_feedback_selected_tags.py -v`
Expected: PASS 全绿

- [ ] **Step 5: Commit**

```bash
git add app/services/creation_service/feedback_service.py tests/test_creation_feedback.py tests/routes/test_creation_feedback_routes.py
git commit -m "feat(feedback): 导出升 aetherframe_feedback_v2（selected_tags/labels + tag_config 快照）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 前端数据层（类型 + API 客户端 + hydrate 映射）

**Files:**
- Modify: `page/src/services/creationApi.ts`（`ImageFeedbackEntry` 约 641 行、`saveImageFeedback` 约 648 行、`FeedbackExportImage`/`FeedbackExportPayload` 约 674-706 行、新增 `getFeedbackTags`）
- Modify: `page/src/types/quickCreate.ts:21`
- Modify: `page/src/utils/batchAutomationDisplay.ts:212-215`

**Interfaces:**
- Consumes: Task 1 的 `GET /feedback/tags`、Task 3/4 的响应字段。
- Produces（Task 6 依赖，名称固定）：
  - `creationApi.ts`：`export type FeedbackSeverity = "minor" | "moderate" | "severe"`；`export interface SelectedFeedbackTag { key: string; severity?: FeedbackSeverity }`；`export interface FeedbackTagDef { key: string; label: string; polarity: "positive" | "negative" | "neutral"; leg_foot_bad: boolean }`；`export async function getFeedbackTags(): Promise<{ version: number; tags: FeedbackTagDef[] }>`（模块级 Promise 缓存，失败返回 `{version: 0, tags: []}` 并清缓存下次重试）；`saveImageFeedback` body 类型加 `selected_tags?: SelectedFeedbackTag[]`；`ImageFeedbackEntry` 加 `selected_tags: SelectedFeedbackTag[]`。
  - `quickCreate.ts`：`userFeedback?: { feedbackText: string; legFootBad: boolean; selectedTags: SelectedFeedbackTag[] } | null`。

- [ ] **Step 1: 扩展 creationApi.ts**

(a) `ImageFeedbackEntry` 及其上方加类型：

```typescript
export type FeedbackSeverity = "minor" | "moderate" | "severe";

export interface SelectedFeedbackTag {
  key: string;
  severity?: FeedbackSeverity;
}

export interface FeedbackTagDef {
  key: string;
  label: string;
  polarity: "positive" | "negative" | "neutral";
  leg_foot_bad: boolean;
}

export interface FeedbackTagConfig {
  version: number;
  tags: FeedbackTagDef[];
}

export interface ImageFeedbackEntry {
  prompt_id: string;
  image_index: number;
  leg_foot_bad: boolean;
  feedback_text: string;
  selected_tags: SelectedFeedbackTag[];
}
```

(b) `saveImageFeedback` 的 body 参数类型改为：

```typescript
  body: { feedback_text: string; leg_foot_bad: boolean; selected_tags?: SelectedFeedbackTag[] }
```

（函数体不变——body 原样 JSON.stringify。）

(c) `exportImageFeedback` 相关类型同步：`FeedbackExportImage` 加 `selected_tags: SelectedFeedbackTag[]; selected_tag_labels: string[];`，`FeedbackExportPayload` 加 `tag_config: FeedbackTagConfig;`。

(d) 文件末尾加（与既有函数同样使用 `API_BASE`/`fetchWithTimeout`/`parseJson`/`throwIfError`/`rethrow`）：

```typescript
let feedbackTagsCache: Promise<FeedbackTagConfig> | null = null;

/** 拉取 feedback 标签配置（模块级缓存；失败降级空词表并允许下次重试） */
export function getFeedbackTags(): Promise<FeedbackTagConfig> {
  if (!feedbackTagsCache) {
    feedbackTagsCache = (async () => {
      const url = `${API_BASE}/feedback/tags`;
      try {
        const response = await fetchWithTimeout(url, { method: "GET" });
        const data = await parseJson<FeedbackTagConfig>(response);
        throwIfError(response, data);
        return (data.data ?? { version: 0, tags: [] }) as FeedbackTagConfig;
      } catch {
        feedbackTagsCache = null; // 失败不缓存，下次打开弹窗重试
        return { version: 0, tags: [] };
      }
    })();
  }
  return feedbackTagsCache;
}
```

- [ ] **Step 2: 扩展 quickCreate.ts 类型**

`page/src/types/quickCreate.ts` 第 21 行改为（顶部加 `import type { SelectedFeedbackTag } from "@/services/creationApi";`）：

```typescript
  /** 已填的人工 feedback（null/undefined = 未填） */
  userFeedback?: {
    feedbackText: string;
    legFootBad: boolean;
    selectedTags: SelectedFeedbackTag[];
  } | null;
```

- [ ] **Step 3: 更新 hydrate 映射**

`page/src/utils/batchAutomationDisplay.ts` 第 213-215 行改为：

```typescript
        return fb
          ? {
              ...base,
              userFeedback: {
                feedbackText: fb.feedback_text,
                legFootBad: fb.leg_foot_bad,
                selectedTags: fb.selected_tags ?? [],
              },
            }
          : base;
```

- [ ] **Step 4: type-check 验证**

Run: `cd page; npm run type-check`
Expected: 若 `BatchCreationPage.tsx` 因 `userFeedback` 新必填字段 `selectedTags` 报错（约 210 行 `nextFb` 构造），先在此处最小修补：`const nextFb = filled ? { feedbackText: text, legFootBad, selectedTags: [] } : null;`（Task 6 会重写此段）。最终 Expected: PASS 无错误。

- [ ] **Step 5: Commit**

```bash
git add page/src/services/creationApi.ts page/src/types/quickCreate.ts page/src/utils/batchAutomationDisplay.ts page/src/pages/home/components/BatchCreationPage.tsx
git commit -m "feat(feedback): 前端数据层支持 selected_tags（类型/标签 API/hydrate 映射）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

（若 Step 4 无需修补 BatchCreationPage.tsx 则不加该文件。）

---

### Task 6: ImageFeedbackModal 标签化改版 + 接线

**Files:**
- Modify: `page/src/pages/home/components/ImageFeedbackModal.tsx`（整体改版）
- Modify: `page/src/pages/home/components/BatchTaskCard.tsx:20-25, 453-460`（onSaveFeedback 签名 + modal onSave）
- Modify: `page/src/pages/home/components/BatchCreationPage.tsx:195-215`（handleSaveFeedback）

**Interfaces:**
- Consumes: Task 5 的 `getFeedbackTags` / `FeedbackTagDef` / `SelectedFeedbackTag` / 扩展后的 `saveImageFeedback`。
- Produces: `ImageFeedbackModalProps.onSave: (feedbackText: string, legFootBad: boolean, selectedTags: SelectedFeedbackTag[]) => Promise<void>`；`BatchTaskCardProps.onSaveFeedback` 尾参同步加 `selectedTags: SelectedFeedbackTag[]`。

- [ ] **Step 1: 改版 ImageFeedbackModal.tsx**

整文件替换为：

```tsx
import { useState, useCallback, useEffect } from "react";
import { getFeedbackTags } from "@/services/creationApi";
import type { FeedbackTagDef, FeedbackSeverity, SelectedFeedbackTag } from "@/services/creationApi";
import type { QuickCreateImage } from "@/types/quickCreate";

interface ImageFeedbackModalProps {
  image: QuickCreateImage;
  promptTitle: string;
  onSave: (
    feedbackText: string,
    legFootBad: boolean,
    selectedTags: SelectedFeedbackTag[]
  ) => Promise<void>;
  onClose: () => void;
}

/** 负面标签点击循环：未选 → 轻微 → 中等 → 严重 → 取消 */
const SEVERITY_CYCLE: (FeedbackSeverity | null)[] = ["minor", "moderate", "severe", null];
const SEVERITY_SHORT: Record<FeedbackSeverity, string> = {
  minor: "轻",
  moderate: "中",
  severe: "重",
};
/** 负面胶囊底色随等级加深 */
const SEVERITY_BG: Record<FeedbackSeverity, string> = {
  minor: "rgba(253,164,175,0.25)",
  moderate: "rgba(244,114,182,0.45)",
  severe: "rgba(225,29,72,0.75)",
};

function TagPill({
  tag,
  selected,
  onClick,
}: {
  tag: FeedbackTagDef;
  selected: SelectedFeedbackTag | undefined;
  onClick: () => void;
}) {
  const isOn = selected !== undefined;
  let bg = "rgba(0,0,0,0.04)";
  let color = "#9ca3af";
  let border = "1px solid rgba(0,0,0,0.08)";
  let suffix = "";
  if (isOn) {
    if (tag.polarity === "negative" && selected?.severity) {
      bg = SEVERITY_BG[selected.severity];
      color = selected.severity === "severe" ? "white" : "#be123c";
      border = "1px solid rgba(225,29,72,0.35)";
      suffix = `·${SEVERITY_SHORT[selected.severity]}`;
    } else if (tag.polarity === "positive") {
      bg = "rgba(74,222,128,0.35)";
      color = "#15803d";
      border = "1px solid rgba(34,197,94,0.4)";
    } else {
      bg = "rgba(148,163,184,0.35)";
      color = "#475569";
      border = "1px solid rgba(100,116,139,0.4)";
    }
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-2.5 py-1 rounded-full text-xs cursor-pointer transition-all duration-150 whitespace-nowrap"
      style={{ background: bg, color, border, fontFamily: "'ZCOOL KuaiLe', cursive" }}
    >
      {tag.label}
      {suffix}
    </button>
  );
}

/** 单张产线出图的人工 feedback 弹窗：标签点选（负面带等级）+ 自由文本 + 兜底勾选 */
export default function ImageFeedbackModal({
  image,
  promptTitle,
  onSave,
  onClose,
}: ImageFeedbackModalProps) {
  const [tagDefs, setTagDefs] = useState<FeedbackTagDef[]>([]);
  const [selected, setSelected] = useState<SelectedFeedbackTag[]>(
    image.userFeedback?.selectedTags ?? []
  );
  const [text, setText] = useState(image.userFeedback?.feedbackText ?? "");
  const [manualBad, setManualBad] = useState(image.userFeedback?.legFootBad ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void getFeedbackTags().then((cfg) => {
      if (alive) setTagDefs(cfg.tags);
    });
    return () => {
      alive = false;
    };
  }, []);

  const defByKey = new Map(tagDefs.map((t) => [t.key, t] as const));
  const derivedBad = selected.some((s) => defByKey.get(s.key)?.leg_foot_bad);
  const effectiveBad = derivedBad || manualBad;

  const toggleTag = useCallback((tag: FeedbackTagDef) => {
    setSelected((prev) => {
      const idx = prev.findIndex((s) => s.key === tag.key);
      if (tag.polarity !== "negative") {
        return idx >= 0
          ? prev.filter((s) => s.key !== tag.key)
          : [...prev, { key: tag.key }];
      }
      const cur = idx >= 0 ? (prev[idx].severity ?? "moderate") : null;
      const next = SEVERITY_CYCLE[(SEVERITY_CYCLE.indexOf(cur) + 1) % SEVERITY_CYCLE.length];
      if (next === null) return prev.filter((s) => s.key !== tag.key);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { key: tag.key, severity: next };
        return copy;
      }
      return [...prev, { key: tag.key, severity: next }];
    });
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(text, manualBad, selected);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }, [onSave, onClose, text, manualBad, selected]);

  const negatives = tagDefs.filter((t) => t.polarity === "negative");
  const positives = tagDefs.filter((t) => t.polarity === "positive");
  const neutrals = tagDefs.filter((t) => t.polarity === "neutral");
  const groups: Array<{ title: string; items: FeedbackTagDef[] }> = [
    { title: "问题标签（点击切换 轻/中/重）", items: negatives },
    { title: "亮点标签", items: positives },
    { title: "中立", items: neutrals },
  ];

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
        onClick={saving ? undefined : onClose}
      />
      <div
        className="relative w-[30rem] max-w-[calc(100vw-2rem)] max-h-[calc(100vh-4rem)] overflow-y-auto rounded-3xl mx-4"
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

          {tagDefs.length > 0 && (
            <div className="mb-3 space-y-2">
              {groups.map(
                (g) =>
                  g.items.length > 0 && (
                    <div key={g.title}>
                      <p className="text-xs text-rose-400/70 mb-1">{g.title}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {g.items.map((t) => (
                          <TagPill
                            key={t.key}
                            tag={t}
                            selected={selected.find((s) => s.key === t.key)}
                            onClick={() => toggleTag(t)}
                          />
                        ))}
                      </div>
                    </div>
                  )
              )}
            </div>
          )}

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={2}
            placeholder="标签覆盖不了的新问题写这里…"
            className="w-full rounded-xl p-3 text-sm text-rose-700/80 resize-none focus:outline-none"
            style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.25)" }}
          />

          <label
            className="flex items-center gap-2 mt-3 select-none"
            style={{ cursor: derivedBad ? "not-allowed" : "pointer" }}
          >
            <input
              type="checkbox"
              checked={effectiveBad}
              disabled={derivedBad}
              onChange={(e) => setManualBad(e.target.checked)}
              className="w-4 h-4 accent-rose-400"
            />
            <span
              className="text-sm font-medium text-rose-600"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              腿脚崩坏
            </span>
            <span className="text-xs text-rose-300/60">
              {derivedBad ? "（已由标签推导）" : "（计入 Case 的 bad 计数）"}
            </span>
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

- [ ] **Step 2: 接线 BatchTaskCard.tsx**

(a) 顶部类型导入加：`import type { SelectedFeedbackTag } from "@/services/creationApi";`

(b) `onSaveFeedback` prop 签名（约 20-25 行）改为：

```typescript
  onSaveFeedback: (
    taskId: string,
    img: QuickCreateImage,
    feedbackText: string,
    legFootBad: boolean,
    selectedTags: SelectedFeedbackTag[]
  ) => Promise<void>;
```

(c) modal 挂载处（约 457 行）改为：

```tsx
          onSave={(text, bad, tags) => onSaveFeedback(task.id, feedbackTarget, text, bad, tags)}
```

- [ ] **Step 3: 接线 BatchCreationPage.tsx**

`handleSaveFeedback`（约 195-215 行）改为——用保存响应回填本地 state（后端是归一化与推导的唯一权威）：

```typescript
  const handleSaveFeedback = useCallback(
    async (
      taskId: string,
      img: QuickCreateImage,
      feedbackText: string,
      legFootBad: boolean,
      selectedTags: SelectedFeedbackTag[]
    ) => {
      const task = tasks.find((t) => t.id === taskId);
      if (!task?.quickCreateRecordId) {
        throw new ApiError("该记录缺少美图创作任务，无法保存 feedback", 400);
      }
      if (typeof img.imageIndex !== "number") {
        throw new ApiError("图片索引缺失，无法保存 feedback", 400);
      }
      const text = feedbackText.trim();
      const saved = await creationApi.saveImageFeedback(
        task.quickCreateRecordId,
        img.promptId,
        img.imageIndex,
        { feedback_text: text, leg_foot_bad: legFootBad, selected_tags: selectedTags }
      );
      const nextFb = saved
        ? {
            feedbackText: saved.feedback_text,
            legFootBad: saved.leg_foot_bad,
            selectedTags: saved.selected_tags ?? [],
          }
        : null;
      const patchImg = (im: QuickCreateImage) =>
        im.id === img.id ? { ...im, userFeedback: nextFb } : im;
```

（`patchImg` 之后的 `setTasks` 逻辑保持原样；顶部补 `import type { SelectedFeedbackTag } from "@/services/creationApi";`——若该文件以 `creationApi.saveImageFeedback` 命名空间方式调用则保持一致。Task 5 Step 4 若加过临时 `selectedTags: []` 修补，此处一并被本段替换。）

- [ ] **Step 4: type-check + lint**

Run: `cd page; npm run type-check; npm run lint`
Expected: 两者 exit 0 无错误

- [ ] **Step 5: 后端全量回归**

Run: `python -m pytest tests/ -v --ignore=tests/experiments`
Expected: PASS（无既有测试因本次改动回归失败）

- [ ] **Step 6: Commit**

```bash
git add page/src/pages/home/components/ImageFeedbackModal.tsx page/src/pages/home/components/BatchTaskCard.tsx page/src/pages/home/components/BatchCreationPage.tsx
git commit -m "feat(feedback): ImageFeedbackModal 标签化改版（三组胶囊 + 四态等级循环 + 兜底勾选）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review 记录

- **Spec 覆盖**：§1 词表/配置 → Task 1；§2 模型迁移/清空即删 → Task 2/3；§3.1 tags API + 退化 → Task 1；§3.2 保存校验/推导 → Task 3；§3.3 回显 → Task 3（serialize 复用）；§4 UI 四态/兜底置灰/退化隐藏标签区 → Task 6（`tagDefs.length > 0` 条件渲染）；§5.1 导出 v2 + 快照 + 存量空数组 → Task 4；§5.2 归档口径为 Claude 侧约定（无代码任务，spec 已记录）；§6 错误处理 → Task 1/3/4 分散实现；§7 测试矩阵 → 各 Task 的测试步骤；§8 不做项 → 无对应任务，符合。
- **占位符扫描**：无 TBD/TODO/「类似 Task N」；所有代码步骤给出完整代码。
- **类型一致性**：`selected_tags`（后端蛇形）/`selectedTags`（前端驼峰）边界在 creationApi 响应映射处（`saved.selected_tags` → `selectedTags`）；`SelectedFeedbackTag`、`FeedbackTagDef`、`getFeedbackTags`、`normalize_selected_tags` 等名称在产出/消费任务间逐一核对一致。
- **既有测试影响**：serialize 字段新增会破坏 `test_creation_feedback.py`/`test_creation_feedback_routes.py` 的精确断言——已在 Task 3/4 Step 1 中明确列出改动点，不会漏。
