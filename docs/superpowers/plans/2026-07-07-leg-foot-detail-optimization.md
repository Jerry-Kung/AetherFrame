# 第二阶段实施计划：出图细节深度优化（腿脚侧重）+ Feedback Case 数据闭环

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立"出图→人工 feedback→结构化 Case 归档→大批量聚合分析"的长期数据闭环，并在其上以 A/B 实验（exp002）验证一套腿脚/袜子描写规范能否显著压低腿脚崩坏率。

**Architecture:** 两层交付。(1) Feedback Case 数据闭环——纯 Python、TDD 可测、独立可合入：崩坏分类活字典（taxonomy）、Case 文本格式解析/序列化、实验结果→Case 归档器、大批量聚合分析器。(2) exp002 实验资产——benchmark_v2 高危基准集、exp002 配置、腿脚规则包（对生产模板的增量编辑 + 结构断言测试）、运行手册。代码放 `experiments/casebank/`（新包），数据放 `experiments/cases/`（数据目录），沿用既有 `experiments/{config,layout,runner,report}.py` 基建。

**Tech Stack:** Python 3 / pytest / PyYAML；复用 `experiments.config.load_benchmark`、`experiments.layout.ExpLayout`、`experiments.report`；生产 Prompt 模板位于 `app/prompts/creation/`。

## Global Constraints

以下为贯穿全部任务的硬约束，每个任务的要求都隐含包含本节（逐条来自设计文档 §5 与相关记忆，值照抄）：

- **腿脚自然展示第一原则不可违反**：任何规则不得靠"藏脚/减少腿脚出镜"降崩坏率；R5 只限制极端姿势，不限制腿脚展示本身。
- **slim 基准不动摇**：规则包是 slim 之上的腿脚专项增量，不推翻 exp001 六条瘦身规则（单一表情+视线、锚点 ≤8 字绑参考图、无文学修辞/解剖学词汇、无机器码、Negative 只留 3-5 条）。
- **冻结件不可编辑**：`experiments/variants/exp001/**`、`experiments/results/exp001*/**`、`experiments/fixtures/benchmark_v1.yaml` 等已冻结实验件永不回改；exp002 一律新建文件。
- **config.py 保密**：`app/tools/llm/config.py` 已 gitignore、含 API key，不入库不外发。
- **Case 原文与 taxonomy_version 永不回改**：taxonomy 演化时靠 aliases 映射归一，历史 Case 的 tags/version 字段冻结。
- **代码/数据分离**：闭环代码在 `experiments/casebank/`，taxonomy 与 Case 数据在 `experiments/cases/`。
- **实验先行**：规则包对生产模板的改动须先由 exp002 A/B 揭盲验证再决定是否长期保留；不因"已提交"等同"已采纳"。

---

## 文件结构

新建/修改的文件与职责：

**Part A — Feedback Case 数据闭环（代码 `experiments/casebank/`，数据 `experiments/cases/`）**
- `experiments/cases/taxonomy.yaml`（新建，数据）：崩坏分类活字典，`version` + 两层 `tags` + `aliases`。
- `experiments/casebank/__init__.py`（新建）：空包标记。
- `experiments/casebank/taxonomy.py`（新建）：`Taxonomy` 加载/校验/归一。
- `experiments/casebank/case_format.py`（新建）：`Case` dataclass + `parse_cases` / `serialize_cases` 文本互转。
- `experiments/casebank/case_archive.py`（新建）：实验结果（manifest + benchmark + 盲评 ratings）→ Case 列表 → 归档文件。
- `experiments/casebank/case_analyze.py`（新建）：扫描 Case 目录 → taxonomy 归一 → 交叉统计崩坏率 + 高频 tag 排行 + CLI。
- 测试：`tests/experiments/test_taxonomy.py`、`test_case_format.py`、`test_case_archive.py`、`test_case_analyze.py`（新建）。

**Part B — exp002 实验资产**
- `experiments/fixtures/benchmark_v2.yaml`（新建）：腿脚高危侧重基准集。
- `experiments/configs/exp002.yaml`（新建）：exp002 实验配置。
- 规则包落点（修改）：`app/prompts/creation/prompt_precreation.py`（step1 腿脚设计指引）、`app/prompts/creation/prompt_template.py`（`init_template` 字段说明 + `good_template1` 范例）。
- 测试：`tests/experiments/test_benchmark_v2.py`（新建）、`tests/services/test_rulepack_template_structure.py`（新建）。
- `docs/superpowers/specs/2026-07-07-exp002-runbook.md`（新建）：exp002 运行手册（生成→盲评→归档→分析）。

---

## Task 1: 崩坏分类活字典 taxonomy

**Files:**
- Create: `experiments/cases/taxonomy.yaml`
- Create: `experiments/casebank/__init__.py`
- Create: `experiments/casebank/taxonomy.py`
- Test: `tests/experiments/test_taxonomy.py`

**Interfaces:**
- Produces:
  - `load_taxonomy(path: str) -> Taxonomy`
  - `Taxonomy` (frozen dataclass): `version: str`, `tags: dict[str, list[str]]`（父→子列表）, `aliases: dict[str, str]`（`旧父/旧子` → `新父/新子`，可链式）
  - `Taxonomy.is_valid(tag: str) -> bool`：`父/子` 形式且存在
  - `Taxonomy.normalize(tag: str) -> str`：先按 aliases 链式解析到规范值，再校验；非法则 `raise ValueError`
  - `Taxonomy.parent_of(tag: str) -> str`：返回归一后的父 tag

- [ ] **Step 1: 写 taxonomy.yaml 数据文件**

```yaml
# 崩坏分类活字典（设计文档 §2.2）。tags 为两层：父类 -> 子类列表。
# 演化规则：新增子 tag 需 bump version；合并/重挂父时把旧 tag 写入 aliases 映射，
# 历史 Case 的 tags 与 taxonomy_version 永不回改，聚合分析时按 aliases 归一。
version: v1
tags:
  脚部: [简陋, 夸张, 比例结构]
  腿部: [结构错误]
  袜子: [上色感, 塑料袋感, 皱褶夸张, 缺失]
  画风: [写实化, 平面2D]
  身体比例: [整体不协调]
  其他: [未分类]
aliases: {}
```

- [ ] **Step 2: 写失败测试**

```python
# tests/experiments/test_taxonomy.py
import os

import pytest

from experiments.casebank.taxonomy import Taxonomy, load_taxonomy

DATA = "experiments/cases/taxonomy.yaml"


def test_loads_real_taxonomy_v1():
    tx = load_taxonomy(DATA)
    assert tx.version == "v1"
    assert "袜子" in tx.tags
    assert "上色感" in tx.tags["袜子"]


def test_is_valid_accepts_known_child_tag():
    tx = load_taxonomy(DATA)
    assert tx.is_valid("袜子/上色感") is True
    assert tx.is_valid("脚部/夸张") is True


def test_is_valid_rejects_unknown_and_malformed():
    tx = load_taxonomy(DATA)
    assert tx.is_valid("袜子/不存在") is False
    assert tx.is_valid("不存在/上色感") is False
    assert tx.is_valid("袜子") is False          # 缺子类
    assert tx.is_valid("a/b/c") is False         # 层级过多


def test_normalize_passthrough_for_canonical_tag():
    tx = load_taxonomy(DATA)
    assert tx.normalize("袜子/上色感") == "袜子/上色感"


def test_normalize_resolves_alias_chain():
    tx = Taxonomy(
        version="v3",
        tags={"袜子": ["上色感"]},
        aliases={"丝袜/涂色": "袜子/上色", "袜子/上色": "袜子/上色感"},
    )
    assert tx.normalize("丝袜/涂色") == "袜子/上色感"


def test_normalize_raises_on_unknown():
    tx = load_taxonomy(DATA)
    with pytest.raises(ValueError):
        tx.normalize("袜子/查无此项")


def test_parent_of_returns_normalized_parent():
    tx = load_taxonomy(DATA)
    assert tx.parent_of("袜子/上色感") == "袜子"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/experiments/test_taxonomy.py -v`
Expected: FAIL（`ModuleNotFoundError: experiments.casebank.taxonomy`）

- [ ] **Step 4: 写实现**

```python
# experiments/casebank/__init__.py
```
（空文件）

```python
# experiments/casebank/taxonomy.py
"""崩坏分类活字典：加载、校验、按 aliases 链式归一。数据在 experiments/cases/taxonomy.yaml。"""
from dataclasses import dataclass

import yaml

_MAX_ALIAS_HOPS = 16


@dataclass(frozen=True)
class Taxonomy:
    version: str
    tags: dict          # 父 -> [子, ...]
    aliases: dict       # "旧父/旧子" -> "新父/新子"

    def is_valid(self, tag: str) -> bool:
        parts = tag.split("/")
        if len(parts) != 2:
            return False
        parent, child = parts
        return parent in self.tags and child in self.tags[parent]

    def normalize(self, tag: str) -> str:
        seen = set()
        cur = tag
        hops = 0
        while cur in self.aliases:
            if cur in seen or hops >= _MAX_ALIAS_HOPS:
                raise ValueError(f"tag alias 成环或过深: {tag}")
            seen.add(cur)
            cur = self.aliases[cur]
            hops += 1
        if not self.is_valid(cur):
            raise ValueError(f"未知崩坏 tag（归一后 {cur}）: {tag}")
        return cur

    def parent_of(self, tag: str) -> str:
        return self.normalize(tag).split("/")[0]


def load_taxonomy(path: str) -> Taxonomy:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    tags = {str(k): [str(c) for c in (v or [])]
            for k, v in (raw.get("tags") or {}).items()}
    if not tags:
        raise ValueError("taxonomy 缺少 tags")
    aliases = {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}
    return Taxonomy(version=str(raw.get("version", "")),
                    tags=tags, aliases=aliases)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/experiments/test_taxonomy.py -v`
Expected: PASS（7 passed）

- [ ] **Step 6: 提交**

```bash
git add experiments/cases/taxonomy.yaml experiments/casebank/__init__.py experiments/casebank/taxonomy.py tests/experiments/test_taxonomy.py
git commit -m "feat(casebank): 崩坏分类活字典 taxonomy（两层 tag + aliases 归一）"
```

---

## Task 2: Case 文本格式解析/序列化

**Files:**
- Create: `experiments/casebank/case_format.py`
- Test: `tests/experiments/test_case_format.py`

**Interfaces:**
- Consumes: 无（纯文本 ↔ dataclass）
- Produces:
  - `Case` (dataclass, mutable): `case_id:str`, `date:str`, `source:str`, `character:str`, `seed_id:str`, `difficulty:str`, `variant:str`, `images:int`, `bad:int`, `tags:list[str]`, `taxonomy_version:str`, `seed_prompt:str`, `final_prompt:str`, `feedback:str`
  - `serialize_cases(cases: list[Case]) -> str`
  - `parse_cases(text: str) -> list[Case]`
  - 往返：`parse_cases(serialize_cases(x)) == x`

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_case_format.py
from experiments.casebank.case_format import Case, parse_cases, serialize_cases


def _sample():
    return Case(
        case_id="Case_exp002_01", date="2026-07-07", source="exp002",
        character="castorice", seed_id="cas_med_squat", difficulty="medium",
        variant="control", images=5, bad=2,
        tags=["袜子/上色感", "袜子/皱褶夸张"], taxonomy_version="v1",
        seed_prompt="角色乖巧地蹲在玄关。", final_prompt="**[COMPOSITION_DECISION]**\naspect_ratio: 3:4\n正文……",
        feedback="",
    )


def test_serialize_contains_all_sections():
    s = serialize_cases([_sample()])
    assert "Case_exp002_01:" in s
    assert "[meta]" in s
    assert "[seed_prompt]" in s
    assert "[final_prompt]" in s
    assert "[feed_back]" in s
    assert "variant: control" in s
    assert "tags: [袜子/上色感, 袜子/皱褶夸张]" in s


def test_round_trip_single_case():
    cases = [_sample()]
    assert parse_cases(serialize_cases(cases)) == cases


def test_round_trip_multiple_cases_and_empty_tags():
    c1 = _sample()
    c2 = _sample()
    c2.case_id = "Case_exp002_02"
    c2.variant = "rulepack"
    c2.tags = []
    c2.bad = 0
    c2.feedback = "三张均正常。\n腿脚袜表现良好。"   # 多行 feedback
    cases = [c1, c2]
    assert parse_cases(serialize_cases(cases)) == cases


def test_parse_preserves_multiline_final_prompt():
    c = _sample()
    c.final_prompt = "第一行\n第二行\n**Negative Prompt**：穿鞋、多指。"
    out = parse_cases(serialize_cases([c]))
    assert out[0].final_prompt == c.final_prompt


def test_parse_tolerates_feedback_with_brackets_free_text():
    c = _sample()
    c.feedback = "问题：脚部[轻微]崩坏"
    out = parse_cases(serialize_cases([c]))
    assert out[0].feedback == c.feedback
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/experiments/test_case_format.py -v`
Expected: FAIL（`ModuleNotFoundError: experiments.casebank.case_format`）

- [ ] **Step 3: 写实现**

```python
# experiments/casebank/case_format.py
"""Case 文本格式（设计文档 §2.1）解析/序列化。一批多 Case 存一个文件，与
experiments/cases 现行手工样例结构兼容，另加 [meta] 结构化头部与 tags。"""
from dataclasses import dataclass, field

_META_INT = ("images", "bad")
_SECTIONS = ("[meta]", "[seed_prompt]", "[final_prompt]", "[feed_back]")


@dataclass
class Case:
    case_id: str
    date: str
    source: str
    character: str
    seed_id: str
    difficulty: str
    variant: str
    images: int
    bad: int
    tags: list = field(default_factory=list)
    taxonomy_version: str = "v1"
    seed_prompt: str = ""
    final_prompt: str = ""
    feedback: str = ""


def _fmt_tags(tags: list) -> str:
    return "[" + ", ".join(tags) + "]"


def _parse_tags(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip() for t in raw.split(",") if t.strip()]


def serialize_cases(cases: list) -> str:
    blocks = []
    for c in cases:
        blocks.append(
            f"{c.case_id}:\n"
            "[meta]\n"
            f"date: {c.date}\n"
            f"source: {c.source}\n"
            f"character: {c.character}\n"
            f"seed_id: {c.seed_id}\n"
            f"difficulty: {c.difficulty}\n"
            f"variant: {c.variant}\n"
            f"images: {c.images}\n"
            f"bad: {c.bad}\n"
            f"tags: {_fmt_tags(c.tags)}\n"
            f"taxonomy_version: {c.taxonomy_version}\n"
            "[seed_prompt]\n"
            f"{c.seed_prompt}\n"
            "[final_prompt]\n"
            f"{c.final_prompt}\n"
            "[feed_back]\n"
            f"{c.feedback}\n"
        )
    return "\n".join(blocks)


def _split_case_chunks(text: str) -> list:
    """按 `Xxx:` 且下一非空行为 [meta] 的行切块，返回 [(case_id, body_lines)]。"""
    lines = text.splitlines()
    chunks = []
    cur_id = None
    cur = []
    for i, line in enumerate(lines):
        is_header = (
            line.endswith(":")
            and not line.startswith("[")
            and i + 1 < len(lines)
            and lines[i + 1].strip() == "[meta]"
        )
        if is_header:
            if cur_id is not None:
                chunks.append((cur_id, cur))
            cur_id = line[:-1].strip()
            cur = []
        elif cur_id is not None:
            cur.append(line)
    if cur_id is not None:
        chunks.append((cur_id, cur))
    return chunks


def _section_map(body_lines: list) -> dict:
    """把 body 行按 [meta]/[seed_prompt]/[final_prompt]/[feed_back] 分段。"""
    out = {}
    cur = None
    for line in body_lines:
        if line.strip() in _SECTIONS:
            cur = line.strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def parse_cases(text: str) -> list:
    cases = []
    for case_id, body in _split_case_chunks(text):
        sec = _section_map(body)
        meta = {}
        for line in sec.get("[meta]", []):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        # 正文段末尾会多一个 serialize 时补的换行，rstrip 一个尾随空行
        def _text(name):
            seg = sec.get(name, [])
            while seg and seg[-1] == "":
                seg = seg[:-1]
            return "\n".join(seg)
        cases.append(Case(
            case_id=case_id,
            date=meta.get("date", ""),
            source=meta.get("source", ""),
            character=meta.get("character", ""),
            seed_id=meta.get("seed_id", ""),
            difficulty=meta.get("difficulty", ""),
            variant=meta.get("variant", ""),
            images=int(meta.get("images", 0)),
            bad=int(meta.get("bad", 0)),
            tags=_parse_tags(meta.get("tags", "[]")),
            taxonomy_version=meta.get("taxonomy_version", "v1"),
            seed_prompt=_text("[seed_prompt]"),
            final_prompt=_text("[final_prompt]"),
            feedback=_text("[feed_back]"),
        ))
    return cases
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/experiments/test_case_format.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add experiments/casebank/case_format.py tests/experiments/test_case_format.py
git commit -m "feat(casebank): Case 文本格式 parse/serialize 往返"
```

---

## Task 3: 实验结果 → Case 归档器

**Files:**
- Create: `experiments/casebank/case_archive.py`
- Test: `tests/experiments/test_case_archive.py`

**Interfaces:**
- Consumes:
  - `experiments.layout.ExpLayout`（`root`、`manifest_path()`、`prompt_path(variant, seed_id)`）
  - `experiments.config.load_benchmark` → `Benchmark.seeds`（`SeedCase.seed_id/difficulty/character_id/text`）
  - `Case`（Task 2）
  - manifest 结构：`{"entries": [{"variant","seed_id","image_index","character_id","ok",...}]}`
  - 盲评产物：`review_key.json`（`{"R001": {"variant","seed_id","image_index"}}`）与 `ratings.json`（`{"R001": {"leg": "broken"|"minor"|"ok", "note": str, ...}}`），均可缺省
- Produces:
  - `build_cases(layout, benchmark, source, date, ratings=None, key=None) -> list[Case]`：每 (variant, seed) 一个 Case；`images` = 该格 ok 图数；`bad` = 该格 leg 档为 `broken` 的图数（无 ratings 时为 0）；`tags` 留空待填；`feedback` 由该格各图 note 拼接（无则空）
  - `archive_experiment(layout, benchmark, source, out_path, date, ratings_path=None, key_path=None) -> str`：写归档文件，返回路径

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_case_archive.py
import json
import os

from experiments.casebank.case_archive import archive_experiment, build_cases
from experiments.casebank.case_format import parse_cases
from experiments.config import load_benchmark
from experiments.layout import ExpLayout

BENCH = """
characters:
  castorice:
    character_id: mchar_x
    anchors: {anchors}
seeds:
  - {{seed_id: s_easy, character: castorice, difficulty: easy, aspect_ratio: "3:4", text: 种子E}}
  - {{seed_id: s_hard, character: castorice, difficulty: hard, aspect_ratio: "4:3", text: 种子H}}
"""
ANCHORS = "anchors:\n  - {anchor_id: a1, question: q?, ref_slot: face_close}\n"


def _setup(tmp_path):
    root = str(tmp_path)
    anchors_p = os.path.join(root, "anchors.yaml")
    with open(anchors_p, "w", encoding="utf-8") as f:
        f.write(ANCHORS)
    bench_p = os.path.join(root, "bench.yaml")
    with open(bench_p, "w", encoding="utf-8") as f:
        f.write(BENCH.format(anchors=anchors_p.replace("\\", "/")))
    layout = ExpLayout(os.path.join(root, "results"), "exp002")
    # 两变体 × 两种子，每格 2 张
    entries = []
    for variant in ("control", "rulepack"):
        for seed in ("s_easy", "s_hard"):
            pdir = layout.prompts_dir(variant)
            os.makedirs(pdir, exist_ok=True)
            with open(layout.prompt_path(variant, seed), "w", encoding="utf-8") as f:
                f.write(f"{variant}/{seed} 正文\n**Negative Prompt**：穿鞋。")
            for k in (1, 2):
                entries.append({"variant": variant, "seed_id": seed,
                                "image_index": k, "character_id": "mchar_x",
                                "image_path": f"images/{variant}/{seed}/img_{k}.png",
                                "aspect_ratio": "3:4", "ok": True})
    os.makedirs(layout.root, exist_ok=True)
    with open(layout.manifest_path(), "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f)
    return layout, bench_p


def test_build_cases_one_per_variant_seed_cell(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    cases = build_cases(layout, bench, source="exp002", date="2026-07-07")
    assert len(cases) == 4          # 2 变体 × 2 种子
    cell = {(c.variant, c.seed_id) for c in cases}
    assert cell == {("control", "s_easy"), ("control", "s_hard"),
                    ("rulepack", "s_easy"), ("rulepack", "s_hard")}


def test_build_cases_fills_meta_and_prompts(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    cases = build_cases(layout, bench, source="exp002", date="2026-07-07")
    hard = next(c for c in cases if c.variant == "control" and c.seed_id == "s_hard")
    assert hard.images == 2
    assert hard.bad == 0                    # 无 ratings
    assert hard.difficulty == "hard"
    assert hard.seed_prompt == "种子H"
    assert "control/s_hard 正文" in hard.final_prompt
    assert hard.tags == []
    assert hard.feedback == ""


def test_build_cases_counts_bad_from_ratings_and_joins_notes(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    key = {"R001": {"variant": "rulepack", "seed_id": "s_easy", "image_index": 1},
           "R002": {"variant": "rulepack", "seed_id": "s_easy", "image_index": 2}}
    ratings = {"R001": {"leg": "broken", "note": "袜子上色感"},
               "R002": {"leg": "ok", "note": ""}}
    cases = build_cases(layout, bench, source="exp002", date="2026-07-07",
                        ratings=ratings, key=key)
    cell = next(c for c in cases if c.variant == "rulepack" and c.seed_id == "s_easy")
    assert cell.bad == 1
    assert "袜子上色感" in cell.feedback


def test_archive_experiment_writes_parseable_file(tmp_path):
    layout, bench_p = _setup(tmp_path)
    bench = load_benchmark(bench_p)
    out = os.path.join(str(tmp_path), "exp002_cases.txt")
    path = archive_experiment(layout, bench, source="exp002", out_path=out,
                              date="2026-07-07")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        cases = parse_cases(f.read())
    assert len(cases) == 4
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/experiments/test_case_archive.py -v`
Expected: FAIL（`ModuleNotFoundError: experiments.casebank.case_archive`）

- [ ] **Step 3: 写实现**

```python
# experiments/casebank/case_archive.py
"""实验结果 → 结构化 Case 归档。图片不落盘；预填 [meta]+种子+出图 Prompt，
feedback/tags 留空待用户手工填写（设计文档 §2.1、feedback-case-data-first 记忆）。"""
import json
import os

from experiments.casebank.case_format import Case, serialize_cases


def _load_json(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_cases(layout, benchmark, source, date, ratings=None, key=None):
    with open(layout.manifest_path(), "r", encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    seed_by_id = {s.seed_id: s for s in benchmark.seeds}
    char_name = {}
    for name, meta in benchmark.characters.items():
        char_name[str(meta["character_id"])] = name

    # (variant, seed) -> ok 图数
    cell_images = {}
    for e in entries:
        if not e.get("ok"):
            continue
        cell_images.setdefault((e["variant"], e["seed_id"]), 0)
        cell_images[(e["variant"], e["seed_id"])] += 1

    # (variant, seed) -> [bad_count, [notes]]  由盲评 ratings+key 汇总
    cell_bad = {}
    cell_notes = {}
    if ratings and key:
        for rid, ident in key.items():
            r = ratings.get(rid, {})
            ck = (ident["variant"], ident["seed_id"])
            if r.get("leg") == "broken":
                cell_bad[ck] = cell_bad.get(ck, 0) + 1
            note = (r.get("note") or "").strip()
            if note:
                cell_notes.setdefault(ck, []).append(note)

    cases = []
    idx = 0
    for (variant, seed_id), n_img in sorted(cell_images.items()):
        idx += 1
        seed = seed_by_id.get(seed_id)
        with open(layout.prompt_path(variant, seed_id), "r",
                  encoding="utf-8") as f:
            final_prompt = f.read().rstrip("\n")
        ck = (variant, seed_id)
        cases.append(Case(
            case_id=f"Case_{source}_{idx:02d}",
            date=date, source=source,
            character=char_name.get(seed.character_id, "") if seed else "",
            seed_id=seed_id,
            difficulty=seed.difficulty if seed else "",
            variant=variant, images=n_img,
            bad=cell_bad.get(ck, 0), tags=[], taxonomy_version="v1",
            seed_prompt=seed.text if seed else "",
            final_prompt=final_prompt,
            feedback="\n".join(cell_notes.get(ck, [])),
        ))
    return cases


def archive_experiment(layout, benchmark, source, out_path, date,
                       ratings_path=None, key_path=None):
    cases = build_cases(
        layout, benchmark, source=source, date=date,
        ratings=_load_json(ratings_path), key=_load_json(key_path),
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(serialize_cases(cases))
    return out_path
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/experiments/test_case_archive.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add experiments/casebank/case_archive.py tests/experiments/test_case_archive.py
git commit -m "feat(casebank): 实验结果→Case 归档器（预填 meta/种子/出图 Prompt，feedback 待填）"
```

---

## Task 4: 大批量聚合分析器

**Files:**
- Create: `experiments/casebank/case_analyze.py`
- Test: `tests/experiments/test_case_analyze.py`

**Interfaces:**
- Consumes: `Case`（Task 2）、`parse_cases`（Task 2）、`Taxonomy`/`load_taxonomy`（Task 1）
- Produces:
  - `analyze(cases: list[Case], taxonomy: Taxonomy) -> dict`，结构：
    ```
    {
      "by_variant": {variant: {"cells":int,"images":int,"bad":int,"bad_rate":float}},
      "by_difficulty_variant": {difficulty: {variant: {...同上...}}},
      "by_source": {source: {"cells":int,"images":int,"bad":int,"bad_rate":float}},
      "tag_freq": {variant: {normalized_tag: cell_count}},   # 子 tag，按 aliases 归一
      "tag_freq_parent": {variant: {parent_tag: cell_count}},
      "unknown_tags": [ "原样非法 tag", ... ],
    }
    ```
    `bad_rate = sum(bad)/sum(images)`（该组，images 为 0 时值为 `None`）。归一失败的 tag 记入 `unknown_tags` 不计频次。
  - `load_cases_dir(dir_path: str) -> list[Case]`：读目录下全部 `*.txt` 并合并解析
  - `main()`：CLI，`--cases-dir` + `--taxonomy` → 打印 JSON

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_case_analyze.py
import os

from experiments.casebank.case_analyze import analyze, load_cases_dir
from experiments.casebank.case_format import Case, serialize_cases
from experiments.casebank.taxonomy import Taxonomy


def _tx():
    return Taxonomy(
        version="v2",
        tags={"袜子": ["上色感", "皱褶夸张"], "脚部": ["夸张"]},
        aliases={"丝袜/涂色感": "袜子/上色感"},
    )


def _case(variant, seed, difficulty, images, bad, tags):
    return Case(case_id=f"C_{variant}_{seed}", date="2026-07-07", source="exp002",
                character="castorice", seed_id=seed, difficulty=difficulty,
                variant=variant, images=images, bad=bad, tags=tags,
                taxonomy_version="v2", seed_prompt="s", final_prompt="f", feedback="")


def test_by_variant_bad_rate():
    cases = [_case("control", "s1", "hard", 5, 3, []),
             _case("control", "s2", "hard", 5, 2, []),
             _case("rulepack", "s1", "hard", 5, 1, []),
             _case("rulepack", "s2", "hard", 5, 0, [])]
    out = analyze(cases, _tx())
    assert out["by_variant"]["control"]["bad"] == 5
    assert out["by_variant"]["control"]["images"] == 10
    assert out["by_variant"]["control"]["bad_rate"] == 0.5
    assert out["by_variant"]["rulepack"]["bad_rate"] == 0.1


def test_by_difficulty_variant_split():
    cases = [_case("control", "s1", "hard", 4, 2, []),
             _case("control", "s2", "easy", 4, 0, [])]
    out = analyze(cases, _tx())
    assert out["by_difficulty_variant"]["hard"]["control"]["bad_rate"] == 0.5
    assert out["by_difficulty_variant"]["easy"]["control"]["bad_rate"] == 0.0


def test_tag_freq_normalized_child_and_parent():
    cases = [_case("control", "s1", "hard", 5, 3,
                   ["丝袜/涂色感", "袜子/皱褶夸张"]),      # 第一个走 alias 归一
             _case("control", "s2", "hard", 5, 1, ["袜子/上色感"])]
    out = analyze(cases, _tx())
    assert out["tag_freq"]["control"]["袜子/上色感"] == 2
    assert out["tag_freq"]["control"]["袜子/皱褶夸张"] == 1
    assert out["tag_freq_parent"]["control"]["袜子"] == 3   # 2+1 cell 计次


def test_unknown_tag_recorded_not_counted():
    cases = [_case("control", "s1", "hard", 5, 3, ["袜子/查无此项"])]
    out = analyze(cases, _tx())
    assert "袜子/查无此项" in out["unknown_tags"]
    assert out["tag_freq"].get("control", {}) == {}


def test_zero_images_bad_rate_none():
    cases = [_case("control", "s1", "hard", 0, 0, [])]
    out = analyze(cases, _tx())
    assert out["by_variant"]["control"]["bad_rate"] is None


def test_by_source_group():
    c1 = _case("control", "s1", "hard", 5, 2, [])
    c2 = _case("control", "s2", "hard", 5, 1, [])
    c2.source = "production"
    out = analyze([c1, c2], _tx())
    assert out["by_source"]["exp002"]["bad_rate"] == 0.4
    assert out["by_source"]["production"]["bad_rate"] == 0.2


def test_load_cases_dir_merges_files(tmp_path):
    d = str(tmp_path)
    with open(os.path.join(d, "a.txt"), "w", encoding="utf-8") as f:
        f.write(serialize_cases([_case("control", "s1", "hard", 5, 1, [])]))
    with open(os.path.join(d, "b.txt"), "w", encoding="utf-8") as f:
        f.write(serialize_cases([_case("rulepack", "s1", "hard", 5, 0, [])]))
    cases = load_cases_dir(d)
    assert {c.variant for c in cases} == {"control", "rulepack"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/experiments/test_case_analyze.py -v`
Expected: FAIL（`ModuleNotFoundError: experiments.casebank.case_analyze`）

- [ ] **Step 3: 写实现**

```python
# experiments/casebank/case_analyze.py
"""大批量 Case 聚合分析：崩坏率按 变体/难度 交叉统计 + tag 频次（按 taxonomy 归一）。
Case 量增长后靠结构化 tags 保持准确；自由文本 feedback 不参与自动统计。"""
import argparse
import glob
import json
import os

from experiments.casebank.case_format import parse_cases
from experiments.casebank.taxonomy import load_taxonomy


def _rate(images, bad):
    return round(bad / images, 4) if images else None


def _group(cases):
    cells = len(cases)
    images = sum(c.images for c in cases)
    bad = sum(c.bad for c in cases)
    return {"cells": cells, "images": images, "bad": bad,
            "bad_rate": _rate(images, bad)}


def analyze(cases, taxonomy):
    by_variant_cases, by_dv, by_src = {}, {}, {}
    for c in cases:
        by_variant_cases.setdefault(c.variant, []).append(c)
        by_dv.setdefault(c.difficulty, {}).setdefault(c.variant, []).append(c)
        by_src.setdefault(c.source, []).append(c)

    by_variant = {v: _group(cs) for v, cs in by_variant_cases.items()}
    by_difficulty_variant = {
        diff: {v: _group(cs) for v, cs in variants.items()}
        for diff, variants in by_dv.items()
    }
    by_source = {s: _group(cs) for s, cs in by_src.items()}

    tag_freq, tag_freq_parent, unknown = {}, {}, []
    for c in cases:
        for tag in c.tags:
            try:
                norm = taxonomy.normalize(tag)
            except ValueError:
                unknown.append(tag)
                continue
            parent = norm.split("/")[0]
            tag_freq.setdefault(c.variant, {})
            tag_freq[c.variant][norm] = tag_freq[c.variant].get(norm, 0) + 1
            tag_freq_parent.setdefault(c.variant, {})
            tag_freq_parent[c.variant][parent] = \
                tag_freq_parent[c.variant].get(parent, 0) + 1

    return {"by_variant": by_variant,
            "by_difficulty_variant": by_difficulty_variant,
            "by_source": by_source,
            "tag_freq": tag_freq, "tag_freq_parent": tag_freq_parent,
            "unknown_tags": unknown}


def load_cases_dir(dir_path):
    cases = []
    for p in sorted(glob.glob(os.path.join(dir_path, "*.txt"))):
        with open(p, "r", encoding="utf-8") as f:
            cases.extend(parse_cases(f.read()))
    return cases


def main():
    ap = argparse.ArgumentParser(description="Case 聚合分析")
    ap.add_argument("--cases-dir", required=True)
    ap.add_argument("--taxonomy", default="experiments/cases/taxonomy.yaml")
    args = ap.parse_args()
    cases = load_cases_dir(args.cases_dir)
    tx = load_taxonomy(args.taxonomy)
    print(json.dumps(analyze(cases, tx), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/experiments/test_case_analyze.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add experiments/casebank/case_analyze.py tests/experiments/test_case_analyze.py
git commit -m "feat(casebank): 大批量 Case 聚合分析器（崩坏率交叉统计 + tag 归一频次）"
```

---

## Task 5: exp002 高危基准集 benchmark_v2 与实验配置

**Files:**
- Create: `experiments/fixtures/benchmark_v2.yaml`
- Create: `experiments/configs/exp002.yaml`
- Test: `tests/experiments/test_benchmark_v2.py`

**Interfaces:**
- Consumes: `experiments.config.load_benchmark`（校验 seed 引用/去重）、`load_experiment_config`（校验字段/并发上限/变体数）
- Produces: 无 Python 接口；产出经校验的数据文件，供 runbook 生成两变体使用。种子文本为草案，**用户审定后冻结**。

> 说明：benchmark_v2 复用 v1 的 medium/hard 种子文本（盘腿/鸭子坐/高背椅伸展），另加 5 个从 bad cases 归纳的丝袜高危场景（仅场景+姿势的种子级描述，**不抄 bad case 的 final_prompt**）。两角色 castorice / hysilens。aspect_ratio 沿 benchmark 冻结惯例预填、生成时 runner 跟随各自决策块。

- [ ] **Step 1: 写 benchmark_v2.yaml**

```yaml
# 基准集 v2（exp002 腿脚高危侧重）。种子 Claude 起草、用户审定后冻结。
# 复用 v1 的 medium/hard 种子；新增 5 个丝袜高危场景（种子级，非 bad case 原文）。
# aspect_ratio 预填惯例值；出图时 runner 跟随各变体 step1 决策块。
characters:
  castorice:
    character_id: mchar_3695c70ca7
    anchors: experiments/fixtures/anchors/castorice.yaml
  hysilens:
    character_id: mchar_50c51e6e37
    anchors: experiments/fixtures/anchors/hysilens.yaml

seeds:
  # —— 复用 v1 medium/hard ——
  - seed_id: cas_med_squat
    character: castorice
    difficulty: medium
    aspect_ratio: "3:4"
    text: 角色乖巧地蹲在满是阳光的玄关处，穿着简单的居家白裙，嘴角挂着若有似无的浅笑。她褪去一半左手的黑色长手套，正用指尖试探性地温柔抚摸着一只趴在鞋柜上的毛绒白猫，展现出极致的信任感。
  - seed_id: cas_hard_wsit
    character: castorice
    difficulty: hard
    aspect_ratio: "4:3"
    text: 阳光明媚的客厅里，角色穿着宽大的浅紫色针织衫鸭子坐在地毯上，正用裸露的右手小心翼翼地半褪下左手的黑色长手套。她紫色的眼眸温柔地注视着镜头，头顶的黑荆棘花冠与现代家居形成奇妙的反差萌。
  - seed_id: hys_med_crossleg
    character: hysilens
    difficulty: medium
    aspect_ratio: "4:3"
    text: 在放着深色抱枕的水光榻榻米上，角色双腿交叠盘腿坐着，双手捧着红色的玻璃杯，微微出神。榻榻米表面折射出梦幻般斑驳的水波焦散光斑。
  - seed_id: hys_hard_bubble
    character: hysilens
    difficulty: hard
    aspect_ratio: "16:9"
    text: 低饱和灰蓝色调的古典居家画室中，角色慵懒而端庄地侧坐在铺有深海蓝天鹅绒坐垫的古典高背椅上，双手捧着吹泡泡细管置于唇边认真轻吹。一条腿曲起折叠在坐垫上，另一条腿从椅缘向斜下方自然伸展、足尖轻触木地板。夕阳碎光透过百叶窗洒入，空气中漂浮着数个肥皂泡。
  # —— 新增丝袜高危场景（种子级，源自 bad cases 的问题模式）——
  - seed_id: cas_hard_kneel_sock
    character: castorice
    difficulty: hard
    aspect_ratio: "3:4"
    text: 深夜私密卧室的木地板上，角色双膝并拢安静跪坐，脚背放松地贴平地面，裸露的右手抱着一只毛绒玩偶到胸前，左手黑色长手套半脱至腕部。她穿着浅紫色吊带睡裙，双腿裹着白色大腿袜。
  - seed_id: cas_med_floorsit_sheer
    character: castorice
    difficulty: medium
    aspect_ratio: "3:4"
    text: 暖黄香薰灯光照亮床边木地板，角色斜坐在地板上，一条腿向前自然平放伸直，另一条腿在身侧微屈。她身穿轻薄淡紫色吊带睡裙，双腿穿着薄透白色大腿袜，怀里抱着一只毛绒小熊。
  - seed_id: cas_hard_hugknee_bed
    character: castorice
    difficulty: hard
    aspect_ratio: "3:4"
    text: 幽暗静谧的卧室大床上，角色背靠床头软枕斜坐，双腿并拢折起、穿着袜子的双脚平稳踩在床单上，双手轻轻环抱膝盖。她身穿白色真丝吊带睡裙，双腿裹着淡紫色半透明大腿袜。
  - seed_id: hys_med_recline_sock
    character: hysilens
    difficulty: medium
    aspect_ratio: "16:9"
    text: 客厅低矮沙发上，角色穿着真丝吊带裙慵懒斜倚在松软靠枕间，双腿交叠向一侧自然伸展，脚背舒展。双腿穿着薄透白色大腿袜，一侧苍白肩膀从松垮开衫中滑落。
  - seed_id: cas_easy_sock_stand
    character: castorice
    difficulty: easy
    aspect_ratio: "3:4"
    text: 清晨冷光洒进简约北欧风起居室，角色安静地站在浅灰木地板上，身体微微侧向镜头，重心落在一条腿上，另一条腿自然放松。她穿着居家长裙，双脚穿着薄透短袜。
```

- [ ] **Step 2: 写 exp002.yaml 配置**

```yaml
# exp002：腿脚规则包 A/B（control=现生产链路，rulepack=规则包链路）。
# 每格 5 张、9 种子、2 变体 = 90 张/轮。concurrency 受 config MAX_CONCURRENCY=10 约束。
exp_id: exp002
benchmark: experiments/fixtures/benchmark_v2.yaml
variants: [control, rulepack]
images_per_cell: 5
concurrency: 6
review_shuffle_seed: 20260707
```

- [ ] **Step 3: 写校验测试**

```python
# tests/experiments/test_benchmark_v2.py
from experiments.config import load_benchmark, load_experiment_config

BENCH = "experiments/fixtures/benchmark_v2.yaml"
CFG = "experiments/configs/exp002.yaml"


def test_benchmark_v2_loads_and_validates():
    bench = load_benchmark(BENCH)
    assert len(bench.seeds) == 9
    assert {"castorice", "hysilens"} <= set(bench.characters)


def test_benchmark_v2_covers_difficulty_gradient():
    bench = load_benchmark(BENCH)
    diffs = {s.difficulty for s in bench.seeds}
    assert {"easy", "medium", "hard"} <= diffs


def test_benchmark_v2_high_risk_sock_seeds_present():
    bench = load_benchmark(BENCH)
    ids = {s.seed_id for s in bench.seeds}
    for sid in ("cas_hard_kneel_sock", "cas_med_floorsit_sheer",
                "cas_hard_hugknee_bed", "hys_med_recline_sock",
                "cas_easy_sock_stand"):
        assert sid in ids


def test_exp002_config_loads():
    cfg = load_experiment_config(CFG)
    assert cfg.exp_id == "exp002"
    assert cfg.variants == ["control", "rulepack"]
    assert cfg.images_per_cell == 5
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/experiments/test_benchmark_v2.py -v`
Expected: PASS（4 passed）。若 FAIL 于 seed 数不符，核对 benchmark_v2.yaml 种子条目。

- [ ] **Step 5: 提交**

```bash
git add experiments/fixtures/benchmark_v2.yaml experiments/configs/exp002.yaml tests/experiments/test_benchmark_v2.py
git commit -m "feat(exp002): benchmark_v2 腿脚高危基准集 + exp002 实验配置"
```

---

## Task 6: 腿脚规则包（生产模板增量编辑 + 结构断言）

**Files:**
- Modify: `app/prompts/creation/prompt_precreation.py`（`prompt_step1` 内 §5 腿脚设计目标段，约 33-39 行）
- Modify: `app/prompts/creation/prompt_template.py`（`init_template` 的「角色脚部/袜子细节」「Negative Prompt」字段说明；`good_template1` 的腿脚/袜子/Negative 示范）
- Test: `tests/services/test_rulepack_template_structure.py`

**Interfaces:**
- Consumes: 现有 `prompt_step1`、`init_template`、`good_template1`、`prompt_step2`（不改 step2 逻辑，仅可能补 Negative 提示）
- Produces: 无新函数；模板文本携带 R1-R6 规则。结构测试保证规则在位且不破坏 slim 骨架。

> 规则包意图（设计文档 §3）落为具体措辞：
> - **R1 材质词黑白名单**：腿脚/袜子段禁用「折射/珠光/透光率/微孔织物/丝线密度/次表面散射/莹润」等光学-材料学词，改用「轻盈/柔和光泽/服帖/朦胧」等感性词。
> - **R2 袜口结构锚定必选**：出现袜子必写一个结构特征（蕾丝袜口/罗纹袜口/缎带）。
> - **R3 脚趾防护标配**：正文写「足尖在袜面包裹下轮廓圆润柔和」，Negative 标配「裸露脚趾、脚趾根根分明」。
> - **R4 褶皱单处克制**：至多一处褶皱、禁程度词「细密/明显/夸张厚度」。
> - **R5 高难姿势退让**：step1 姿势指引规避「深度折叠/肢体多重交叠」，改同场景舒展变体；腿脚展示量不减。
> - **R6 Negative 腿脚位保底**：5 条限额内腿脚相关条目（多肢/脚趾/袜子缺失）优先占位。

- [ ] **Step 1: 写失败测试（先固化规则断言）**

```python
# tests/services/test_rulepack_template_structure.py
"""exp002 腿脚规则包结构断言：保证 R1-R6 在生产模板就位，且不破坏 slim 骨架。"""
from app.prompts.creation.prompt_precreation import prompt_step1
from app.prompts.creation.prompt_template import good_template1, init_template
from app.services.creation_service.prompt_precreation_service import _build_step1_prompt


class TestRulePackStep1:
    def _p(self):
        return _build_step1_prompt(chara_profile="档案", seed_prompt="种子")

    def test_r1_material_word_blacklist_declared(self):
        # 黑名单词与感性白名单指引同时出现在 step1 腿脚设计段
        assert "次表面散射" in prompt_step1
        assert "珠光" in prompt_step1 or "折射" in prompt_step1
        assert "感性" in prompt_step1 or "轻盈" in prompt_step1

    def test_r3_toe_protection_guidance(self):
        assert "脚趾根根分明" in prompt_step1
        assert "圆润" in prompt_step1 or "弱化脚趾" in prompt_step1

    def test_r4_single_wrinkle_restraint(self):
        assert "褶皱" in prompt_step1
        assert "一处" in prompt_step1 or "至多" in prompt_step1

    def test_r5_extreme_pose_backoff_but_keeps_exposure(self):
        assert "深度折叠" in prompt_step1 or "多重交叠" in prompt_step1
        # 第一原则护栏：退让措辞不得删掉腿脚展示要求
        assert "自然展示腿部与脚部，但不低俗" in prompt_step1

    def test_slim_leg_foot_guidance_still_present(self):
        # slim 基准不动摇：原腿脚设计目标未被删
        assert "不要写实化或包含过度的解剖细节" in prompt_step1


class TestRulePackGoodTemplate:
    def test_r2_sock_cuff_structure_anchor(self):
        # 范例袜口带结构特征（蕾丝/罗纹/缎带其一）
        assert any(k in good_template1 for k in ("蕾丝", "罗纹", "缎带"))

    def test_r3_toe_rounded_phrasing_in_exemplar(self):
        assert "圆润" in good_template1 or "轮廓柔和" in good_template1

    def test_r1_no_physics_material_words_in_good_template(self):
        for w in ("次表面散射", "透光率", "微孔织物", "折射率"):
            assert w not in good_template1

    def test_r6_negative_reserves_leg_foot_slots(self):
        neg = good_template1.split("**Negative Prompt**")[1]
        assert "脚趾" in neg or "多肢" in neg or "多余的手指" in neg
        # slim 上限不破：仍 ≤5 条
        assert len([p for p in neg.replace("：", "").split("、") if p.strip()]) <= 5

    def test_good_template_keeps_slim_skeleton(self):
        for field in ("**角色脚部/袜子细节**", "**Negative Prompt**",
                      "**光影", "**材质与质感"):
            assert field in good_template1


class TestRulePackInitTemplate:
    def test_sock_field_hint_mentions_structure_and_toe(self):
        seg = init_template.split("**角色脚部/袜子细节**")[1].split("**角色神态**")[0]
        assert "袜口" in seg or "蕾丝" in seg or "罗纹" in seg
        assert "脚趾" in seg

    def test_negative_field_hint_reserves_leg_foot(self):
        seg = init_template.split("**Negative Prompt**")[1]
        assert "脚趾" in seg or "腿脚" in seg
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/services/test_rulepack_template_structure.py -v`
Expected: FAIL（多条 assert 未命中，规则尚未写入模板）

- [ ] **Step 3: 编辑 `prompt_step1` 腿脚设计段（R1/R3/R4/R5）**

在 `app/prompts/creation/prompt_precreation.py` 中，把现有第 5 条腿脚设计目标段（"5、角色的脚部和袜子细节是高价值元素…"到"…通过前脚掌与袜面起伏暗示结构。"及其后"注意事项"）替换为下面加强版（保留原 slim 指引，叠加 R1/R3/R4/R5）：

```python
# 替换 prompt_step1 中第 5 条腿脚设计目标 + 注意事项两段为：
"""5、角色的脚部和袜子细节是高价值元素，在“角色脚部/袜子细节”字段中增加适量的补充描述。
设计目标：
- 脚部：结构自然、准确，轮廓细腻，不要写实化或包含过度的解剖细节，保持柔和细腻的二次元高级质感；足尖在袜面包裹下呈现圆润柔和的轮廓，弱化脚趾轮廓，严禁脚趾根根分明；
- 袜子：体现自然的视觉质感、轻微贴合感，自然包裹脚掌，弱化脚趾轮廓，不强调脚趾分离。保持二次元角色特有的柔软与轻盈感。对于丝袜类袜子，可以自然表现脚趾与前脚掌在袜面下的轻微体积暗示；对于非丝质袜子（如棉袜等），则以轮廓体积和织物纹理为主。
- 袜口结构锚定：凡出现袜子，必须写明一个具体的袜口结构特征（如蕾丝花边袜口 / 细罗纹袜口 / 缎带装饰其一），给模型“这是一件织物”的结构锚，避免被画成脚上涂色。
材质用词规范（重要）：
- 腿脚与袜子的材质描述改用**感性、克制**的词（轻盈、柔和光泽、服帖、朦胧、干净）；
- **禁用光学-材料学词汇**：折射、折射率、珠光、透光率、次表面散射、微孔织物、丝线密度等——这类写实渲染词会把画面推向塑料/写实质感，导致“塑料袋感”与画风崩坏。
褶皱规范：袜子褶皱至多描述**一处**（如脚踝处少许自然堆叠），禁止“细密 / 明显 / 夸张厚度”等程度词与多处褶皱堆砌。
注意事项：
- 避免厚羊毛袜、毛线袜、绒毛袜、罗纹厚袜、针织厚袜等冬季厚袜，不要臃肿感/厚重感/毛茸茸感；
- 丝袜类袜子的选型推荐：轻薄顺滑、轻微柔和光泽、袜面干净细腻，带精致蕾丝袜口或淡雅装饰边；
- 非丝袜类袜子（如棉袜等）的选型推荐：夏季轻薄款，材质平滑、轻盈、柔软、表面哑光，贴合但不过分紧绷，带小巧蕾丝/罗纹袜口。
6、不要修改其他上面没有提到的字段。"""
```

同时，在 `prompt_step1` 的姿势相关说明（"任务步骤"第 2 步"角色的位置与姿势"处，或"模版填写说明"处）补入 R5 退让指引。定位到 `prompt_step1` 中 "2、描述该画面中的核心场景要素：…角色的位置与姿势（自然展示腿部与脚部，但不低俗）；" 一行，替换为：

```python
# 替换该行为（叠加 R5，保留第一原则原文）：
"2、描述该画面中的核心场景要素：房间的风格与布局、核心家具（例如床、沙发、椅子等）、角色的位置与姿势（自然展示腿部与脚部，但不低俗）；姿势优先选择自然舒展的坐/倚/跪/蹲，避免深度折叠（如抱膝深折使小腿完全压叠）与肢体多重交叠的极端姿势——这类姿势易导致腿部结构与比例崩坏。退让时保持腿脚的自然展示量不变，仅降低姿势的折叠极端度；"
```

- [ ] **Step 4: 编辑 `init_template` 字段说明（R2/R3/R6）**

在 `app/prompts/creation/prompt_template.py` 中，替换 `init_template` 的「角色脚部/袜子细节」与「Negative Prompt」两行字段说明：

```python
# 「角色脚部/袜子细节」字段说明替换为：
"**角色脚部/袜子细节**：（根据角色的袜子样式设计，增加2-3句角色腿/脚部及袜子的相关细节。必须写明一个袜口结构特征（蕾丝/罗纹/缎带其一）；足尖在袜面下轮廓圆润柔和、弱化脚趾、严禁脚趾根根分明；袜子褶皱至多一处、不用“细密/明显/夸张厚度”等程度词；材质用感性词，禁用折射/珠光/透光率/次表面散射等光学-材料学词）\n"
```

```python
# 「Negative Prompt」字段说明替换为（叠加 R6 腿脚位保底）：
"**Negative Prompt**：（step1 先填 1-3 条高危项，step2 补足，最终合计 3-5 条高危名词短语，用“、”分隔。腿脚相关高危项（多肢 / 脚趾根根分明 / 裸露脚趾 / 袜子缺失）在限额内优先占位。正文已正向声明的内容禁止写入；禁止 (word:1.3) 权重语法；不要包含模型几乎不可能犯的低级错误）\n"
```

- [ ] **Step 5: 编辑 `good_template1` 腿脚示范（R1/R2/R3/R4/R6）**

在 `app/prompts/creation/prompt_template.py` 中，`good_template1` 的「角色脚部/袜子细节」「材质与质感」「Negative Prompt」三处已基本合规（袜口有蕾丝、有圆润），仅需微调确保 R3 圆润措辞显式、R6 Negative 含脚趾项。替换这两行：

```python
# 「角色脚部/袜子细节」行替换为（R3 显式圆润 + R2 蕾丝袜口 + R4 单处褶皱）：
"**角色脚部/袜子细节**：淡紫色薄纱短袜，轻盈柔和，服帖包裹足部，微透出皮肤的淡粉色。袜口有极窄的蕾丝花边，松松贴合脚踝，仅脚踝处少许自然褶皱。足尖在袜面包裹下轮廓圆润柔和，脚跟因蹲姿略微抬起。\n"
```

```python
# 「Negative Prompt」行替换为（R6 腿脚位保底，仍 ≤5 条）：
"**Negative Prompt**：穿鞋、脚趾根根分明、多余的手指、面部五官变形、画风割裂。\n"
```

- [ ] **Step 6: 运行结构测试确认通过**

Run: `pytest tests/services/test_rulepack_template_structure.py -v`
Expected: PASS（12 passed）

- [ ] **Step 7: 运行 slim 回归测试确认未破坏基准**

Run: `pytest tests/services/test_slim_template_structure.py -v`
Expected: PASS（全部通过；若 `test_negative_is_short_noun_list` 或 `test_leg_foot_exposure_preserved` 失败，说明规则包破坏了 slim 骨架，需回退措辞）

- [ ] **Step 8: 提交**

```bash
git add app/prompts/creation/prompt_precreation.py app/prompts/creation/prompt_template.py tests/services/test_rulepack_template_structure.py
git commit -m "feat(exp002): 腿脚规则包 R1-R6 落入生产模板（材质词黑白名单/袜口锚定/脚趾防护/褶皱克制/姿势退让/Negative 保底）"
```

---

## Task 7: exp002 运行手册

**Files:**
- Create: `docs/superpowers/specs/2026-07-07-exp002-runbook.md`

**Interfaces:**
- Consumes: 前 6 个任务的全部产物（baseline_gen、runner、report、casebank 四模块、benchmark_v2、exp002.yaml、规则包 commit）
- Produces: 操作手册；无 Python 接口。其"测试"为按手册走查每步命令与判定标准自洽（评审验证）。

> 关键约束记录在手册内：control 变体须用**规则包 commit 之前**的模板生成，rulepack 变体用规则包 commit 之后的模板生成；baseline_gen 在运行时读取 `app/prompts/creation/*`，故用 git 切换模板状态分两次生成（沿用 exp001b 的目录改名手法）。

- [ ] **Step 1: 写运行手册**

写入 `docs/superpowers/specs/2026-07-07-exp002-runbook.md`，内容如下：

````markdown
# exp002 运行手册：腿脚规则包 A/B（control vs rulepack）

> 前置：Task 1-6 已合入。规则包 commit 记为 `<RULEPACK_SHA>`（Task 6 的提交）。
> 目的：验证腿脚规则包能否显著压低腿脚崩坏率（基线：exp001 slim 组 ~22%），且脸部/构图/画风不回退。

## 1. 生成两变体 Prompt（生产链路，分两次切模板）

control = 规则包之前的模板；rulepack = 规则包之后的模板。baseline_gen 运行时读取
`app/prompts/creation/*`，因此用 git 切换模板状态。

```bash
# rulepack（当前 HEAD 已含规则包）
python -m experiments.baseline_gen --config experiments/configs/exp002.yaml
mv experiments/variants/exp002/baseline experiments/variants/exp002/rulepack

# control（回到规则包之前的模板状态）
git stash            # 若有未提交改动
git checkout <RULEPACK_SHA>~1 -- app/prompts/creation/
python -m experiments.baseline_gen --config experiments/configs/exp002.yaml
mv experiments/variants/exp002/baseline experiments/variants/exp002/control
git checkout HEAD -- app/prompts/creation/   # 恢复规则包模板
```

冻结语义：baseline_gen 对已存在文件跳过；两变体各 9 份，合计 18 份 Prompt。

## 2. 出图前规则遵从抽查（rulepack 变体，出图门槛）

逐份检查 rulepack 的 9 份 Prompt：

- [ ] 腿脚/袜子段无光学-材料学词（折射/珠光/透光率/次表面散射/微孔织物）
- [ ] 每份袜子描述含一个袜口结构特征（蕾丝/罗纹/缎带）
- [ ] 正文有足尖圆润/弱化脚趾措辞；Negative 含「脚趾根根分明」或「裸露脚趾」
- [ ] 袜子褶皱至多一处、无「细密/明显/夸张厚度」程度词
- [ ] 高难种子姿势未出现深度折叠/多重交叠，且腿脚仍自然展示
- [ ] Negative 合计 3-5 条、无权重语法、与正文无正负矛盾

系统性不达标 → 回到规则包措辞迭代（模板遵从性问题），不进入出图。

## 3. 出图

```bash
python -m experiments.runner --config experiments/configs/exp002.yaml
```

runner 发送前自动剥离决策块、画幅跟随各变体决策块（`resolve_send_inputs`）。
每变体 9 种子 × 5 张 = 45 张，合计 90 张。

## 4. 盲评（单遍，评完即归档）

```bash
python -m experiments.report review --config experiments/configs/exp002.yaml
```

打开 `experiments/results/exp002/review.html`，逐图对 脸部/锚点/腿脚袜 三组打分，
并在 note 里填该图的具体问题（自由文本）。导出 `ratings.json`。
盲评页图片乱序匿名，变体不可见——保持盲评有效。

## 5. 归档为结构化 Case（揭盲后）

```bash
python -m experiments.report metrics --config experiments/configs/exp002.yaml   # 可选：自动指标
python -c "from experiments.config import load_benchmark; \
from experiments.layout import ExpLayout; \
from experiments.casebank.case_archive import archive_experiment; \
lay=ExpLayout('experiments/results','exp002'); \
bench=load_benchmark('experiments/fixtures/benchmark_v2.yaml'); \
archive_experiment(lay, bench, source='exp002', \
  out_path='experiments/cases/exp002/exp002_cases.txt', date='2026-07-07', \
  ratings_path='experiments/results/exp002/ratings.json', \
  key_path='experiments/results/exp002/review_key.json')"
```

产出 `experiments/cases/exp002/exp002_cases.txt`：每 (变体, 种子) 一个 Case，
`[meta]` 预填、`bad` 由 leg=broken 计数、`feedback` 由 note 拼接。
逐 Case 复核 feedback，并按 `experiments/cases/taxonomy.yaml` 填 `tags`
（子 tag 覆盖不了的问题 → 提议新子 tag，用户确认后 bump taxonomy version）。

## 6. 聚合分析与判定

```bash
python -m experiments.casebank.case_analyze --cases-dir experiments/cases/exp002
```

看 `by_variant` / `by_difficulty_variant` 的 `bad_rate`（腿脚崩坏率）与
`tag_freq_parent`（残余崩坏模式分布）。

判定（设计文档 §4）：
- 主指标：rulepack 腿脚崩坏率相对 control 显著下降（且相对 ~22% 基线改善）。
- 护栏：脸部/构图/画风不回退（画风崩坏纳入 tags 统计）。
- 判定框架沿用 exp001：区分「模板遵从性问题」（LLM 没照做 → 迭代措辞重跑）
  与「规则本身问题」（自动链路下有副作用 → 回退该条规则）。
- 无效或回退：`git revert <RULEPACK_SHA>` 撤下规则包，保留 Case 数据供后续分析。

## 7. 后续（B/C 辅助，满足触发条件才做）

- B 单规则消融：某类崩坏未改善 → 对应规则单独变体小规模消融。
- C 链路手段：Prompt 层到平台期 → 崩坏检测自动重 roll、腿脚特写参考图注入。
````

- [ ] **Step 2: 校验手册内引用的命令/路径与代码一致**

逐条核对：`experiments/baseline_gen.py` 输出目录 `experiments/variants/exp002/baseline`（`baseline_gen.py:56`）；`report review`/`metrics` 子命令存在（`report.py:227`）；`archive_experiment` 签名（Task 3）；`case_analyze` CLI `--cases-dir`（Task 4）。发现不符即修手册。

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/specs/2026-07-07-exp002-runbook.md
git commit -m "docs(exp002): 运行手册（切模板生成两变体→盲评→Case 归档→聚合分析→判定）"
```

---

## 执行顺序与依赖

Task 1 → 2 → 3 → 4 为闭环基建，严格顺序（3 依赖 1/2，4 依赖 1/2）。Task 5、6 相互独立、可在 1-4 之后任意序。Task 7 依赖全部前置。Part A（1-4）可独立合入并立即产生价值；Part B（5-7）构成 exp002 的可执行资产，规则包（Task 6）合入即等待 exp002 揭盲定夺去留。
