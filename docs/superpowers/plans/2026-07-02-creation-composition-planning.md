# 创作模块构图规划优化 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 spec `docs/superpowers/specs/2026-06-30-creation-composition-planning-design.md` 定义的构图规划字段集分散嵌入现有 4 个工作流节点(创意方向 / 种子提示词 / 预生成 step1 / 预生成 review),分 S0–S5 六个可独立回滚的切片落地,同步预留可扩展/可学习机制装配点。

**Architecture:** 不新增工作流节点,不建新表(仅 `material_creative_directions` 加 `home_settings` 一列)。所有枚举值集中在 `app/services/creation_service/composition_dimensions.py`,通过 `get_dimension_values(dimension_code: str)` 接口读取并实时渲染到 Prompt 字符串中,Prompt 模板不硬编码任何枚举自然语言形态。step1 决策结果统一写入任务 cards JSON 的 `composition` 段,quick_create 出图时读取 per-card 比例,实现「auto 长宽比」尺寸闭环。

**Tech Stack:** Python 3 + FastAPI + SQLAlchemy + SQLite(WAL,`migrate_*` ALTER TABLE 模式,无 Alembic) / React 19 + TypeScript + Vite / pytest / Gemini via yibuapi.com

## Global Constraints

- 第一硬约束:自然展示角色腿部与脚部(袜子)——任何字段/枚举/组合上线前必须过一遍「会不会遮挡/裁掉腿脚」过滤;严禁 fetish 倾向的镜头语言(脚部特写/袜子特写/袜口装饰特写/纯下半身镜头等)进入枚举。
- LLM 能力上限:不设计复杂腿脚动作枚举,腿脚摆放用自然语言 1–2 句;用「机位组合多样性」代替「姿势细节多样性」。
- 每个切片是「1 个逻辑变更单元 = 若干文件」,不再按纯文件计数硬性限制。当前豁免:S0-2(3 文件:方向 Prompt + 服务层 + schema)、S1-2(5 文件:模板 + step1 Prompt + review Prompt + 装配层 + schema + quick_create,尺寸闭环)、S1-3(4 文件:3 个前端页面 + 前端类型)、S3-1(3 文件:step1 Prompt + template + 装配层)、S4-1(3 文件:同 S3-1)。切片顺序:S0 → S1 → S2 → S3 → S4 → S5;S2 必须在 S3/S4 之前(上游先稳定)。
- 枚举值不得在 Prompt 模板里硬编码。任何节点装配层需要枚举集时,必须调用 `get_dimension_values(dimension_code)` 读取并现场渲染进 Prompt 字符串。软指引表(`home_setting → pose_family`)同理。
- 本轮唯一允许的 schema 变动:S0 给 `material_creative_directions` 加 `home_settings TEXT` 列,沿用现有 `migrate_*` ALTER TABLE 模式。其他任何表 schema 不动。
- 不实现可学习机制的写入路径 / 权重 UI / 参考图上传;所有相关段落本轮只做「空字符串预留」。
- 提交纪律:每个 Step 5 都是独立 `git commit`,消息前缀区分切片(`feat(S0): ...` / `feat(S1): ...` 等)。分支从 `dev` 拉出,合并回 `dev`。

## 文件结构总览

**新建**
- `app/services/creation_service/composition_dimensions.py` — 构图维度枚举集中管理模块,承载 `get_dimension_values()` 接口与 `home_setting → pose_family` 软指引表读取。
- `tests/services/test_composition_dimensions.py` — 维度接口单测。
- `tests/services/test_creative_direction_home_settings.py` — home_settings 抽取与持久化单测。
- `tests/services/test_prompt_precreation_composition_persistence.py` — step1 决策字段持久化到 cards 的单测。

**修改(按切片顺序)**
- `app/models/material.py` — `MaterialCreativeDirection` 加 `home_settings` 列 (S0)。
- `app/models/database.py` — 增加 `migrate_material_creative_directions_add_home_settings()` 并挂入启动链 (S0)。
- `app/prompts/material/creative_direction.py` — `creative_direction_prompt` 加 home_settings 输出要求;`creation_direction_seed_prompt` 加姿态家族均衡 / pose_detail / 反 fetish / 背景联动 / 分布偏好预留段 (S0 + S2)。
- `app/services/material_service/creative_direction_generation_service.py` — 解析并持久化 home_settings (S0)。
- `app/schemas/material.py` — `CreativeDirectionResponse` 加 `home_settings` 字段 (S0)。
- `app/services/material_service/seed_prompt_generation_service.py` — 把 home_settings 折叠进 `chara_creative_direction` 注入文本 (S0);拼装分布偏好预留段 (S2)。
- `app/prompts/creation/prompt_precreation.py` — `prompt_step1` 加任务步骤 0 / 镜头组合分布偏好预留段 / Negative Prompt 风险标签合并指令 (S1/S3/S4);`prompt_review` 加维度差异分 + 权重表预留段 (S5)。
- `app/prompts/creation/prompt_template.py` — `init_template` 与 `good_template1` 把 `16:9` 改为可回填占位符,「构图硬约束」段增加主体占比条,「镜头与构图」段顶部增加 3 行回填位 (S1/S3/S4)。
- `app/services/creation_service/prompt_precreation_service.py` — 装配层:调 `get_dimension_values()` 现场渲染枚举集到 Prompt;从 step1 输出解析结构化决策,写入每张 card 的 `composition` 段 (S1/S3/S4)。
- `app/schemas/creation.py` — `aspect_ratio` Literal 加入 `auto` (S1);`PromptCardItem` 加可选 `composition` 结构 (S1/S3/S4)。
- `app/services/creation_service/quick_create_service.py` — `VALID_ASPECT_RATIOS` 加 `auto`;出图循环在入参为 `auto` 时改用 per-card 决策比例 (S1)。
- `page/src/pages/creation/components/QuickCreatePage.tsx` / `PromptGenPage.tsx` / `page/src/pages/home/components/BatchCreationPage.tsx` — 长宽比选项加 `auto` (S1)。
- `page/src/services/creationApi.ts` — 类型 Literal 加 `auto` (S1)。

---

## S0 — 创意方向加 `home_settings` 字段

### Task S0-1: DB 迁移 + 模型加列

**Files:**
- Modify: `app/models/material.py:165-195` — `MaterialCreativeDirection` 增字段
- Modify: `app/models/database.py` — 新增 `migrate_material_creative_directions_add_home_settings()` 并挂入 `_run_all_migrations()` (行号见步骤)
- Test: `tests/services/test_creative_direction_home_settings.py::test_home_settings_column_exists_and_defaults_to_null`

**Interfaces:**
- Consumes: 现有 `_ensure_app_migrations_table` / `_is_migration_applied` / `_mark_migration_applied` (`app/models/database.py:79-108`)
- Produces: `MaterialCreativeDirection.home_settings: Optional[str]`(JSON 字符串或 NULL);迁移标记名 `mig_material_creative_directions_add_home_settings`

- [ ] **Step 1: Write the failing test**

新建 `tests/services/test_creative_direction_home_settings.py`:

```python
from sqlalchemy import text
from app.models.database import engine
from app.models.material import MaterialCreativeDirection


def test_home_settings_column_exists_and_defaults_to_null(db_session):
    """home_settings 列必须存在,且新建方向默认为 NULL。"""
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info(material_creative_directions)")).fetchall()
    names = {c[1] for c in cols}
    assert "home_settings" in names, f"missing home_settings column, got: {sorted(names)}"

    row = MaterialCreativeDirection(
        id="cd_test_home_settings_null",
        character_id="chr_dummy_hs",
        title="t",
        description="d",
        divergence="mid",
    )
    db_session.add(row)
    db_session.commit()
    reloaded = db_session.get(MaterialCreativeDirection, "cd_test_home_settings_null")
    assert reloaded.home_settings is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_creative_direction_home_settings.py::test_home_settings_column_exists_and_defaults_to_null -v`
Expected: FAIL with `missing home_settings column` 或 `MaterialCreativeDirection has no attribute 'home_settings'`

- [ ] **Step 3: Write minimal implementation**

`app/models/material.py`,在 `MaterialCreativeDirection` 的 `updated_at` 之后、`character = relationship(...)` 之前插入:

```python
    home_settings = Column(Text, nullable=True)
```

`app/models/database.py`,在 `migrate_bio_official_seed_prompts_add_direction_fk` 定义之后、`_run_all_migrations` 定义之前追加:

```python
def migrate_material_creative_directions_add_home_settings() -> None:
    """轻量迁移:为 material_creative_directions 补 home_settings TEXT 列(JSON 数组或 NULL)。"""
    if not os.path.exists(DB_PATH):
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='material_creative_directions'"
                )
            ).fetchone()
            if row is None:
                return
            cols = conn.execute(
                text("PRAGMA table_info(material_creative_directions)")
            ).fetchall()
            names = {c[1] for c in cols}
            if "home_settings" in names:
                return
            conn.execute(
                text(
                    "ALTER TABLE material_creative_directions "
                    "ADD COLUMN home_settings TEXT"
                )
            )
        logger.info("已迁移: material_creative_directions 增加 home_settings 列")
    except Exception as e:
        logger.error(
            f"迁移 material_creative_directions.home_settings 失败: {e}",
            exc_info=True,
        )
        raise
```

在 `_run_all_migrations()`(围绕 `app/models/database.py:515-527`)的迁移调用列表末尾追加一行:

```python
        migrate_material_creative_directions_add_home_settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_creative_direction_home_settings.py::test_home_settings_column_exists_and_defaults_to_null -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/material.py app/models/database.py tests/services/test_creative_direction_home_settings.py
git commit -m "feat(S0): 为 material_creative_directions 增加 home_settings 列"
```

### Task S0-2: Prompt 加 home_settings 输出要求 + 服务层解析持久化

**Files:**
- Modify: `app/prompts/material/creative_direction.py:1-69` — `creative_direction_prompt` 加 home_settings 输出要求
- Modify: `app/services/material_service/creative_direction_generation_service.py:36-49,130-148` — 解析并写入 `home_settings`
- Modify: `app/schemas/material.py:316-327` — `CreativeDirectionResponse` 加字段
- Test: `tests/services/test_creative_direction_home_settings.py::test_parse_direction_json_extracts_home_settings`
- Test: `tests/services/test_creative_direction_home_settings.py::test_parse_direction_json_missing_home_settings_is_none`

**Interfaces:**
- Consumes: `MaterialCreativeDirection.home_settings` (Task S0-1)、`_parse_direction_json` 现有签名
- Produces: 修改 `_parse_direction_json(raw: str) -> tuple[str, str, Optional[list[str]]]`(第三返回值为 home_settings 数组或 None);`CreativeDirectionResponse.home_settings: Optional[List[str]]`

- [ ] **Step 1: Write the failing tests**

在 `tests/services/test_creative_direction_home_settings.py` 追加:

```python
import json
from app.services.material_service.creative_direction_generation_service import (
    _parse_direction_json,
)


def test_parse_direction_json_extracts_home_settings():
    raw = json.dumps({
        "title": "T",
        "description": "D",
        "home_settings": ["卧室大床", "客厅沙发", "飘窗台"],
    })
    title, desc, home = _parse_direction_json(raw)
    assert title == "T"
    assert desc == "D"
    assert home == ["卧室大床", "客厅沙发", "飘窗台"]


def test_parse_direction_json_missing_home_settings_is_none():
    raw = json.dumps({"title": "T", "description": "D"})
    _, _, home = _parse_direction_json(raw)
    assert home is None


def test_parse_direction_json_trims_and_dedups_home_settings():
    raw = json.dumps({
        "title": "T",
        "description": "D",
        "home_settings": [" 卧室大床 ", "卧室大床", "客厅沙发", "", None, 123],
    })
    _, _, home = _parse_direction_json(raw)
    assert home == ["卧室大床", "客厅沙发"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_creative_direction_home_settings.py -v -k parse_direction_json`
Expected: FAIL — `_parse_direction_json` 现在只返回 2 元组

- [ ] **Step 3: Write minimal implementation**

`app/prompts/material/creative_direction.py`,在 `creative_direction_prompt` 的「推荐场景」相关描述后补一条创作要求(与现有「创作要求」块并列的新块前一段位置,`# 输出的JSON格式示例` 之前):

```
**居家背景框架输出(新增)**:
- 请在 JSON 输出中额外增加 `home_settings` 字段,取值为 1–3 个具体的居家背景框架短语数组
- 每个短语应描述一处可容纳角色天然展示腿部与脚部的居家空间锚点(例如「卧室大床」「客厅沙发」「日式榻榻米」「飘窗台」「书房地毯」)
- 短语应与你在 `description` 中「推荐场景」小节所描述的空间相一致,是对该场景的具体化落点
```

同一文件中,修改「输出的JSON格式示例」为:

```
{{
    \"title\": \"标题内容\",
    \"description\": \"内容描述\",
    \"home_settings\": [\"短语1\", \"短语2\"]
}}
```

`app/services/material_service/creative_direction_generation_service.py`,把 `_parse_direction_json` 改为返回 3 元组并做规范化:

```python
def _parse_direction_json(raw: str) -> tuple[str, str, Optional[list[str]]]:
    cleaned = _strip_json_fence(raw)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        snippet = (cleaned[:800] + "..." if len(cleaned) > 800 else cleaned)
        raise ValueError(f"LLM JSON parse failed: {e}; snippet={snippet!r}") from e
    title = obj.get("title")
    desc = obj.get("description")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("LLM output missing 'title'")
    if not isinstance(desc, str) or not desc.strip():
        raise ValueError("LLM output missing 'description'")
    raw_home = obj.get("home_settings")
    home: Optional[list[str]] = None
    if isinstance(raw_home, list):
        seen: set[str] = set()
        cleaned_home: list[str] = []
        for x in raw_home:
            if not isinstance(x, str):
                continue
            s = x.strip()
            if not s or s in seen:
                continue
            seen.add(s)
            cleaned_home.append(s)
            if len(cleaned_home) >= 3:
                break
        home = cleaned_home or None
    return title.strip(), desc, home
```

同一文件的 `run_creative_direction_task` 中,把 `title, description = _parse_direction_json(llm_raw)` 改为:

```python
            title, description, home_settings = _parse_direction_json(llm_raw)
```

并在构造 `MaterialCreativeDirection(...)` 时增加:

```python
                    home_settings=json.dumps(home_settings, ensure_ascii=False) if home_settings else None,
```

在 `_write_direction_json_file` 的写出字典里增加 `"home_settings": ...`,值取 `json.loads(direction.home_settings) if direction.home_settings else None`。

`app/schemas/material.py:316-327`,在 `CreativeDirectionResponse` 类里追加字段:

```python
    home_settings: Optional[List[str]] = None
```

并在类顶部 imports 已含 `List`/`Optional` 时无需再动;如缺少 `List`,补 `from typing import List`。字段序列化时需要把 DB 里存的 JSON 字符串转回列表 — 在 `MaterialService.list_creative_directions` / `get_creative_direction_task_status` / `patch_creative_direction` 等 `model_validate(row)` 前不方便介入,采用 `@field_validator` 在 schema 侧做转换,即在 `CreativeDirectionResponse` 类里追加:

```python
    @field_validator("home_settings", mode="before")
    @classmethod
    def _coerce_home_settings(cls, v):
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            try:
                parsed = json.loads(s)
                return parsed if isinstance(parsed, list) else None
            except json.JSONDecodeError:
                return None
        return None
```

顶部 imports 需要 `import json` 与 `from pydantic import BaseModel, ConfigDict, Field, field_validator`(补 `field_validator` 若缺)。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_creative_direction_home_settings.py -v`
Expected: PASS(全部 4 条:列存在 + 3 条 parse)

- [ ] **Step 5: Commit**

```bash
git add app/prompts/material/creative_direction.py app/services/material_service/creative_direction_generation_service.py app/schemas/material.py tests/services/test_creative_direction_home_settings.py
git commit -m "feat(S0): 创意方向 Prompt 增 home_settings 输出并持久化"
```

---

## S1 — Auto 长宽比 + 主体占比下限(尺寸闭环)

Auto 模式的实际画布尺寸真正闭环:step1 决策 → 写入每张 card 的 `composition.aspect_ratio` → quick_create 出图循环按 per-card 值传给图片 API。这是 S1 突破「每切片改 1–2 个文件」约束的唯一位置(S0/S2/S3/S4/S5 仍然坚守)。

### Task S1-1: 新建构图维度枚举模块

**Files:**
- Create: `app/services/creation_service/composition_dimensions.py`
- Test: `tests/services/test_composition_dimensions.py`

**Interfaces:**
- Consumes: 无(纯常量模块)
- Produces:
  - `DimensionValue`(dataclass 或 NamedTuple):字段 `code: str, display_name: str, description: str`
  - `get_dimension_values(dimension_code: str) -> List[DimensionValue]` — 支持维度 code:`aspect_ratio_manual` / `aspect_ratio_auto_full` / `aspect_ratio_auto_mainstream` / `subject_area_min` / `pose_family` / `shooting_angle` / `camera_height` / `gaze_direction`
  - `get_home_setting_pose_hints() -> List[Tuple[str, List[str]]]` — 软指引参考表,返回 `[("卧室大床", ["躺姿","倚靠","盘腿坐"]), ...]`
  - 常量 `VALID_MANUAL_ASPECT_CODES: frozenset[str]`(即 `{"16:9","4:3","1:1","3:4","9:16"}`)
  - 常量 `VALID_AUTO_ASPECT_CODES: frozenset[str]`(9 档全集)

- [ ] **Step 1: Write the failing test**

新建 `tests/services/test_composition_dimensions.py`:

```python
import pytest

from app.services.creation_service.composition_dimensions import (
    DimensionValue,
    VALID_AUTO_ASPECT_CODES,
    VALID_MANUAL_ASPECT_CODES,
    get_dimension_values,
    get_home_setting_pose_hints,
)


def test_manual_aspect_ratio_returns_five_values():
    values = get_dimension_values("aspect_ratio_manual")
    assert len(values) == 5
    codes = {v.code for v in values}
    assert codes == {"16:9", "4:3", "1:1", "3:4", "9:16"}
    assert VALID_MANUAL_ASPECT_CODES == frozenset(codes)


def test_auto_aspect_ratio_full_has_nine_values_and_includes_manual_five():
    values = get_dimension_values("aspect_ratio_auto_full")
    codes = {v.code for v in values}
    assert len(codes) == 9
    assert VALID_MANUAL_ASPECT_CODES.issubset(codes)
    assert VALID_AUTO_ASPECT_CODES == frozenset(codes)
    for extra in ("4:5", "5:4", "2:3", "3:2"):
        assert extra in codes


def test_auto_aspect_ratio_mainstream_is_the_five_manual():
    values = get_dimension_values("aspect_ratio_auto_mainstream")
    assert {v.code for v in values} == VALID_MANUAL_ASPECT_CODES


def test_subject_area_min_four_tiers():
    values = get_dimension_values("subject_area_min")
    codes = [v.code for v in values]
    assert codes == ["0.45", "0.55", "0.65", "0.75"]


def test_pose_family_six_tiers():
    values = get_dimension_values("pose_family")
    display = {v.display_name for v in values}
    assert display == {"坐姿", "躺姿", "跪姿", "蹲姿", "倚靠", "盘腿坐"}


def test_shooting_angle_five_tiers_includes_back_glance():
    values = get_dimension_values("shooting_angle")
    codes = {v.code for v in values}
    assert "back_glance" in codes
    assert len(codes) == 5


def test_camera_height_four_tiers():
    values = get_dimension_values("camera_height")
    codes = {v.code for v in values}
    assert codes == {"slight_up", "eye_level", "slight_down", "high_down"}


def test_gaze_direction_five_tiers():
    values = get_dimension_values("gaze_direction")
    assert len({v.code for v in values}) == 5


def test_unknown_dimension_raises():
    with pytest.raises(KeyError):
        get_dimension_values("no_such_dimension")


def test_dimension_value_has_all_three_fields():
    v = get_dimension_values("pose_family")[0]
    assert isinstance(v, DimensionValue)
    assert v.code and v.display_name and v.description


def test_home_setting_pose_hints_returns_tuples_with_nonempty_lists():
    hints = get_home_setting_pose_hints()
    assert len(hints) >= 5
    for setting, poses in hints:
        assert isinstance(setting, str) and setting
        assert isinstance(poses, list) and all(isinstance(p, str) and p for p in poses)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_composition_dimensions.py -v`
Expected: FAIL — 模块不存在 (`ModuleNotFoundError`)

- [ ] **Step 3: Write minimal implementation**

新建 `app/services/creation_service/composition_dimensions.py`:

```python
"""构图维度枚举集中管理。所有 Prompt 装配层通过 get_dimension_values() 读取。

新增/删除/改名枚举值只需在此文件调整,不需要修改 Prompt 模板与节点拓扑。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Tuple


@dataclass(frozen=True)
class DimensionValue:
    code: str
    display_name: str
    description: str


_MANUAL_ASPECT: List[DimensionValue] = [
    DimensionValue("16:9", "16:9", "横向宽屏,适合横向卧姿/横构图"),
    DimensionValue("4:3",  "4:3",  "横向常规,适合半环境居中构图"),
    DimensionValue("1:1",  "1:1",  "正方形,适合居中坐姿/居中构图"),
    DimensionValue("3:4",  "3:4",  "竖向常规,适合竖向全身"),
    DimensionValue("9:16", "9:16", "竖向宽屏,适合竖向全身/纵深构图"),
]

_EXTRA_AUTO_ASPECT: List[DimensionValue] = [
    DimensionValue("4:5", "4:5", "接近竖向正方形,适合半环境竖构图"),
    DimensionValue("5:4", "5:4", "接近正方形略横,适合居中坐姿"),
    DimensionValue("2:3", "2:3", "竖向偏窄,适合竖向全身"),
    DimensionValue("3:2", "3:2", "横向偏窄,适合横向全身"),
]

VALID_MANUAL_ASPECT_CODES: FrozenSet[str] = frozenset(v.code for v in _MANUAL_ASPECT)
VALID_AUTO_ASPECT_CODES: FrozenSet[str] = frozenset(
    v.code for v in (_MANUAL_ASPECT + _EXTRA_AUTO_ASPECT)
)

_SUBJECT_AREA_MIN: List[DimensionValue] = [
    DimensionValue("0.45", "45%", "较低占比,适合大空间/纵深强调环境"),
    DimensionValue("0.55", "55%", "中等偏低,常用平衡档"),
    DimensionValue("0.65", "65%", "中等偏高,缩略图友好的默认建议档"),
    DimensionValue("0.75", "75%", "高占比,主体强调/角色特写但仍全身可见"),
]

_POSE_FAMILY: List[DimensionValue] = [
    DimensionValue("sitting",    "坐姿",   "坐在椅/沙发/床沿/窗台等平面上"),
    DimensionValue("lying",      "躺姿",   "侧卧/仰卧/俯卧于床/地板/沙发"),
    DimensionValue("kneeling",   "跪姿",   "跪坐/跽坐,双膝着地"),
    DimensionValue("squatting",  "蹲姿",   "蹲下或半蹲,腿脚仍完整可见"),
    DimensionValue("leaning",    "倚靠",   "倚靠墙/沙发靠背/窗框,身体重心倾斜"),
    DimensionValue("cross_leg",  "盘腿坐", "盘腿坐或双腿交叠坐,腿脚自然收拢"),
]

_SHOOTING_ANGLE: List[DimensionValue] = [
    DimensionValue("front",           "正面",       "镜头正对角色正面"),
    DimensionValue("three_quarter",   "3/4 正面",   "镜头 3/4 侧前方"),
    DimensionValue("side",            "侧面",       "镜头完全侧面"),
    DimensionValue("three_quarter_back", "3/4 背面", "镜头 3/4 后方"),
    DimensionValue("back_glance",     "背面(回眸)", "镜头在角色后方,角色上半身回头朝向镜头、视线接触观者"),
]

_CAMERA_HEIGHT: List[DimensionValue] = [
    DimensionValue("slight_up",   "略仰", "机位略低于视平,轻微仰拍"),
    DimensionValue("eye_level",   "平视", "机位与视平齐"),
    DimensionValue("slight_down", "略俯", "机位略高于视平,轻微俯拍"),
    DimensionValue("high_down",   "大俯", "机位明显高于视平,明显俯拍"),
]

_GAZE_DIRECTION: List[DimensionValue] = [
    DimensionValue("to_camera",       "看镜头",     "视线直接接触观者"),
    DimensionValue("three_quarter_out","3/4 看出画", "视线朝画面外 3/4 方向"),
    DimensionValue("to_side",         "侧面看",     "视线朝纯侧面"),
    DimensionValue("to_down",         "看下方",     "视线略微下垂"),
    DimensionValue("to_far",          "看远处",     "视线望向远方,焦点在画外"),
]

_REGISTRY: Dict[str, List[DimensionValue]] = {
    "aspect_ratio_manual":            _MANUAL_ASPECT,
    "aspect_ratio_auto_full":         _MANUAL_ASPECT + _EXTRA_AUTO_ASPECT,
    "aspect_ratio_auto_mainstream":   _MANUAL_ASPECT,
    "subject_area_min":               _SUBJECT_AREA_MIN,
    "pose_family":                    _POSE_FAMILY,
    "shooting_angle":                 _SHOOTING_ANGLE,
    "camera_height":                  _CAMERA_HEIGHT,
    "gaze_direction":                 _GAZE_DIRECTION,
}


def get_dimension_values(dimension_code: str) -> List[DimensionValue]:
    if dimension_code not in _REGISTRY:
        raise KeyError(f"unknown dimension_code: {dimension_code!r}")
    return list(_REGISTRY[dimension_code])


_HOME_SETTING_POSE_HINTS: List[Tuple[str, List[str]]] = [
    ("卧室大床",    ["躺姿", "倚靠", "盘腿坐"]),
    ("客厅沙发",    ["倚靠", "坐姿", "躺姿"]),
    ("日式榻榻米",  ["跪姿", "盘腿坐", "坐姿"]),
    ("飘窗台",      ["坐姿", "倚靠"]),
    ("书房地毯",    ["盘腿坐", "蹲姿", "跪姿"]),
]


def get_home_setting_pose_hints() -> List[Tuple[str, List[str]]]:
    return [(s, list(poses)) for s, poses in _HOME_SETTING_POSE_HINTS]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_composition_dimensions.py -v`
Expected: PASS(10 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/creation_service/composition_dimensions.py tests/services/test_composition_dimensions.py
git commit -m "feat(S1): 新建构图维度枚举集中管理模块"
```

### Task S1-2: 模板占位符化 + step1 总是决策 aspect_ratio 与主体占比

**设计说明**:pre-creation 入口(PromptGenPage)当前不选 auto/manual — auto/manual 是 quick_create 出图时的选择。因此 step1 采取「auto capable」策略:**始终**决策 aspect_ratio 与 subject_area_min 写入 card 的 `composition` 段;出图时用户选 `auto` → 用 per-card 值,用户选 `16:9` → 用户值覆盖 per-card。这样 step1 无 mode 分支参数,代码路径唯一,已决策的字段也天然作为学习机制的历史数据(spec §8.6)。

**Files:**
- Modify: `app/prompts/creation/prompt_template.py` — 移除 `16:9` 硬编码,`{aspect_ratio}` 占位符;「构图硬约束」段加主体占比条
- Modify: `app/prompts/creation/prompt_precreation.py` — `prompt_step1` / `prompt_step2` / `prompt_review` / `prompt_review_backup` 顶部四处「16:9」文案统一改为「(由 step1 决策的长宽比)」;任务步骤顶端插入任务步骤 0(所有 pre-creation 都走)
- Modify: `app/services/creation_service/prompt_precreation_service.py` — 装配层渲染枚举集,解析结构化决策写入 card
- Modify: `app/schemas/creation.py:36-37,120-123,231-233` — `aspect_ratio` Literal 加 `auto`;`PromptCardItem` 加可选 `composition`
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_build_step1_prompt_renders_aspect_ratio_and_subject_area_enums`
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_parse_step1_composition_from_output`
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_parse_step1_composition_missing_returns_empty`
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_parse_step1_composition_rejects_out_of_enum`

**Interfaces:**
- Consumes: `get_dimension_values` / `VALID_AUTO_ASPECT_CODES` (Task S1-1)
- Produces:
  - `PromptCardItem.composition: Optional[Dict[str, str]]` — 本切片写入 `{"aspect_ratio","subject_area_min"}`,后续 S3/S4 会追加 `shooting_angle`/`camera_height`/`gaze_direction`
  - 内部纯函数: `_render_dimension_list(dim: str) -> str`、`_build_step1_prompt(*, chara_profile: str, seed_prompt: str) -> str`、`_parse_step1_composition(step1_output: str) -> Dict[str, str]`

- [ ] **Step 1: Write the failing tests**

新建 `tests/services/test_prompt_precreation_composition_persistence.py`:

```python
import pytest


def test_build_step1_prompt_renders_aspect_ratio_and_subject_area_enums():
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    for code in ("16:9", "4:3", "1:1", "3:4", "9:16", "2:3", "3:2", "4:5", "5:4"):
        assert code in p, f"missing aspect_ratio {code}"
    for code in ("0.45", "0.55", "0.65", "0.75"):
        assert code in p, f"missing subject_area_min {code}"
    assert "任务步骤 0" in p or "任务步骤0" in p
    assert "aspect_ratio" in p and "subject_area_min" in p


def test_parse_step1_composition_from_output():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**【固定】任务目标**:...
**[COMPOSITION_DECISION]**
aspect_ratio: 1:1
subject_area_min: 0.65
**背景场景**:...
"""
    result = _parse_step1_composition(text)
    assert result == {"aspect_ratio": "1:1", "subject_area_min": "0.65"}


def test_parse_step1_composition_missing_returns_empty():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    result = _parse_step1_composition("no decision block here")
    assert result == {}


def test_parse_step1_composition_rejects_out_of_enum():
    """LLM 幻觉出枚举外的值,静默剔除该字段而不是 crash。"""
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
aspect_ratio: 7:11
subject_area_min: 0.65
"""
    result = _parse_step1_composition(text)
    assert "aspect_ratio" not in result
    assert result.get("subject_area_min") == "0.65"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_prompt_precreation_composition_persistence.py -v`
Expected: FAIL — 函数不存在 (`ImportError`/`AttributeError`)

- [ ] **Step 3: Write minimal implementation**

**3.1** `app/prompts/creation/prompt_template.py`,把 `init_template` 与 `good_template1` 里所有出现的 ` **16:9** ` 改为 ` **{aspect_ratio}** `;把「构图硬约束」括号说明扩充为:

```
**构图硬约束**:{composition_hard_constraint_lead}(对于构图固定约束的补充说明与强调)
```

其中 `composition_hard_constraint_lead` 用于回填「角色主体在画面中占比不低于 X%」等。装配层填入,模板不写死。

**3.2** `app/prompts/creation/prompt_precreation.py`,把 `prompt_step1` 顶部「16:9尺寸的」改为「**由你根据场景自主决策长宽比**的」;`prompt_step2` 顶部同句「16:9尺寸的」改为「(由 step1 决策的长宽比,已经在 init_template 的任务目标段中回填)」;`prompt_review` 顶部「16:9尺寸的」改为「(由 step1 决策的长宽比)」;`prompt_review_backup` 顶部同句同步改为「(由 step1 决策的长宽比)」。

在「任务步骤」列表**顶端**(现有「1、根据用户的需求...」之前)插入:

```
{step1_task_step_zero}
```

在「模版填写说明」列表**末尾**(现有「6、不要修改...」之后)追加:

```
{step1_composition_output_requirement}
```

(`prompt_step2` / `prompt_review` / `prompt_review_backup` 顶部四处「16:9」已在上面统一处理。)

**3.3** `app/services/creation_service/prompt_precreation_service.py`,追加以下常量与纯函数(放在 `PREVIEW_MAX_LEN` 之后、`compose_seed_prompt_with_direction` 之前):

```python
import re as _re
from typing import Dict, Optional

from app.services.creation_service.composition_dimensions import (
    VALID_AUTO_ASPECT_CODES,
    get_dimension_values,
)

_COMPOSITION_BLOCK_RE = _re.compile(
    r"\*\*\[COMPOSITION_DECISION\]\*\*\s*(.*?)(?=\n\s*\*\*|\Z)",
    _re.DOTALL,
)
_COMPOSITION_LINE_RE = _re.compile(r"^\s*([a-z_]+)\s*:\s*(\S+)\s*$", _re.MULTILINE)

_ENUM_CODES: Dict[str, set] = {
    "aspect_ratio": set(VALID_AUTO_ASPECT_CODES),
    "subject_area_min": {v.code for v in get_dimension_values("subject_area_min")},
}


def _render_dimension_list(dim: str) -> str:
    return "\n".join(
        f"  - `{v.code}` ({v.display_name}): {v.description}"
        for v in get_dimension_values(dim)
    )


def _build_step1_prompt(*, chara_profile: str, seed_prompt: str) -> str:
    step_zero = (
        "0、**先做构图决策(必须在脑补画面之前完成)**:\n"
        "   - 从下面 9 个长宽比档位中选择最契合本次场景的一个:\n"
        f"{_render_dimension_list('aspect_ratio_auto_full')}\n"
        "   - 优先在主流 5 档 (`9:16`, `3:4`, `1:1`, `4:3`, `16:9`) 中选择;"
        "除非场景明显适配特殊比例(如 `5:4` 适合接近正方形的居中坐姿、`2:3` 适合竖向全身)才使用扩展 4 档。\n"
        "   - 从下面 4 档中选择角色主体在画面中的占比下限:\n"
        f"{_render_dimension_list('subject_area_min')}"
    )
    composition_output = (
        "7、请在输出的模板正文**之前**,插入一段用 `**[COMPOSITION_DECISION]**` 标记的构图决策说明,格式如下(仅两行,取上一步选定的 code 值):\n"
        "```\n"
        "**[COMPOSITION_DECISION]**\n"
        "aspect_ratio: <code>\n"
        "subject_area_min: <code>\n"
        "```\n"
        "后续「任务目标」与「构图硬约束」段中,请用你选定的长宽比替换 `{aspect_ratio}` 占位符、"
        "用主体占比下限的百分比值(如 65%)替换 `{subject_area_min_pct}` 占位符。"
    )
    return prompt_step1.format(
        chara_profile=chara_profile,
        seed_prompt=seed_prompt,
        init_template=init_template,   # 保留 {aspect_ratio} / {subject_area_min_pct} 占位符,由 LLM 回填
        good_template=good_template1,
        step1_task_step_zero=step_zero,
        step1_composition_output_requirement=composition_output,
    )


def _parse_step1_composition(step1_output: str) -> Dict[str, str]:
    m = _COMPOSITION_BLOCK_RE.search(step1_output)
    if not m:
        return {}
    body = m.group(1)
    result: Dict[str, str] = {}
    for key, value in _COMPOSITION_LINE_RE.findall(body):
        if key not in _ENUM_CODES:
            continue
        if value not in _ENUM_CODES[key]:
            logger.warning(
                "step1 composition %s=%s out of enum, dropped", key, value
            )
            continue
        result[key] = value
    return result
```

同一文件,把 `_collect_candidates` 中 `p1 = prompt_step1.format(...)` 一行改为 `p1 = _build_step1_prompt(chara_profile=chara_profile, seed_prompt=seed_prompt)`,并在得到 `step1_result` 之后调用 `_parse_step1_composition(step1_result)`,把结果存入本函数返回值之外的第二个字典 `compositions: Dict[str, Dict[str, str]]`(key 与 candidates 同为 `candidate_prompt_NNN`)。

改造 `_collect_candidates` 签名与返回:

```python
def _collect_candidates(
    *,
    chara_profile: str,
    seed_prompt: str,
    work_dir: str,
    n: int,
) -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
    ...
    return candidates, compositions
```

`_build_cards` 签名加参数:

```python
def _build_cards(
    best_files: List[str],
    candidates: Dict[str, str],
    compositions: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    ...
    for i, name in enumerate(best_files):
        ...
        cards.append({
            ...,
            "composition": compositions.get(name) or None,
        })
```

`run_prompt_precreation_task_sync` 中同步解包与传参。

**3.4** `app/prompts/creation/prompt_template.py`,`init_template`:
- 顶部「任务目标」段的 ` **16:9** ` 改为 ` **{aspect_ratio}** `。
- 「构图硬约束」段的括号说明后追加一行:
  ```
  角色主体在画面中占比不低于 {subject_area_min_pct}%;
  ```
- 装配层不预填这两个占位符;它们随模板文本一起进入 step1 LLM 上下文,由 LLM 依据决策结果自己在输出中把占位符替换为实际值(与 `**[COMPOSITION_DECISION]**` 决策块一致)。

`good_template1` 保留 16:9 与具体百分比作为示例(不动),模板 `str.format` 不会解析 `good_template` 字符串内的 `{...}`,因为它是 `_build_step1_prompt` 的独立 slot。若担心 format 报 KeyError,把 `good_template1` 内可能出现的孤立 `{...}` 全部转义为 `{{...}}`(仅在 `good_template1` 里),或改用 `str.replace` 避免占位符冲突。

**3.5** `app/schemas/creation.py`:

- 第 37 行、第 121 行、第 232 行的 `aspect_ratio: Literal["16:9","4:3","1:1","3:4","9:16"]` 全部改为 `Literal["auto","16:9","4:3","1:1","3:4","9:16"]`。
- `PromptCardItem` 追加字段:
  ```python
      composition: Optional[Dict[str, str]] = None
  ```
  顶部 imports 已含 `Dict`;若缺则补 `from typing import Dict`。

**3.6** `app/services/creation_service/quick_create_service.py`:

- `VALID_ASPECT_RATIOS` 改为 `{"auto","16:9","4:3","1:1","3:4","9:16"}`。
- 出图循环 (`generate_image_with_nano_banana_pro` 调用处,`quick_create_service.py:347`) 改为按 per-card 值决定实际比例:

  ```python
  effective_ar = task.aspect_ratio
  if effective_ar == "auto":
      composition = (item.get("composition") or {}) if isinstance(item, dict) else {}
      effective_ar = composition.get("aspect_ratio") or "16:9"
  ok = generate_image_with_nano_banana_pro(
      Content=content,
      output_path=prompt_dir,
      file_name=file_name,
      aspect_ratio=effective_ar,
  )
  ```

- `_resolve_selected_prompts` 保留 card 里 `composition` 字段透传:

  ```python
  out.append({
      "id": pid or f"manual_{len(out) + 1}",
      "fullPrompt": resolved_full,
      "composition": (
          card_map[pid].get("composition") if pid in card_map else item.get("composition")
      ) or {},
  })
  ```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_prompt_precreation_composition_persistence.py -v`
Expected: PASS(5 tests)

同时跑回归:
Run: `pytest tests/test_creation_quick_create.py -v`
Expected: PASS — 手动比例路径行为不变

- [ ] **Step 5: Commit**

```bash
git add app/prompts/creation/prompt_template.py app/prompts/creation/prompt_precreation.py app/services/creation_service/prompt_precreation_service.py app/schemas/creation.py app/services/creation_service/quick_create_service.py tests/services/test_prompt_precreation_composition_persistence.py
git commit -m "feat(S1): step1 决策 auto 长宽比+主体占比并打通尺寸闭环"
```

### Task S1-3: 前端 auto 长宽比选项

**Files:**
- Modify: `page/src/pages/creation/components/QuickCreatePage.tsx:32-38` — `ASPECT_RATIO_OPTIONS` 加 auto
- Modify: `page/src/pages/creation/components/PromptGenPage.tsx:43-46` — `clampPromptAspect` 兼容 auto
- Modify: `page/src/pages/home/components/BatchCreationPage.tsx:200-230` — 批量创作入口加 auto 档
- Modify: `page/src/services/creationApi.ts:99,170,185,345,495` — 类型 Literal 加 `"auto"`
- Verify: `npm run type-check && npm run lint && npm run build`

**Interfaces:**
- Consumes: 后端 `aspect_ratio` Literal 已含 `"auto"` (Task S1-2)
- Produces: 前端 3 个入口都可提交 `aspect_ratio: "auto"`

- [ ] **Step 1: 前端类型改动 — 类型检查先失败**

在改任何 tsx 之前,先让 Union 类型现出问题:先修改 `page/src/services/creationApi.ts` 的其中一处 Literal 加 `"auto"` — 例如第 99 行:

```typescript
  aspect_ratio: "auto" | "16:9" | "4:3" | "1:1" | "3:4" | "9:16";
```

Run: `cd page && npm run type-check`
Expected: FAIL — QuickCreatePage 里 `AspectRatioValue` 的推导集合与该字段不匹配

- [ ] **Step 2: 全量类型对齐**

`page/src/services/creationApi.ts` 第 99/170/185/345/495 全部改为 `"auto" | "16:9" | "4:3" | "1:1" | "3:4" | "9:16"`(字符串字段第 170/185 是 `string`,只需保持不变即可,type-check 会指示实际需要改的位置)。

`page/src/pages/creation/components/QuickCreatePage.tsx:32-38`,`ASPECT_RATIO_OPTIONS` 顶部追加一档:

```typescript
const ASPECT_RATIO_OPTIONS = [
  { label: "Auto", value: "auto" },
  { label: "16:9", value: "16:9" },
  { label: "4:3", value: "4:3" },
  { label: "1:1", value: "1:1" },
  { label: "3:4", value: "3:4" },
  { label: "9:16", value: "9:16" },
] as const;
```

`clampAspect` 允许集合自动跟上(因它从 `ASPECT_RATIO_OPTIONS` 派生),无需改。

`page/src/pages/creation/components/PromptGenPage.tsx:43-46`,把 `clampPromptAspect` 改为(保留原 `"1:1"` 兜底,不改动无效值时的默认行为):

```typescript
function clampPromptAspect(ratio: string): ChainedQuickCreateResumePayload["aspectRatio"] {
  const allowed: ChainedQuickCreateResumePayload["aspectRatio"][] = [
    "auto", "16:9", "4:3", "1:1", "3:4", "9:16",
  ];
  return (allowed.includes(ratio as ChainedQuickCreateResumePayload["aspectRatio"])
    ? ratio
    : "1:1") as ChainedQuickCreateResumePayload["aspectRatio"];
}
```

同一文件,把 `ChainedQuickCreateResumePayload["aspectRatio"]` 类型定义处(在 `creationApi.ts` 里的相关 `Literal` 声明)加入 `"auto"`。

`page/src/pages/home/components/BatchCreationPage.tsx:200-230`,把 `ar` 允许集合与选项列表同步加入 `"auto"`。

- [ ] **Step 3: 类型检查通过**

Run: `cd page && npm run type-check`
Expected: PASS

- [ ] **Step 4: Lint + Build**

Run: `cd page && npm run lint && npm run build`
Expected: PASS(全绿,`app/static/` 产物已更新)

- [ ] **Step 5: Commit**

```bash
git add page/src/services/creationApi.ts page/src/pages/creation/components/QuickCreatePage.tsx page/src/pages/creation/components/PromptGenPage.tsx page/src/pages/home/components/BatchCreationPage.tsx
git commit -m "feat(S1): 前端长宽比选项加 auto 档"
```

---

## S2 — 种子提示词姿态家族均衡 + 背景联动 + 分布偏好预留

### Task S2-1: seed prompt 加姿态家族均衡 + 背景联动 + 分布偏好占位

**Files:**
- Modify: `app/prompts/material/creative_direction.py:71-115` — `creation_direction_seed_prompt` 加姿态家族均衡硬约束、pose_detail 简洁性、反 fetish、背景联动、`{pose_family_distribution_bias}` 占位符
- Modify: `app/services/material_service/seed_prompt_generation_service.py:66-135` — 从方向行读 `home_settings` 折叠进 `chara_creative_direction`;渲染 pose_family 枚举与软指引表;`pose_family_distribution_bias` 本轮渲染为空字符串
- Test: `tests/services/test_seed_prompt_composition_prompt.py::test_seed_prompt_renders_pose_family_enum`
- Test: `tests/services/test_seed_prompt_composition_prompt.py::test_seed_prompt_folds_home_settings_from_direction`
- Test: `tests/services/test_seed_prompt_composition_prompt.py::test_seed_prompt_distribution_bias_is_empty_this_round`

**Interfaces:**
- Consumes: `get_dimension_values("pose_family")` / `get_home_setting_pose_hints()` (S1-1)、`MaterialCreativeDirection.home_settings` (S0-1)
- Produces: 纯函数 `_render_pose_family_enum() -> str`、`_render_home_setting_hints() -> str`、`_build_seed_prompt(*, chara_profile, direction_text, history_seed_prompts) -> str`

- [ ] **Step 1: Write the failing tests**

新建 `tests/services/test_seed_prompt_composition_prompt.py`:

```python
import json


def test_seed_prompt_renders_pose_family_enum():
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp",
        direction_text="direction",
        history_seed_prompts="none",
    )
    for name in ("坐姿", "躺姿", "跪姿", "蹲姿", "倚靠", "盘腿坐"):
        assert name in p, f"missing pose family: {name}"
    assert "≥4" in p or "至少 4" in p or "至少4" in p
    assert "不超过 3" in p or "不超过3" in p


def test_seed_prompt_folds_home_settings_from_direction():
    from app.services.material_service.seed_prompt_generation_service import (
        _fold_home_settings_into_direction_text,
    )
    text = _fold_home_settings_into_direction_text(
        title="T", description="D", home_settings=["卧室大床", "飘窗台"]
    )
    assert "卧室大床" in text and "飘窗台" in text
    assert "home_settings" in text or "居家背景" in text


def test_seed_prompt_fold_no_home_settings_passthrough():
    from app.services.material_service.seed_prompt_generation_service import (
        _fold_home_settings_into_direction_text,
    )
    text = _fold_home_settings_into_direction_text(
        title="T", description="D", home_settings=None
    )
    assert text == "T\n\nD"


def test_seed_prompt_distribution_bias_is_empty_this_round():
    """S2 本轮:分布偏好段渲染为空字符串,占位符不残留。"""
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp", direction_text="direction", history_seed_prompts="none",
    )
    assert "{pose_family_distribution_bias}" not in p


def test_seed_prompt_renders_home_setting_hint_table():
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp", direction_text="direction", history_seed_prompts="none",
    )
    assert "卧室大床" in p and "飘窗台" in p


def test_seed_prompt_includes_home_settings_fallback_when_missing():
    """当方向未提供 home_settings 时,注入 fallback 说明。"""
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp", direction_text="direction", history_seed_prompts="none",
        has_home_settings=False,
    )
    assert "未提供" in p or "自由选择" in p
    assert "{home_settings_fallback_note}" not in p


def test_seed_prompt_no_fallback_note_when_home_settings_present():
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp", direction_text="direction", history_seed_prompts="none",
        has_home_settings=True,
    )
    assert "本方向未提供" not in p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_seed_prompt_composition_prompt.py -v`
Expected: FAIL — 函数不存在

- [ ] **Step 3: Write minimal implementation**

**3.1** `app/prompts/material/creative_direction.py`,在 `creation_direction_seed_prompt` 的「注意事项」块末尾追加两条,并在「特别要求」之前插入两个新块:

在「注意事项」内部现有列表末尾追加:

```
- **姿态家族均衡(硬约束)**:8–10 条种子必须覆盖 ≥4 类姿态家族,任一姿态家族出现不超过 3 条。可选家族(必须从中选取):
{pose_family_enum}
- **腿脚摆放描述简洁性**:每条种子必须包含一句简洁的腿脚自然摆放描述(如"一条腿自然搭在沙发靠背上""盘腿坐,脚踝交叠");严禁复杂多肢交叉、悬空、扭曲。
- **反 fetish 基调**:腿脚摆放描述不得带有暗示性或刻意聚焦,以自然居家状态为基调。
- **背景联动**:每条种子必须选用「角色创意方向」中 `home_settings` 提供的其中一个居家背景,并优先选择与该背景天然契合的姿态家族。参考软指引表(可创造性发挥,但姿态需自然可行):
{home_setting_hint_table}
{home_settings_fallback_note}
- 8–10 条种子在方向提供的(或你自由选定的)1–3 个背景之间均衡分布。
```

在「特别要求」之前追加分布偏好预留段:

```
**分布偏好(本轮空占位,后续由学习机制注入)**:
{pose_family_distribution_bias}
```

**3.2** `app/services/material_service/seed_prompt_generation_service.py`,`_resolve_direction_text` 上方追加辅助函数并改写调用:

```python
from typing import Optional
from app.services.creation_service.composition_dimensions import (
    get_dimension_values,
    get_home_setting_pose_hints,
)


def _render_pose_family_enum() -> str:
    return "\n".join(
        f"  - `{v.code}` ({v.display_name}): {v.description}"
        for v in get_dimension_values("pose_family")
    )


def _render_home_setting_hints() -> str:
    lines = []
    for setting, poses in get_home_setting_pose_hints():
        lines.append(f"  - {setting} → {' / '.join(poses)}")
    return "\n".join(lines)


def _fold_home_settings_into_direction_text(
    *, title: str, description: str, home_settings: Optional[list[str]]
) -> str:
    if not home_settings:
        return f"{title}\n\n{description}"
    hs_line = "home_settings(候选居家背景框架): " + " / ".join(home_settings)
    return f"{title}\n\n{description}\n\n{hs_line}"


_SEED_HOME_SETTINGS_FALLBACK = (
    "本方向未提供 home_settings 候选列表,请自由选择自然的居家背景(如客厅沙发、卧室大床、书房地毯等),"
    "并让所有种子分布在你选定的 1–3 个背景之间。"
)


def _build_seed_prompt(
    *,
    chara_profile: str,
    direction_text: str,
    history_seed_prompts: str,
    has_home_settings: bool = True,
) -> str:
    home_setting_source = (
        "" if has_home_settings else _SEED_HOME_SETTINGS_FALLBACK
    )
    return creation_direction_seed_prompt.format(
        chara_profile=chara_profile,
        chara_creative_direction=direction_text,
        history_seed_prompts=history_seed_prompts,
        pose_family_enum=_render_pose_family_enum(),
        home_setting_hint_table=_render_home_setting_hints(),
        home_settings_fallback_note=home_setting_source,
        pose_family_distribution_bias="",
    )
```

修改 `_resolve_direction_text`(66–79 行):把 `MaterialCreativeDirection` 行的 `home_settings`(TEXT JSON)一起返回。改造后返回 3 元组 `(text, effective_id, home_settings_list)`:

```python
def _resolve_direction_text(
    db, character_id: str, creative_direction_id: Optional[str]
) -> tuple[str, Optional[str], Optional[list[str]]]:
    if not creative_direction_id:
        return FALLBACK_DIRECTION_TEXT, None, None
    row = db.get(MaterialCreativeDirection, creative_direction_id)
    if row is None or row.character_id != character_id:
        logger.warning(
            "seed task: direction %s invalid (deleted or cross-character); falling back",
            creative_direction_id,
        )
        return FALLBACK_DIRECTION_TEXT, None, None
    home_list: Optional[list[str]] = None
    if row.home_settings:
        try:
            parsed = json.loads(row.home_settings)
            if isinstance(parsed, list):
                home_list = [str(x) for x in parsed if isinstance(x, str) and x.strip()]
        except json.JSONDecodeError:
            home_list = None
    folded = _fold_home_settings_into_direction_text(
        title=row.title, description=row.description, home_settings=home_list
    )
    return folded, creative_direction_id, home_list
```

修改 `run_seed_prompt_task` 中的解包处对齐三元组:

```python
                direction_text, effective_direction_id, home_list = _resolve_direction_text(
                    db, character_id, requested_direction_id
                )
```

并把 `prompt = creation_direction_seed_prompt.format(...)` 一行替换为:

```python
            prompt = _build_seed_prompt(
                chara_profile=chara_profile,
                direction_text=direction_text,
                history_seed_prompts=history_text,
                has_home_settings=bool(home_list),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_seed_prompt_composition_prompt.py -v`
Expected: PASS(5 tests)

同时跑现有 seed_prompt 回归:
Run: `pytest tests/services/test_seed_prompt_generation_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/prompts/material/creative_direction.py app/services/material_service/seed_prompt_generation_service.py tests/services/test_seed_prompt_composition_prompt.py
git commit -m "feat(S2): seed prompt 加姿态家族均衡+背景联动+分布偏好占位"
```

---

## S3 — step1 引入机位方位 + 机位高度枚举决策

### Task S3-1: step1 任务步骤 0 增机位方位与高度 + 结构化持久化

**Files:**
- Modify: `app/prompts/creation/prompt_precreation.py` — `prompt_step1` 任务步骤 0 追加机位方位、机位高度选择;Negative Prompt 段追加风险标签合并指令(本轮空源)
- Modify: `app/prompts/creation/prompt_template.py` — 「镜头与构图」段顶部加 2 行回填位 `[SHOOTING_ANGLE]` / `[CAMERA_HEIGHT]`
- Modify: `app/services/creation_service/prompt_precreation_service.py` — `_build_step1_prompt` 渲染机位维度枚举;`_parse_step1_composition` 扩集到 `shooting_angle` / `camera_height`;写入 card 的 `composition` 字段
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_parse_step1_composition_includes_shooting_and_height`
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_build_step1_prompt_renders_shooting_and_camera_enums`
(back_glance 互斥测试已按用户决策从 S3 移除,统一交给后续反 fetish 模块处理)
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_step1_camera_bias_placeholder_empty`

**Interfaces:**
- Consumes: S1-1 的 `get_dimension_values("shooting_angle")` / `("camera_height")`;S1-2 的 `_build_step1_prompt(*, chara_profile, seed_prompt) -> str` / `_parse_step1_composition` / `_ENUM_CODES`
- Produces: card `composition` 字段扩展形态 `{"aspect_ratio","subject_area_min","shooting_angle","camera_height"}`(任一均可缺)

- [ ] **Step 1: Write the failing tests**

在 `tests/services/test_prompt_precreation_composition_persistence.py` 追加:

```python
def test_build_step1_prompt_renders_shooting_and_camera_enums():
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    for name in ("正面", "3/4 正面", "侧面", "3/4 背面", "背面(回眸)"):
        assert name in p, f"missing shooting_angle {name}"
    for name in ("略仰", "平视", "略俯", "大俯"):
        assert name in p, f"missing camera_height {name}"


def test_parse_step1_composition_includes_shooting_and_height():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
aspect_ratio: 1:1
subject_area_min: 0.65
shooting_angle: three_quarter
camera_height: slight_up
"""
    result = _parse_step1_composition(text)
    assert result == {
        "aspect_ratio": "1:1",
        "subject_area_min": "0.65",
        "shooting_angle": "three_quarter",
        "camera_height": "slight_up",
    }


def test_parse_step1_composition_rejects_shooting_out_of_enum():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
shooting_angle: from_below_between_legs
camera_height: eye_level
"""
    result = _parse_step1_composition(text)
    assert "shooting_angle" not in result
    assert result["camera_height"] == "eye_level"


def test_step1_camera_bias_placeholder_empty():
    """本轮 step1 的镜头组合分布偏好段渲染为空,占位符不残留。"""
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    assert "{camera_combo_distribution_bias}" not in p
    assert "{negative_prompt_risk_tags}" not in p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_prompt_precreation_composition_persistence.py -v -k "shooting or camera or bias_placeholder"`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

**3.1** `app/prompts/creation/prompt_precreation.py`,把 `prompt_step1` 里现有任务步骤 1 之前追加(**auto/manual 都要**):

```
{step1_task_step_zero_camera}
```

在任务步骤 0-cam 之后、其他任务步骤(现有「1、根据用户的需求」)之前,插入镜头组合分布偏好预留段(与 S2 的 `pose_family_distribution_bias` 段对称;本轮渲染为空字符串,供后续学习机制注入):

```
**镜头组合分布偏好(可选;本轮为空,由后续学习机制注入)**:
{camera_combo_distribution_bias}
```

在 Negative Prompt 相关字段说明后,追加(Prompt 里已有列出的 `**Negative Prompt**` 字段说明括号后紧跟):

```
{negative_prompt_risk_tags}
```

调整 `_build_step1_prompt` 常量与拼装:

```python
_STEP0_CAMERA_TEMPLATE = (
    "0-cam、**镜头维度决策(先于画面脑补)**:请从以下枚举中选择本次创作的机位方位与机位高度各一个:\n"
    "机位方位(shooting_angle)候选:\n"
    "{shooting_angle_enum}\n"
    "机位高度(camera_height)候选:\n"
    "{camera_height_enum}\n"
    "请把选择结果一并写入下方 [COMPOSITION_DECISION] 决策块。"
)
```

修改 `_build_step1_prompt` 内部装配:

```python
    step_zero_camera = _STEP0_CAMERA_TEMPLATE.format(
        shooting_angle_enum=_render_dimension_list("shooting_angle"),
        camera_height_enum=_render_dimension_list("camera_height"),
    )
    composition_output = (  # 覆盖 S1-2 的 composition_output
        "7、请在输出的模板正文**之前**,插入一段用 `**[COMPOSITION_DECISION]**` 标记的构图决策说明,"
        "格式如下(每行取上一步选定的 code 值):\n"
        "```\n"
        "**[COMPOSITION_DECISION]**\n"
        "aspect_ratio: <code>\n"
        "subject_area_min: <code>\n"
        "shooting_angle: <code>\n"
        "camera_height: <code>\n"
        "```\n"
        "后续「任务目标」与「构图硬约束」段中,请用你选定的长宽比替换 `{aspect_ratio}` 占位符、"
        "用主体占比下限的百分比值替换 `{subject_area_min_pct}` 占位符。"
    )
    return prompt_step1.format(
        chara_profile=chara_profile,
        seed_prompt=seed_prompt,
        init_template=init_template,
        good_template=good_template1,
        step1_task_step_zero=step_zero,
        step1_task_step_zero_camera=step_zero_camera,
        step1_composition_output_requirement=composition_output,
        camera_combo_distribution_bias="",
        negative_prompt_risk_tags="",
    )
```

补充 `_ENUM_CODES`:

```python
_ENUM_CODES.update({
    "shooting_angle": {v.code for v in get_dimension_values("shooting_angle")},
    "camera_height":  {v.code for v in get_dimension_values("camera_height")},
})
```

**3.2** `app/prompts/creation/prompt_template.py`,把「镜头与构图(让人一眼"WoW")」这一段的括号说明改为:

```
**镜头与构图(让人一眼"WoW")**:
`[SHOOTING_ANGLE]` <从 step1 决策块回填,例:three_quarter (3/4 正面)>
`[CAMERA_HEIGHT]` <从 step1 决策块回填,例:slight_up (略仰)>
(镜头和构图的描述,指定 **等效焦段范围**,并在镜头决策基础上展开三角构图、前中后景分层、焦点路径,等等,需要让人一眼"WoW")
```

`good_template1` 同段同步替换为示例值(如 `three_quarter` / `slight_up`),保持模板可读性。

**3.3** `_parse_step1_composition` 自动因 `_ENUM_CODES` 扩展而支持新键,不需要修改;新增的两键会通过 card 的 `composition` 字段自动持久化,不需要额外改动 `_build_cards`(S1-2 已支持透传)。

**3.4** quick_create 的 per-card 出图循环无需感知镜头维度(镜头决策已折叠进 fullPrompt);仅 aspect_ratio 需 per-card 取值,S1-2 已实现。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_prompt_precreation_composition_persistence.py -v`
Expected: PASS(全部,含 S1 已有的 5 条 + S3 新增 5 条)

- [ ] **Step 5: Commit**

```bash
git add app/prompts/creation/prompt_precreation.py app/prompts/creation/prompt_template.py app/services/creation_service/prompt_precreation_service.py tests/services/test_prompt_precreation_composition_persistence.py
git commit -m "feat(S3): step1 引入机位方位+高度维度决策"
```

---

## S4 — step1 引入视线枚举决策

### Task S4-1: 视线枚举加入任务步骤 0 + 结构化持久化

**Files:**
- Modify: `app/prompts/creation/prompt_precreation.py` — 任务步骤 0-cam 中追加 gaze_direction 决策
- Modify: `app/prompts/creation/prompt_template.py` — 「镜头与构图」段顶部再加 1 行 `[GAZE_DIRECTION]` 回填位
- Modify: `app/services/creation_service/prompt_precreation_service.py` — `_STEP0_CAMERA_TEMPLATE` 追加 gaze 段与 output 段;`_ENUM_CODES` 加 gaze_direction
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_parse_step1_composition_includes_gaze`
- Test: `tests/services/test_prompt_precreation_composition_persistence.py::test_build_step1_prompt_renders_gaze_enum`

**Interfaces:**
- Consumes: S1-1 的 `get_dimension_values("gaze_direction")`;S3-1 的 `_STEP0_CAMERA_TEMPLATE` / `_ENUM_CODES`
- Produces: card `composition` 字段进一步扩展含 `gaze_direction`

- [ ] **Step 1: Write the failing tests**

在 `tests/services/test_prompt_precreation_composition_persistence.py` 追加:

```python
def test_build_step1_prompt_renders_gaze_enum():
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    for name in ("看镜头", "3/4 看出画", "侧面看", "看下方", "看远处"):
        assert name in p, f"missing gaze_direction {name}"


def test_parse_step1_composition_includes_gaze():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
aspect_ratio: 1:1
subject_area_min: 0.65
shooting_angle: front
camera_height: eye_level
gaze_direction: to_camera
"""
    result = _parse_step1_composition(text)
    assert result["gaze_direction"] == "to_camera"


def test_parse_step1_composition_rejects_gaze_out_of_enum():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
gaze_direction: sultry_stare
"""
    result = _parse_step1_composition(text)
    assert "gaze_direction" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_prompt_precreation_composition_persistence.py -v -k gaze`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

**3.1** `app/services/creation_service/prompt_precreation_service.py`,`_STEP0_CAMERA_TEMPLATE` 扩为:

```python
_STEP0_CAMERA_TEMPLATE = (
    "0-cam、**镜头维度决策(先于画面脑补)**:请从以下枚举中各选择一个:\n"
    "机位方位(shooting_angle)候选:\n"
    "{shooting_angle_enum}\n"
    "机位高度(camera_height)候选:\n"
    "{camera_height_enum}\n"
    "视线方向(gaze_direction)候选:\n"
    "{gaze_direction_enum}\n"
    "请把三项选择一并写入下方 [COMPOSITION_DECISION] 决策块。"
)
```

`_build_step1_prompt` 的 `step_zero_camera` 组装处补上 `gaze_direction_enum=_render_dimension_list("gaze_direction")`;`composition_output` 示例决策块补一行 `gaze_direction: <code>`。

`_ENUM_CODES` 追加:

```python
_ENUM_CODES["gaze_direction"] = {v.code for v in get_dimension_values("gaze_direction")}
```

**3.2** `app/prompts/creation/prompt_template.py`,「镜头与构图」段顶部再加一行(接 S3 的两行后):

```
`[GAZE_DIRECTION]` <从 step1 决策块回填,例:to_camera (看镜头)>
```

`good_template1` 同段补示例。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_prompt_precreation_composition_persistence.py -v`
Expected: PASS(全部)

- [ ] **Step 5: Commit**

```bash
git add app/prompts/creation/prompt_precreation.py app/prompts/creation/prompt_template.py app/services/creation_service/prompt_precreation_service.py tests/services/test_prompt_precreation_composition_persistence.py
git commit -m "feat(S4): step1 补齐视线维度决策与结构化持久化"
```

---

## S5 — review 加入反同质化评分 + 权重表预留

### Task S5-1: prompt_review 增维度差异分与权重表独立预留段

**Files:**
- Modify: `app/prompts/creation/prompt_precreation.py` — `prompt_review` 增维度差异分段落 + 独立权重表预留段
- Modify: `app/services/creation_service/prompt_precreation_service.py` — `_run_review` 渲染时把维度权重表段填空
- Test: `tests/services/test_prompt_review_composition.py::test_review_prompt_mentions_composition_diversity_dimensions`
- Test: `tests/services/test_prompt_review_composition.py::test_review_prompt_weight_table_placeholder_rendered_empty`
- Test: `tests/services/test_prompt_review_composition.py::test_review_prompt_separates_diversity_and_weight_sections`

**Interfaces:**
- Consumes: `prompt_review` 现有 `{input_content}` / `{seed_prompt}` / `{chara_profile}` / `{num_best_prompts}` 参数
- Produces: `_build_review_prompt(*, input_content, seed_prompt, chara_profile, num_best_prompts) -> str`(纯函数,供测试);内部渲染 `{composition_diversity_criteria}` 恒定文案 + `{composition_weight_table}` 空占位

- [ ] **Step 1: Write the failing tests**

新建 `tests/services/test_prompt_review_composition.py`:

```python
def test_review_prompt_mentions_composition_diversity_dimensions():
    from app.services.creation_service.prompt_precreation_service import _build_review_prompt
    p = _build_review_prompt(
        input_content="[]", seed_prompt="sp", chara_profile="cp", num_best_prompts=2,
    )
    for kw in ("shooting_angle", "camera_height", "gaze_direction", "pose_family"):
        assert kw in p, f"missing dimension {kw} in review prompt"
    assert "差异" in p or "多样" in p


def test_review_prompt_weight_table_placeholder_rendered_empty():
    from app.services.creation_service.prompt_precreation_service import _build_review_prompt
    p = _build_review_prompt(
        input_content="[]", seed_prompt="sp", chara_profile="cp", num_best_prompts=2,
    )
    assert "{composition_weight_table}" not in p
    assert "{composition_diversity_criteria}" not in p


def test_review_prompt_separates_diversity_and_weight_sections():
    from app.services.creation_service.prompt_precreation_service import _build_review_prompt
    p = _build_review_prompt(
        input_content="[]", seed_prompt="sp", chara_profile="cp", num_best_prompts=2,
    )
    diversity_idx = p.find("维度差异")
    weight_idx = p.find("维度权重表")
    assert diversity_idx != -1 and weight_idx != -1
    assert diversity_idx < weight_idx, "diversity block must come before weight block"


def test_review_prompt_num_best_prompts_still_injected():
    from app.services.creation_service.prompt_precreation_service import _build_review_prompt
    p = _build_review_prompt(
        input_content="[]", seed_prompt="sp", chara_profile="cp", num_best_prompts=3,
    )
    assert "3" in p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_prompt_review_composition.py -v`
Expected: FAIL — `_build_review_prompt` 不存在

- [ ] **Step 3: Write minimal implementation**

**3.1** `app/prompts/creation/prompt_precreation.py`,把 `prompt_review` 的开头段扩展为(在 `**注意**,避免任何色情...` 一行之前追加两个独立段落):

```
**维度差异分(始终生效)**:
{composition_diversity_criteria}

**维度权重表(可选二级排序;本轮为空,由后续学习机制注入)**:
{composition_weight_table}
```

**3.2** `app/services/creation_service/prompt_precreation_service.py`,追加纯函数(在 `_run_review` 之前):

```python
_REVIEW_DIVERSITY_CRITERIA = (
    "在质量相近的候选之间,优先挑选 `shooting_angle` / `camera_height` / `gaze_direction` / `pose_family` "
    "维度组合差异更大的 {num_best_prompts} 条,以保证批次内构图多样性。差异度评估以候选 Prompt 显式声明的 "
    "[COMPOSITION_DECISION] 字段为准;若候选未显式声明,请从其画面描述中推断这四个维度。"
)


def _build_review_prompt(
    *,
    input_content: str,
    seed_prompt: str,
    chara_profile: str,
    num_best_prompts: int,
) -> str:
    return prompt_review.format(
        input_content=input_content,
        seed_prompt=seed_prompt,
        chara_profile=chara_profile,
        num_best_prompts=num_best_prompts,
        composition_diversity_criteria=_REVIEW_DIVERSITY_CRITERIA.format(
            num_best_prompts=num_best_prompts
        ),
        composition_weight_table="(本轮为空,由后续学习机制注入)",
    )
```

`_run_review` 中 `call_main`:

```python
    def call_main() -> str:
        p = _build_review_prompt(
            input_content=input_content,
            seed_prompt=seed_prompt,
            chara_profile=chara_profile,
            num_best_prompts=n,
        )
        return yibu_gemini_infer(p, thinking_level="high", temperature=0.7)
```

`call_backup` 保持原样(仍走 `prompt_review_backup`,该 Prompt 是无差异分/权重段的兜底路径,以确保 JSON 输出格式稳定)。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_prompt_review_composition.py -v`
Expected: PASS(4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/prompts/creation/prompt_precreation.py app/services/creation_service/prompt_precreation_service.py tests/services/test_prompt_review_composition.py
git commit -m "feat(S5): prompt_review 增维度差异分与权重表预留段"
```

---

## 全量回归 + 手工验证

### Task Z-1: 全量测试回归 + 前端类型/构建回归 + 手工验证清单

**Files:**
- Verify only(不产生代码改动)

**Interfaces:**
- Consumes: 全部前置切片
- Produces: 一份可勾选的验证记录(供 review 用)

- [ ] **Step 1: 后端全量 pytest**

Run: `pytest -x -q`
Expected: 全绿。若失败,回到对应切片修补 — **不允许**通过修改测试来掩盖行为回退。

- [ ] **Step 2: 前端 lint / type-check / build**

Run: `cd page && npm run type-check && npm run lint && npm run build`
Expected: 全绿,`app/static/` 有产物更新。

- [ ] **Step 3: 手工端到端(需 API key,本机跑)**

启动:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

对某已有角色执行以下手工验证清单(逐项 ✅ / ❌ 记录):

1. **S0 验证**:新建一条创意方向,DB `material_creative_directions.home_settings` 字段非空且为 1–3 个短语数组;前端 `GET /api/material/characters/{id}/creative-directions` 响应含 `home_settings`。
2. **S1 验证(auto 尺寸闭环)**:前端选 `auto` 长宽比,提交预生成 → 打开预生成结果 → 每张 card 的 `composition.aspect_ratio` 存在;进一步走一键创作,查看 `data/beautify/quick_create/.../result.json` 中每张图对应的实际图片尺寸符合该 card 的 `aspect_ratio` 而非入口的 `auto`。
3. **S1 手动比例回归**:选 `16:9` 手动比例,同样跑一次预生成 → 一键创作,画布尺寸应始终为 16:9,不受 step1 影响。
4. **S2 验证**:同一角色重新生成一批种子,观察 8–10 条种子的姿态家族分布是否覆盖 ≥4 类;每条是否明确关联一个 `home_settings` 中的短语;腿脚描述是否简洁自然,无复杂多肢或 fetish 语言。
5. **S3 验证**:同一 seed 跑 N 张,查看每张 card 的 `composition.shooting_angle` × `camera_height` 组合分布是否分散。
6. **S4 验证**:同上,card 里 `composition.gaze_direction` 存在且取值合理。
7. **S5 验证**:对同一批 2N 候选跑 review,新 review 挑出的 N 条构图维度差异 vs 旧 review 挑的 N 条,差异度目测提升(或至少不劣化)。

- [ ] **Step 4: 提交手工验证记录(可选)**

若手工验证过程中发现问题,回到对应切片修补 — 每一处修补都是 fresh commit。

---

## 12. 关联文档

- 设计 spec:`docs/superpowers/specs/2026-06-30-creation-composition-planning-design.md`
- 现有创作工作流总览:`claude_docs/architecture.md`
- 创意方向 / 种子提示词模块设计:`claude_docs/feature_creative_direction/design.md`










