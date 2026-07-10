# Feedback 弹窗体验优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 负面标签按 5 组分类展示、严重程度「轻/中/重」任意等级一次点选、移除「腿脚崩坏」勾选框改为纯标签推导（含存量数据一次性重算迁移）、弹窗加宽到 52rem。

**Architecture:** 在 2026-07-09 标签化改版之上增量演化。配置文件 `feedback_tags.yaml` 负面标签加 `group` 字段并按组重排（后端加载器解析、API 下发、导出快照自然携带）；后端 `derive_leg_foot_bad` 去掉 checkbox 参数变纯推导，清空即删从三条件简化为两条件；`app_migrations` 元表守卫的一次性数据迁移重算全库存量行；前端弹窗重写为分组 + 常显分段式胶囊，删除勾选框及 `manualBad` 状态。数据模型与导出 schema（aetherframe_feedback_v2）不变。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite（后端），React 19 + TypeScript + Tailwind（前端），pytest。

**设计文档（唯一事实来源）：** `docs/superpowers/specs/2026-07-10-feedback-modal-ux-design.md`

## Global Constraints

- `app/tools/llm/config.py` 含 API key、已 gitignore，永不提交。
- `.claude/settings.local.json` 有用户本地改动，永不 stage / 提交。
- 冻结实验物永不编辑：`experiments/variants/**`、`benchmark_v1/v3.yaml`、`experiments/results/**`。
- Case 原文与已定稿 tags/taxonomy_version 永不回改。
- 每个 Task 结束时按计划 commit（用户已批准的 SDD 流程）；**push 未获授权，不得执行**。
- 标签 `key` 一经启用不得复用为其他含义；本计划不改任何既有 key/label/taxonomy/leg_foot_bad，只加 `group` 和重排。
- API 响应一律 `ApiResponse(success, data, message)` 包裹。
- 前端 React hooks 显式 import（`npm run type-check` 不认 auto-imports）。
- **预存环境债（非本计划引入，勿修勿理）：** `tests/test_bio_walk_migration.py`、`tests/test_migrate_batch_items_add_dir_id.py` 在当前环境有 7-8 个失败（基线 f4d0911 即已失败）；`npm run lint` 有 11 条预存警告（全在本计划不触碰的文件里）。验证时跑**指定测试文件**并保证零新增失败/警告即可。

---

### Task 1: 标签配置分组（yaml `group` 字段 + 加载器 + API 下发）

**Files:**
- Modify: `app/config/feedback_tags.yaml`（全量重写：负面按 5 组重排 + 加 group）
- Modify: `app/services/creation_service/feedback_tags.py:50-54`（load_tag_config 解析 group）、`:112-125`（tags_for_api 下发 group）
- Test: `tests/test_feedback_tags_config.py`

**Interfaces:**
- Consumes: 现有 `load_tag_config` / `tags_for_api`（`app/services/creation_service/feedback_tags.py`）。
- Produces: 配置里每个 **negative** 标签必有 `group: str`（缺失默认 `"其他"`）；`tags_for_api` 每个条目多一个 `"group"` 键——negative 为组名字符串，positive/neutral 为 `None`（JSON null）。前端（Task 4）依赖 `FeedbackTagDef.group: string | null`。导出快照（deepcopy）自动携带 group，无需改 `tag_config_snapshot`。

- [ ] **Step 1: 更新既有断言并新增分组测试（先写失败测试）**

`tests/test_feedback_tags_config.py` 改动三处：

(a) `SMALL_CONFIG`（第 23-30 行）负面条目加 group：

```python
SMALL_CONFIG = """
    version: 7
    tags:
      - { key: sock_wrinkle_heavy, label: 袜子皱褶过于夸张, polarity: negative, leg_foot_bad: true, taxonomy: 袜子/皱褶夸张, group: 袜子 }
      - { key: style_doll3d, label: 3D玩偶感, polarity: negative, leg_foot_bad: false, taxonomy: 画风/3D玩偶感, group: 画风 }
      - { key: pos_overall_good, label: 整体效果好, polarity: positive }
      - { key: neutral_normal, label: 正常, polarity: neutral }
"""
```

(b) `TestLoad` 内：`test_load_valid_config` 在 `assert neg["taxonomy"] == ...` 后追加一行 `assert neg["group"] == "袜子"`；新增两个测试；`test_get_tag_config_reads_repo_file` 末尾追加仓库配置的分组断言：

```python
    def test_load_negative_missing_group_defaults_other(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, """
            version: 1
            tags:
              - { key: no_group_tag, label: 无分组, polarity: negative, leg_foot_bad: true, taxonomy: 其他/未分类 }
        """))
        assert cfg["tags"][0]["group"] == "其他"

    def test_load_positive_neutral_have_no_group(self, tmp_path):
        cfg = load_tag_config(_write_config(tmp_path, SMALL_CONFIG))
        assert "group" not in cfg["tags"][2]  # positive
        assert "group" not in cfg["tags"][3]  # neutral
```

`test_get_tag_config_reads_repo_file` 末尾追加：

```python
        groups = [t["group"] for t in cfg["tags"] if t["polarity"] == "negative"]
        assert set(groups) == {"袜子", "脚部", "腿部与姿势", "画风", "脸部与身体"}
        assert groups[0] == "袜子"  # 生产最高频组排最前
```

(c) `TestViews.test_tags_for_api_strips_taxonomy` 的两个精确断言字典各加 group 键：

```python
        assert view["tags"][0] == {
            "key": "sock_wrinkle_heavy", "label": "袜子皱褶过于夸张",
            "polarity": "negative", "leg_foot_bad": True, "group": "袜子",
        }
        assert view["tags"][2] == {
            "key": "pos_overall_good", "label": "整体效果好",
            "polarity": "positive", "leg_foot_bad": False, "group": None,
        }
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_feedback_tags_config.py -v`
Expected: 上述新增/改动断言 FAIL（KeyError `group` / 字典不等），其余 PASS。

- [ ] **Step 3: 实现——yaml 全量重写 + 加载器**

`app/config/feedback_tags.yaml` 整文件替换为（仅重排 + 加 group + version 升 2 + 注释更新；所有 key/label/taxonomy/leg_foot_bad 与现状逐字一致）：

```yaml
# 生产 feedback 标签词表（设计文档 docs/superpowers/specs/2026-07-10-feedback-modal-ux-design.md §1）
# key 一经启用不得复用为其他含义；改 label 措辞 / taxonomy 映射 / group 分组 / 增删标签只改本文件，重启生效。
# polarity: positive | negative | neutral；leg_foot_bad / taxonomy / group 仅 negative 有意义。
# 组间展示顺序 = 该组首个标签在本文件中的出现顺序；组内顺序 = 本文件顺序。
version: 2
tags:
  # ---- 负面 · 袜子（选中即计 bad；生产最高频组排最前）----
  - { key: sock_painted,        label: 袜子上色感,                   polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/上色感,         group: 袜子 }
  - { key: sock_toe_separation, label: 脚趾分离感,                   polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/上色感,         group: 袜子 }
  - { key: sock_plastic,        label: 袜子塑料袋感,                 polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/塑料袋感,       group: 袜子 }
  - { key: sock_wrinkle_heavy,  label: 袜子皱褶过于夸张,             polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/皱褶夸张,       group: 袜子 }
  - { key: sock_missing,        label: 袜子缺失,                     polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/缺失,           group: 袜子 }
  - { key: sock_shoes,          label: 错误穿鞋,                     polarity: negative, leg_foot_bad: true,  taxonomy: 袜子/穿鞋,           group: 袜子 }
  # ---- 负面 · 脚部（选中即计 bad）----
  - { key: foot_crude,          label: 脚部简陋,                     polarity: negative, leg_foot_bad: true,  taxonomy: 脚部/简陋,           group: 脚部 }
  - { key: foot_exaggerated,    label: 脚部细节夸张,                 polarity: negative, leg_foot_bad: true,  taxonomy: 脚部/夸张,           group: 脚部 }
  - { key: foot_proportion,     label: 脚部比例结构异常,             polarity: negative, leg_foot_bad: true,  taxonomy: 脚部/比例结构,       group: 脚部 }
  - { key: foot_tip_discolor,   label: 脚尖变色,                     polarity: negative, leg_foot_bad: true,  taxonomy: 脚部/脚尖变色,       group: 脚部 }
  # ---- 负面 · 腿部与姿势（选中即计 bad）----
  - { key: leg_multi_missing,   label: 多肢/缺肢,                    polarity: negative, leg_foot_bad: true,  taxonomy: 腿部/结构错误,       group: 腿部与姿势 }
  - { key: leg_twist,           label: 腿部异常扭曲（含脚尖反向）,   polarity: negative, leg_foot_bad: true,  taxonomy: 腿部/结构错误,       group: 腿部与姿势 }
  - { key: pose_weird,          label: 姿势诡异（不符合人类正常姿势）, polarity: negative, leg_foot_bad: true,  taxonomy: 其他/未分类,         group: 腿部与姿势 }
  - { key: leg_proportion,      label: 腿部比例失调（过粗/过细）,    polarity: negative, leg_foot_bad: true,  taxonomy: 身体比例/整体不协调, group: 腿部与姿势 }
  # ---- 负面 · 画风（不计 bad）----
  - { key: style_realistic,     label: 画风写实化,                   polarity: negative, leg_foot_bad: false, taxonomy: 画风/写实化,         group: 画风 }
  - { key: style_flat2d,        label: 画风平面2D,                   polarity: negative, leg_foot_bad: false, taxonomy: 画风/平面2D,         group: 画风 }
  - { key: style_doll3d,        label: 3D玩偶感,                     polarity: negative, leg_foot_bad: false, taxonomy: 画风/3D玩偶感,       group: 画风 }
  # ---- 负面 · 脸部与身体（不计 bad）----
  - { key: face_collapse,       label: 脸部细节崩坏,                 polarity: negative, leg_foot_bad: false, taxonomy: 其他/未分类,         group: 脸部与身体 }
  - { key: face_anchor_lost,    label: 视觉锚点丢失,                 polarity: negative, leg_foot_bad: false, taxonomy: 其他/未分类,         group: 脸部与身体 }
  - { key: face_expression,     label: 表情诡异,                     polarity: negative, leg_foot_bad: false, taxonomy: 其他/未分类,         group: 脸部与身体 }
  - { key: body_proportion,     label: 身体比例不协调,               polarity: negative, leg_foot_bad: false, taxonomy: 身体比例/整体不协调, group: 脸部与身体 }
  # ---- 正面 ----
  - { key: pos_sock_style,      label: 袜子样式好看,                 polarity: positive }
  - { key: pos_leg_natural,     label: 腿脚自然,                     polarity: positive }
  - { key: pos_overall_good,    label: 整体效果好,                   polarity: positive }
  # ---- 中立 ----
  - { key: neutral_normal,      label: 正常,                         polarity: neutral }
```

`app/services/creation_service/feedback_tags.py` 两处：

`load_tag_config` 的 negative 分支（现第 51-53 行）追加一行：

```python
        if polarity == "negative":
            entry["leg_foot_bad"] = bool(t.get("leg_foot_bad", False))
            entry["taxonomy"] = str(t.get("taxonomy") or "其他/未分类").strip()
            entry["group"] = str(t.get("group") or "其他").strip()
```

`tags_for_api`（现第 112-125 行）条目加 group（docstring 同步）：

```python
def tags_for_api(config: Dict[str, Any]) -> Dict[str, Any]:
    """前端下发视图：剥离 taxonomy（前端用不到），leg_foot_bad 统一补齐布尔，group 下发（非负面为 None）。"""
    return {
        "version": config.get("version", 0),
        "tags": [
            {
                "key": t["key"],
                "label": t["label"],
                "polarity": t["polarity"],
                "leg_foot_bad": bool(t.get("leg_foot_bad", False)),
                "group": t.get("group"),
            }
            for t in config.get("tags", [])
        ],
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_feedback_tags_config.py tests/routes/test_creation_feedback_routes.py -v`
Expected: `test_feedback_tags_config.py` 全 PASS；**`test_creation_feedback_routes.py::test_feedback_tags_api` 会 FAIL**（精确字典断言缺 group）——在该测试的期望字典里加 `"group": "袜子"`：

```python
    assert by_key["sock_wrinkle_heavy"] == {
        "key": "sock_wrinkle_heavy", "label": "袜子皱褶过于夸张",
        "polarity": "negative", "leg_foot_bad": True, "group": "袜子",
    }
```

重跑同命令，Expected: 全 PASS。

- [ ] **Step 5: 全量回归 + Commit**

Run: `pytest tests/test_feedback_tags_config.py tests/test_creation_feedback.py tests/routes/test_creation_feedback_routes.py tests/test_migrate_feedback_selected_tags.py -v`
Expected: 全 PASS（导出快照 deepcopy 自动带 group，不影响既有断言）。

```bash
git add app/config/feedback_tags.yaml app/services/creation_service/feedback_tags.py tests/test_feedback_tags_config.py tests/routes/test_creation_feedback_routes.py
git commit -m "feat(feedback): 标签配置加 group 分组并按组重排，API 下发 group"
```

---

### Task 2: bad 纯标签推导 + 两条件清空（后端保存链路）

**Files:**
- Modify: `app/services/creation_service/feedback_tags.py:100-109`（derive_leg_foot_bad 去 checkbox 参数）
- Modify: `app/services/creation_service/feedback_service.py:65-98`（save_feedback 去 leg_foot_bad 参数、两条件清空）
- Modify: `app/schemas/creation.py:302-305`（leg_foot_bad 标注 deprecated）
- Modify: `app/routes/creation.py:557-565`（不再透传 body.leg_foot_bad）
- Test: `tests/test_feedback_tags_config.py`（TestDeriveBad）、`tests/test_creation_feedback.py`、`tests/routes/test_creation_feedback_routes.py`、`tests/test_batch_automation_hydrated_equivalence.py`

**Interfaces:**
- Consumes: Task 1 后的 `feedback_tags` 模块。
- Produces: `derive_leg_foot_bad(normalized: List[Dict], config: Dict) -> bool`（**两参数**）；`ImageFeedbackService.save_feedback(*, task_id, prompt_id, image_index, feedback_text, selected_tags=None)`（**无 leg_foot_bad 参数**）。Task 3 的迁移依赖新版两参数 `derive_leg_foot_bad`。请求体 `ImageFeedbackSaveRequest.leg_foot_bad` 字段保留（默认 False）但值被忽略。

- [ ] **Step 1: 更新测试为新语义（先写失败测试）**

(a) `tests/test_feedback_tags_config.py` 的 `TestDeriveBad` 整类替换（两参数签名、无 checkbox 兜底）：

```python
class TestDeriveBad:
    def _cfg(self, tmp_path):
        return load_tag_config(_write_config(tmp_path, SMALL_CONFIG))

    def test_legfoot_negative_tag_implies_bad(self, tmp_path):
        assert derive_leg_foot_bad(
            [{"key": "sock_wrinkle_heavy", "severity": "minor"}], self._cfg(tmp_path)
        ) is True

    def test_non_legfoot_negative_does_not_imply(self, tmp_path):
        assert derive_leg_foot_bad(
            [{"key": "style_doll3d", "severity": "severe"}], self._cfg(tmp_path)
        ) is False

    def test_no_tags_or_positive_only_is_false(self, tmp_path):
        cfg = self._cfg(tmp_path)
        assert derive_leg_foot_bad([], cfg) is False
        assert derive_leg_foot_bad([{"key": "pos_overall_good"}], cfg) is False
```

(b) `tests/test_creation_feedback.py`——**所有** `save_feedback(...)` 调用删掉 `leg_foot_bad=...` 实参（repo `upsert(... leg_foot_bad=...)` 调用**不动**，repo 层字段照旧）。涉及行：101、115、117、122、128、137、146、155、175、185、195、202、211、260、262、298、312、314、330、338、348。其中语义变化的四处：

`test_save_creates_row_and_returns_payload`（第 96-109 行）——纯文本不再计 bad：

```python
    def test_save_creates_row_and_returns_payload(self, db_session):
        task = make_qc_task(db_session)
        svc = ImageFeedbackService(db_session)
        data = svc.save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="袜口花边过重",
        )
        assert data == {
            "prompt_id": "p1",
            "image_index": 0,
            "leg_foot_bad": False,  # 勾选框已移除：纯文本不计 bad，bad 纯标签推导
            "feedback_text": "袜口花边过重",
            "selected_tags": [],
        }
```

`test_save_only_checkbox_is_filled`（第 124-130 行）整个替换为：

```python
    def test_no_text_no_tags_is_empty_regardless_of_flag(self, db_session):
        # 「仅勾选」场景已不存在：文本空且无标签 → 两条件清空即删
        task = make_qc_task(db_session)
        data = ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=2, feedback_text="",
        )
        assert data is None
```

`test_save_checkbox_fallback_with_text_only`（第 181-187 行）整个替换为：

```python
    def test_text_only_does_not_set_bad(self, db_session):
        task = make_qc_task(db_session)
        data = ImageFeedbackService(db_session).save_feedback(
            task_id=task.id, prompt_id="p1", image_index=0,
            feedback_text="标签覆盖不了的新问题", selected_tags=[],
        )
        assert data is not None and data["leg_foot_bad"] is False
```

`TestBuildExport.test_export_with_batch_item`（第 285-292 行）期望里 image 0 的 `"leg_foot_bad": True` 改为 `False`（该行原靠手动勾选置 True）。

(c) `tests/routes/test_creation_feedback_routes.py::test_save_and_clear_feedback`（第 51-65 行）——body 传 `leg_foot_bad: True` 被忽略：

```python
def test_save_and_clear_feedback(api_client, db_session):
    task = _make_qc_task(db_session)
    # body 里 deprecated 的 leg_foot_bad=True 被忽略：无 bad 标签 → 落库 False
    r = api_client.put(_fb_url(task.id), json={"feedback_text": "脚部简陋", "leg_foot_bad": True})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"] == {
        "prompt_id": "p1", "image_index": 0,
        "leg_foot_bad": False, "feedback_text": "脚部简陋",
        "selected_tags": [],
    }
    # 清空即删
    r2 = api_client.put(_fb_url(task.id), json={"feedback_text": "", "leg_foot_bad": False})
    assert r2.status_code == 200
    assert r2.json()["data"] is None
```

(d) `tests/test_batch_automation_hydrated_equivalence.py` 第 209-215 行删掉 `leg_foot_bad=True,`，第 233 行附近期望 `"leg_foot_bad": True` 改为 `False`。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_feedback_tags_config.py::TestDeriveBad tests/test_creation_feedback.py -v`
Expected: FAIL（TypeError：derive_leg_foot_bad 参数数不符 / save_feedback 不认识的行为）。

- [ ] **Step 3: 实现**

(a) `app/services/creation_service/feedback_tags.py` 第 100-109 行替换：

```python
def derive_leg_foot_bad(
    normalized: List[Dict[str, Any]], config: Dict[str, Any]
) -> bool:
    """落库 leg_foot_bad = 任一选中负面标签 leg_foot_bad=true（纯标签推导，勾选框已移除）。"""
    known = _tag_map(config)
    for item in normalized:
        tag = known.get(item.get("key"))
        if tag is not None and tag.get("leg_foot_bad"):
            return True
    return False
```

(b) `app/services/creation_service/feedback_service.py`：模块 docstring 的设计文档行追加 `；2026-07-10-feedback-modal-ux-design.md §3（bad 纯标签推导）`。`save_feedback`（第 65-98 行）替换：

```python
    def save_feedback(
        self,
        *,
        task_id: str,
        prompt_id: str,
        image_index: int,
        feedback_text: str,
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
        # 清空即删两条件：文本空 且 无选中标签（bad 为纯推导值，无标签必为 False）
        if not text and not normalized:
            self.repo.delete_for_image(tid, pid, image_index)
            return None
        row = self.repo.upsert(
            quick_create_task_id=tid,
            prompt_id=pid,
            image_index=image_index,
            leg_foot_bad=feedback_tags.derive_leg_foot_bad(normalized, config),
            feedback_text=text,
            selected_tags_json=json.dumps(normalized, ensure_ascii=False),
        )
        return serialize_feedback_row(row)
```

(c) `app/schemas/creation.py` 第 302-305 行（`feedback_text` 行保持原样）：

```python
class ImageFeedbackSaveRequest(BaseModel):
    feedback_text: str = ""
    # deprecated（2026-07-10 起）：bad 已改为纯标签推导，本字段仅为兼容旧页面缓存保留，值被忽略
    leg_foot_bad: bool = False
    selected_tags: List[ImageFeedbackTagIn] = Field(default_factory=list)
```

（若第 303 行 `feedback_text` 默认值与上述不同，保留现状原文，只加注释行。）

(d) `app/routes/creation.py` 第 558-565 行：删掉 `leg_foot_bad=body.leg_foot_bad,` 一行，其余不动。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_feedback_tags_config.py tests/test_creation_feedback.py tests/routes/test_creation_feedback_routes.py tests/test_batch_automation_hydrated_equivalence.py tests/test_migrate_feedback_selected_tags.py -v`
Expected: 全 PASS。

- [ ] **Step 5: Commit**

```bash
git add app/services/creation_service/feedback_tags.py app/services/creation_service/feedback_service.py app/schemas/creation.py app/routes/creation.py tests/test_feedback_tags_config.py tests/test_creation_feedback.py tests/routes/test_creation_feedback_routes.py tests/test_batch_automation_hydrated_equivalence.py
git commit -m "feat(feedback): leg_foot_bad 改纯标签推导，清空即删简化为两条件"
```

---

### Task 3: 存量数据一次性迁移重算（app_migrations 守卫）

**Files:**
- Modify: `app/models/database.py`（新迁移函数插在 `migrate_creation_image_feedbacks_add_selected_tags` 之后，约第 557 行；`init_db` 调用列表末尾追加，第 597 行后）
- Test: Create `tests/test_migrate_feedback_bad_recompute.py`

**Interfaces:**
- Consumes: Task 2 的两参数 `derive_leg_foot_bad`；现有 `_is_migration_applied` / `_mark_migration_applied`（`app/models/database.py:91-106`）；`json` 已在 database.py 顶部 import（bio walk 在用）。
- Produces: `migrate_creation_image_feedbacks_recompute_leg_foot_bad()`；app_migrations 标记名 `"2026-07-10_feedback_leg_foot_bad_recompute"`。无后续任务依赖。

- [ ] **Step 1: 写失败测试**

Create `tests/test_migrate_feedback_bad_recompute.py`：

```python
"""一次性数据迁移：leg_foot_bad 重算为纯标签推导值（app_migrations 守卫）"""

import uuid

from sqlalchemy import text

from app.repositories.creation_feedback_repository import CreationImageFeedbackRepository
from app.services.creation_service import feedback_tags

FLAG = "2026-07-10_feedback_leg_foot_bad_recompute"

TEST_CFG = {
    "version": 9,
    "tags": [
        {"key": "sock_wrinkle_heavy", "label": "袜子皱褶过于夸张", "polarity": "negative",
         "leg_foot_bad": True, "taxonomy": "袜子/皱褶夸张", "group": "袜子"},
        {"key": "style_doll3d", "label": "3D玩偶感", "polarity": "negative",
         "leg_foot_bad": False, "taxonomy": "画风/3D玩偶感", "group": "画风"},
        {"key": "pos_overall_good", "label": "整体效果好", "polarity": "positive"},
    ],
}


def _seed(db_session, *, text_="", bad=False, tags_json="[]"):
    return CreationImageFeedbackRepository(db_session).upsert(
        quick_create_task_id=f"qcreate_{uuid.uuid4().hex[:12]}",
        prompt_id="p1", image_index=0,
        leg_foot_bad=bad, feedback_text=text_, selected_tags_json=tags_json,
    )


def _run_migration(monkeypatch, cfg=TEST_CFG):
    from app.models import database

    monkeypatch.setattr(feedback_tags, "get_tag_config", lambda: cfg)
    database.migrate_creation_image_feedbacks_recompute_leg_foot_bad()


def _flag_set(db_session) -> bool:
    row = db_session.connection().execute(
        text("SELECT 1 FROM app_migrations WHERE name = :n"), {"n": FLAG}
    ).fetchone()
    return row is not None


def _clear_flag(db_session):
    """自清理：不假设 db_session 是每测试独立库。"""
    from app.models.database import _ensure_app_migrations_table

    _ensure_app_migrations_table()
    conn = db_session.connection()
    conn.execute(text("DELETE FROM app_migrations WHERE name = :n"), {"n": FLAG})
    conn.execute(text("DELETE FROM creation_image_feedbacks"))
    db_session.commit()


def test_recompute_rules_and_cleanup(db_session, monkeypatch):
    _clear_flag(db_session)
    r_text = _seed(db_session, text_="纯文本时代的手动 bad", bad=True)  # → bad 归 False，行保留
    r_bad = _seed(db_session, tags_json='[{"key": "sock_wrinkle_heavy", "severity": "severe"}]')  # → True
    r_style = _seed(db_session, bad=True, tags_json='[{"key": "style_doll3d", "severity": "minor"}]')  # → False
    r_empty = _seed(db_session, bad=True)  # 文本空+无标签 → 删除
    _run_migration(monkeypatch)
    db_session.expire_all()
    rows = {r.id: r for r in CreationImageFeedbackRepository(db_session).list_all()}
    assert r_empty.id not in rows
    assert rows[r_text.id].leg_foot_bad is False
    assert rows[r_bad.id].leg_foot_bad is True
    assert rows[r_style.id].leg_foot_bad is False
    assert _flag_set(db_session)


def test_flag_makes_it_run_once(db_session, monkeypatch):
    _clear_flag(db_session)
    _run_migration(monkeypatch)  # 空库跑一遍，置标记
    assert _flag_set(db_session)
    row = _seed(db_session, bad=True)  # 标记已置，重跑不得再动数据
    _run_migration(monkeypatch)
    db_session.expire_all()
    got = CreationImageFeedbackRepository(db_session).list_all()
    assert [r.id for r in got] == [row.id]
    assert got[0].leg_foot_bad is True


def test_empty_config_skips_without_flag(db_session, monkeypatch):
    _clear_flag(db_session)
    _seed(db_session, text_="有文本", bad=True)
    _run_migration(monkeypatch, cfg={"version": 0, "tags": []})
    assert not _flag_set(db_session)  # 不置标记，下次启动重试
    db_session.expire_all()
    got = CreationImageFeedbackRepository(db_session).list_all()
    assert got[0].leg_foot_bad is True  # 数据未动


def test_corrupt_tags_json_treated_as_empty(db_session, monkeypatch):
    _clear_flag(db_session)
    kept = _seed(db_session, text_="有文本", bad=True, tags_json="{broken")  # → False，保留
    gone = _seed(db_session, bad=True, tags_json="{broken")  # 解析失败视为无标签且无文本 → 删除
    _run_migration(monkeypatch)
    db_session.expire_all()
    ids = {r.id for r in CreationImageFeedbackRepository(db_session).list_all()}
    assert kept.id in ids and gone.id not in ids
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_migrate_feedback_bad_recompute.py -v`
Expected: FAIL（AttributeError：函数不存在）。

- [ ] **Step 3: 实现迁移**

`app/models/database.py`，插在 `migrate_creation_image_feedbacks_add_selected_tags`（第 527-556 行）之后：

```python
_FEEDBACK_BAD_RECOMPUTE_FLAG = "2026-07-10_feedback_leg_foot_bad_recompute"


def migrate_creation_image_feedbacks_recompute_leg_foot_bad() -> None:
    """一次性数据迁移：勾选框移除后，把存量行 leg_foot_bad 重算为纯标签推导值。

    设计文档 docs/superpowers/specs/2026-07-10-feedback-modal-ux-design.md §3.3：
    - app_migrations 标记守卫只跑一次（防将来改配置 leg_foot_bad 时重写历史数据）；
    - 标签配置为空时跳过且不置标记（配置缺失窗口不得清零全库 bad），下次启动重试；
    - 重算后「文本空且无标签」的行删除（对齐两条件清空语义）。
    """
    from app.services.creation_service import feedback_tags

    try:
        _ensure_app_migrations_table()  # 自给自足：独立调用本迁移时元表也存在
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='creation_image_feedbacks'"
                )
            ).fetchone()
            if row is None:
                return
            if _is_migration_applied(conn, _FEEDBACK_BAD_RECOMPUTE_FLAG):
                return
            config = feedback_tags.get_tag_config()
            if not config.get("tags"):
                logger.warning(
                    "feedback bad 重算迁移：标签配置为空，跳过（不置标记，下次启动重试）"
                )
                return
            rows = conn.execute(
                text(
                    "SELECT id, feedback_text, selected_tags_json FROM creation_image_feedbacks"
                )
            ).fetchall()
            updated = deleted = 0
            for r in rows:
                try:
                    selected = json.loads(r.selected_tags_json or "[]")
                except (TypeError, ValueError):
                    selected = []
                if not isinstance(selected, list):
                    selected = []
                selected = [s for s in selected if isinstance(s, dict)]
                if not (r.feedback_text or "").strip() and not selected:
                    conn.execute(
                        text("DELETE FROM creation_image_feedbacks WHERE id = :id"),
                        {"id": r.id},
                    )
                    deleted += 1
                    continue
                bad = feedback_tags.derive_leg_foot_bad(selected, config)
                conn.execute(
                    text(
                        "UPDATE creation_image_feedbacks SET leg_foot_bad = :bad WHERE id = :id"
                    ),
                    {"bad": 1 if bad else 0, "id": r.id},
                )
                updated += 1
            _mark_migration_applied(conn, _FEEDBACK_BAD_RECOMPUTE_FLAG)
            conn.commit()
        logger.info(
            "已迁移: creation_image_feedbacks leg_foot_bad 重算 updated=%d deleted=%d",
            updated, deleted,
        )
    except Exception as e:
        logger.error(
            f"迁移 creation_image_feedbacks leg_foot_bad 重算失败: {e}", exc_info=True
        )
        raise
```

`init_db` 里 `migrate_creation_image_feedbacks_add_selected_tags()`（第 597 行）之后追加一行：

```python
        migrate_creation_image_feedbacks_recompute_leg_foot_bad()
```

（顺序必须在 add_selected_tags 之后——列先存在才能读。）

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_migrate_feedback_bad_recompute.py tests/test_migrate_feedback_selected_tags.py tests/test_creation_feedback.py -v`
Expected: 全 PASS。

- [ ] **Step 5: Commit**

```bash
git add app/models/database.py tests/test_migrate_feedback_bad_recompute.py
git commit -m "feat(feedback): 存量 leg_foot_bad 一次性重算迁移（app_migrations 守卫）"
```

---

### Task 4: 前端——分组分段式弹窗、去勾选框、52rem

**Files:**
- Modify: `page/src/services/creationApi.ts:648-653`（FeedbackTagDef 加 group）、`:668-672`（saveImageFeedback body 去 leg_foot_bad）
- Rewrite: `page/src/pages/home/components/ImageFeedbackModal.tsx`（整文件替换）
- Modify: `page/src/pages/home/components/BatchTaskCard.tsx:21-27`（onSaveFeedback 签名）、`:459`（onSave 透传）
- Modify: `page/src/pages/home/components/BatchCreationPage.tsx:196-240`（handleSaveFeedback）

**Interfaces:**
- Consumes: Task 1 的 API `group` 字段；后端保存响应仍含 `leg_foot_bad`（回显值继续写入 `userFeedback.legFootBad`，`page/src/types/quickCreate.ts` 与 `batchAutomationDisplay.ts` **不改**）。
- Produces: `FeedbackTagDef` 增 `group: string | null`；`saveImageFeedback` 的 body 类型为 `{ feedback_text: string; selected_tags?: SelectedFeedbackTag[] }`；`ImageFeedbackModal` 的 `onSave: (feedbackText: string, selectedTags: SelectedFeedbackTag[]) => Promise<void>`；`BatchTaskCard` 的 `onSaveFeedback: (taskId, image, feedbackText, selectedTags) => Promise<void>`。终端任务，无后续依赖。

- [ ] **Step 1: 改数据层类型**

`page/src/services/creationApi.ts`：

第 648-653 行 `FeedbackTagDef` 加一行：

```typescript
export interface FeedbackTagDef {
  key: string;
  label: string;
  polarity: "positive" | "negative" | "neutral";
  leg_foot_bad: boolean;
  /** 负面标签的 UI 分组名；正面/中立为 null */
  group: string | null;
}
```

第 672 行 body 类型改为：

```typescript
  body: { feedback_text: string; selected_tags?: SelectedFeedbackTag[] }
```

- [ ] **Step 2: 重写弹窗组件**

`page/src/pages/home/components/ImageFeedbackModal.tsx` 整文件替换：

```tsx
import { useState, useCallback, useEffect } from "react";
import { getFeedbackTags } from "@/services/creationApi";
import type { FeedbackTagDef, FeedbackSeverity, SelectedFeedbackTag } from "@/services/creationApi";
import type { QuickCreateImage } from "@/types/quickCreate";

interface ImageFeedbackModalProps {
  image: QuickCreateImage;
  promptTitle: string;
  onSave: (feedbackText: string, selectedTags: SelectedFeedbackTag[]) => Promise<void>;
  onClose: () => void;
}

const SEVERITY_ORDER: FeedbackSeverity[] = ["minor", "moderate", "severe"];
const SEVERITY_SHORT: Record<FeedbackSeverity, string> = {
  minor: "轻",
  moderate: "中",
  severe: "重",
};
/** 选中后整个胶囊底色随等级加深 */
const SEVERITY_BG: Record<FeedbackSeverity, string> = {
  minor: "rgba(253,164,175,0.25)",
  moderate: "rgba(244,114,182,0.45)",
  severe: "rgba(225,29,72,0.75)",
};
const OTHER_GROUP = "其他";

/** 负面标签：常显分段式「标签名│轻│中│重」，任意等级一次点选；点标签名按「中等」快捷选中/取消 */
function NegativeTagPill({
  tag,
  severity,
  onPick,
}: {
  tag: FeedbackTagDef;
  severity: FeedbackSeverity | null;
  onPick: (next: FeedbackSeverity | null) => void;
}) {
  const isOn = severity !== null;
  return (
    <div
      className="inline-flex items-center rounded-full text-xs transition-all duration-150"
      style={{
        background: isOn ? SEVERITY_BG[severity] : "rgba(0,0,0,0.04)",
        border: isOn ? "1px solid rgba(225,29,72,0.35)" : "1px solid rgba(0,0,0,0.08)",
      }}
    >
      <button
        type="button"
        onClick={() => onPick(isOn ? null : "moderate")}
        title={isOn ? "取消选中" : "按「中等」选中"}
        className="pl-2.5 pr-1 py-1 cursor-pointer whitespace-nowrap"
        style={{
          color: isOn ? (severity === "severe" ? "white" : "#be123c") : "#9ca3af",
          fontFamily: "'ZCOOL KuaiLe', cursive",
        }}
      >
        {tag.label}
      </button>
      <div className="flex items-center gap-0.5 pr-1.5">
        {SEVERITY_ORDER.map((s) => {
          const active = severity === s;
          return (
            <button
              key={s}
              type="button"
              onClick={() => onPick(active ? null : s)}
              title={active ? "取消选中" : `按「${SEVERITY_SHORT[s]}」选中`}
              className="px-1.5 py-0.5 rounded-full cursor-pointer leading-none transition-all duration-150"
              style={{
                background: active ? "rgba(255,255,255,0.9)" : "transparent",
                color: active
                  ? "#be123c"
                  : isOn
                    ? severity === "severe"
                      ? "rgba(255,255,255,0.7)"
                      : "rgba(190,18,60,0.5)"
                    : "rgba(0,0,0,0.22)",
                fontWeight: active ? 700 : 400,
              }}
            >
              {SEVERITY_SHORT[s]}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** 正面/中立标签：开关式胶囊 */
function SimpleTagPill({
  tag,
  isOn,
  onClick,
}: {
  tag: FeedbackTagDef;
  isOn: boolean;
  onClick: () => void;
}) {
  let bg = "rgba(0,0,0,0.04)";
  let color = "#9ca3af";
  let border = "1px solid rgba(0,0,0,0.08)";
  if (isOn) {
    if (tag.polarity === "positive") {
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
    </button>
  );
}

/** 单张产线出图的人工 feedback 弹窗：分组标签点选（负面等级一次点选）+ 自由文本；bad 纯标签推导 */
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
  const severityOf = (key: string): FeedbackSeverity | null => {
    const item = selected.find((s) => s.key === key);
    if (!item) return null;
    return item.severity ?? "moderate";
  };
  const isSelected = (key: string) => selected.some((s) => s.key === key);

  const pickNegative = useCallback((tag: FeedbackTagDef, next: FeedbackSeverity | null) => {
    setSelected((prev) => {
      const idx = prev.findIndex((s) => s.key === tag.key);
      if (next === null) return idx >= 0 ? prev.filter((s) => s.key !== tag.key) : prev;
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { key: tag.key, severity: next };
        return copy;
      }
      return [...prev, { key: tag.key, severity: next }];
    });
  }, []);

  const toggleSimple = useCallback((tag: FeedbackTagDef) => {
    setSelected((prev) =>
      prev.some((s) => s.key === tag.key)
        ? prev.filter((s) => s.key !== tag.key)
        : [...prev, { key: tag.key }]
    );
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(text, selected);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }, [onSave, onClose, text, selected]);

  // 负面标签按 group 分组：组间顺序 = 该组首个标签在配置中的出现顺序；「其他」固定排最后
  const negativeGroups: Array<{ name: string; items: FeedbackTagDef[] }> = [];
  for (const t of tagDefs) {
    if (t.polarity !== "negative") continue;
    const name = t.group ?? OTHER_GROUP;
    const g = negativeGroups.find((x) => x.name === name);
    if (g) g.items.push(t);
    else negativeGroups.push({ name, items: [t] });
  }
  const otherIdx = negativeGroups.findIndex((g) => g.name === OTHER_GROUP);
  if (otherIdx >= 0) negativeGroups.push(...negativeGroups.splice(otherIdx, 1));
  const positives = tagDefs.filter((t) => t.polarity === "positive");
  const neutrals = tagDefs.filter((t) => t.polarity === "neutral");

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
        onClick={saving ? undefined : onClose}
      />
      <div
        className="relative w-[52rem] max-w-[calc(100vw-2rem)] max-h-[calc(100vh-4rem)] overflow-y-auto rounded-3xl mx-4"
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
            <div className="mb-3 space-y-2.5">
              <p className="text-xs text-rose-400/70">
                问题标签（点「轻/中/重」一次选中；点标签名按「中等」快捷选中）
              </p>
              {negativeGroups.map((g) => (
                <div key={g.name} className="flex items-start gap-2">
                  <span
                    className="shrink-0 w-20 pt-1.5 text-right text-xs text-rose-300/80"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    {g.name}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {g.items.map((t) => (
                      <NegativeTagPill
                        key={t.key}
                        tag={t}
                        severity={severityOf(t.key)}
                        onPick={(next) => pickNegative(t, next)}
                      />
                    ))}
                  </div>
                </div>
              ))}
              {(positives.length > 0 || neutrals.length > 0) && (
                <div className="flex items-start gap-2 pt-2 border-t border-rose-100/60">
                  <span
                    className="shrink-0 w-20 pt-1.5 text-right text-xs text-rose-300/80"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    亮点/中立
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {[...positives, ...neutrals].map((t) => (
                      <SimpleTagPill
                        key={t.key}
                        tag={t}
                        isOn={isSelected(t.key)}
                        onClick={() => toggleSimple(t)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {derivedBad && (
            <p
              className="mb-2 text-xs text-rose-500/90"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              已判定：腿脚崩坏（由标签自动推导，计入 Case 的 bad 计数）
            </p>
          )}

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={2}
            placeholder="标签覆盖不了的新问题写这里…"
            className="w-full rounded-xl p-3 text-sm text-rose-700/80 resize-none focus:outline-none"
            style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.25)" }}
          />

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

要点核对（相对旧版）：勾选框、`manualBad`、`SEVERITY_CYCLE`、tag-config useEffect 里的 manualBad 归零逻辑全部删除；useEffect 依赖简化为 `[]`（不再读 `image.userFeedback`）。

- [ ] **Step 3: 改调用链**

(a) `page/src/pages/home/components/BatchTaskCard.tsx` 第 21-27 行签名去掉 `legFootBad`：

```typescript
  onSaveFeedback: (
    taskId: string,
    image: QuickCreateImage,
    feedbackText: string,
    selectedTags: SelectedFeedbackTag[]
  ) => Promise<void>;
```

第 459 行：

```tsx
          onSave={(text, tags) => onSaveFeedback(task.id, feedbackTarget, text, tags)}
```

(b) `page/src/pages/home/components/BatchCreationPage.tsx` 第 196-217 行，`handleSaveFeedback` 去掉 `legFootBad` 参数与请求体字段（第 218-240 行的回填逻辑不动——`legFootBad: saved.leg_foot_bad` 仍是后端推导回显）：

```typescript
  const handleSaveFeedback = useCallback(
    async (
      taskId: string,
      img: QuickCreateImage,
      feedbackText: string,
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
        { feedback_text: text, selected_tags: selectedTags }
      );
```

- [ ] **Step 4: 验证**

Run: `cd page && npm run type-check`
Expected: 0 errors。

Run: `cd page && npm run lint`
Expected: 仅 11 条预存警告（均不在本 Task 触碰的文件里），零新增。

- [ ] **Step 5: Commit**

```bash
git add page/src/services/creationApi.ts page/src/pages/home/components/ImageFeedbackModal.tsx page/src/pages/home/components/BatchTaskCard.tsx page/src/pages/home/components/BatchCreationPage.tsx
git commit -m "feat(feedback): 弹窗分组+等级一次点选+去勾选框，加宽到 52rem"
```

---

## 完成后人工环节（不属于任何 Task）

- 生产环境重启一次：`app_migrations` 迁移自动重算存量 bad（启动日志有 `updated=/deleted=` 计数）；建议重启前备份 `data/db/aetherframe.db`。
- 实际点选体验验收（分组查找、一次点选、推导提示）。
