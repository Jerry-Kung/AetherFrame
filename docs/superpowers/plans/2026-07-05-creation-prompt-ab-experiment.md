# 创作模块出图质量 A/B 实验体系 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 `experiments/` 命令行实验层（运行器 + 新核对节点 + 报告/盲评工具），支撑 exp001「Prompt 瘦身 6 规则」A/B 对照实验。

**Architecture:** 纯后端脚本层，与 `app/` 并列、复用 `app.tools.llm` 与 `app.services` 的既有函数，不动前端与 DB 任务流。代码/配置/fixtures 进 git（生产环境 git 同步后运行），`experiments/results/` 整目录 gitignore（打包拷回本地评判）。所有 LLM/图片调用通过 `ThreadPoolExecutor` 限并发 ≤ 10。

**Tech Stack:** Python 3.14 / PyYAML（本地 6.0.3 已装，需加入 requirements.txt）/ pytest / 既有 `yibu_gemini_infer`（文本+多模态）与 `generate_image_with_nano_banana_pro`。

**Spec:** `docs/superpowers/specs/2026-07-05-creation-prompt-ab-experiment-design.md`

## Global Constraints

- 并发硬上限 **≤ 10**，独立于生产 `task_concurrency`，配置项 `concurrency` 默认 10。
- `experiments/results/` 必须 gitignore；`experiments/` 其余全部进 git。
- **.gitignore 第 11 行有 `test*` 模式**：tests/ 下新建测试文件必须 `git add -f` 才能入库（既有测试就是这么加的）。
- 运行环境为生产 Linux + 本地 Windows 双端：路径一律 `os.path.join`，文件读写显式 `encoding="utf-8"`。
- 入口统一 `python -m experiments.<module>`，从仓库根运行（保证 `app.*` 可导入；`app/tools/llm/config.py` 生产已存在）。
- 复用函数签名（本计划各任务直接引用，不得重新实现）：
  - `yibu_gemini_infer(prompt, image_path: list[str]|None = None, model="gemini-3.1-pro-preview", system_instruction=..., temperature=0.5, top_p=1.0, thinking_level="medium", host=..., timeout=300) -> str`（`app/tools/llm/yibu_llm_infer.py`；image_path 最多 5 张，失败抛异常）
  - `generate_image_with_nano_banana_pro(Content, output_path: str, file_name: str, aspect_ratio: str = "16:9", timeout: int = 2700) -> bool`（`app/tools/llm/nano_banana_pro.py`；Content 为 `[{"text": ...}, {"picture": 本地路径}, ...]`）
  - `read_chara_profile_markdown(character_id, "chara_profile_final.md") -> Optional[str]`、`standard_reference_paths_for_multimodal_prompt(character_id) -> Optional[List[str]]`、`get_standard_slot_image_path(character_id, shot_type) -> Optional[str]`（`app/services/material_service/material_file_service.py`）
  - `_build_step1_prompt(*, chara_profile, seed_prompt) -> str`、`_parse_step1_composition(step1_output) -> Dict[str, str]`、`prompt_step2.format(init_template=step1_result, good_template=good_template1, chara_profile=..., seed_prompt=...)`（`app/services/creation_service/prompt_precreation_service.py` 与 `app/prompts/creation/`）
- 测试不打真实 API：所有涉及 LLM/图片调用的测试用 `monkeypatch` 替换推理函数。
- 提交信息风格与仓库一致（中文、`feat(experiments): ...` / `test: ...`）。

## 文件结构总览

```
experiments/
├── __init__.py
├── config.py            # ExperimentConfig / Benchmark 加载与校验（Task 1/2）
├── layout.py            # results 目录布局唯一事实源（Task 1）
├── baseline_gen.py      # 基线 Prompt 生成冻结 CLI（Task 8）
├── runner.py            # 出图执行器 CLI（Task 9）
├── report.py            # 指标聚合 + review.html + 合流报告 CLI（Task 10/11）
├── configs/
│   └── exp001.yaml
├── fixtures/
│   ├── benchmark_v1.yaml         # 角色 + 6 种子 + 每种子 aspect_ratio
│   └── anchors/
│       ├── castorice.yaml        # 锚点核对清单（用户审定后冻结）
│       └── hysilens.yaml
├── variants/
│   └── exp001/
│       ├── baseline/<seed_id>.txt   # 冻结基线（Task 8 产出）
│       └── slim/<seed_id>.txt       # 瘦身版（离线人工改写，执行阶段产出）
├── checker/
│   ├── __init__.py
│   ├── parsers.py        # LLM 应答解析纯函数（Task 3）
│   ├── checks.py         # 4 结构检查 + 锚点核对封装（Task 4）
│   ├── run_checks.py     # 逐图全量核对 CLI（Task 5）
│   └── calibrate.py      # 校准集验证 CLI（Task 6）
└── results/              # gitignored
    └── exp001/
        ├── prompts/<variant>/<seed_id>.txt      # 实际发送全文存档
        ├── images/<variant>/<seed_id>/img_<k>.png
        ├── checks/<variant>__<seed_id>__img_<k>.json
        ├── manifest.json                        # 每张图的生成记录
        ├── metrics.json / review.html / final_report.md
tests/experiments/        # 全部 git add -f
```

自动指标口径（report 聚合 checks JSON）：锚点保留率、多腿率、躯干重复率、颈腰扭曲率、背景崩坏率。主观项（脸/腿脚审美）只走 review.html 人工盲评。

---

### Task 1: experiments 包骨架 + 配置加载 + 目录布局

**Files:**
- Create: `experiments/__init__.py`（空文件）
- Create: `experiments/config.py`
- Create: `experiments/layout.py`
- Create: `experiments/checker/__init__.py`（空文件）
- Create: `tests/experiments/__init__.py`（空文件）
- Test: `tests/experiments/test_config.py`
- Modify: `.gitignore`（追加 results 忽略）
- Modify: `requirements.txt`（追加 pyyaml）

**Interfaces:**
- Produces: `load_experiment_config(path: str) -> ExperimentConfig`，字段：`exp_id: str, benchmark: str（fixtures yaml 相对仓库根路径）, variants: list[str], images_per_cell: int, concurrency: int, review_shuffle_seed: int`
- Produces: `ExpLayout(results_root: str, exp_id: str)`，方法：`prompts_dir(variant)`, `image_dir(variant, seed_id)`, `image_path(variant, seed_id, k)`, `check_path(variant, seed_id, k)`, `manifest_path()`, `metrics_path()`, `review_html_path()`, `final_report_path()`（全部返回 str 绝对/相对拼接路径，命名规则见下方实现）

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_config.py
import os
import pytest

from experiments.config import ExperimentConfig, load_experiment_config
from experiments.layout import ExpLayout


def _write(tmp_path, text):
    p = os.path.join(str(tmp_path), "exp.yaml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


VALID = """
exp_id: exp001
benchmark: experiments/fixtures/benchmark_v1.yaml
variants: [baseline, slim]
images_per_cell: 3
concurrency: 10
review_shuffle_seed: 20260705
"""


def test_load_valid_config(tmp_path):
    cfg = load_experiment_config(_write(tmp_path, VALID))
    assert cfg == ExperimentConfig(
        exp_id="exp001",
        benchmark="experiments/fixtures/benchmark_v1.yaml",
        variants=["baseline", "slim"],
        images_per_cell=3,
        concurrency=10,
        review_shuffle_seed=20260705,
    )


def test_concurrency_capped_at_10(tmp_path):
    bad = VALID.replace("concurrency: 10", "concurrency: 32")
    with pytest.raises(ValueError, match="concurrency"):
        load_experiment_config(_write(tmp_path, bad))


def test_missing_field_raises(tmp_path):
    bad = VALID.replace("images_per_cell: 3\n", "")
    with pytest.raises(ValueError, match="images_per_cell"):
        load_experiment_config(_write(tmp_path, bad))


def test_layout_paths():
    lay = ExpLayout("experiments/results", "exp001")
    assert lay.image_path("slim", "cas_hard", 2) == os.path.join(
        "experiments", "results", "exp001", "images", "slim", "cas_hard", "img_2.png"
    )
    assert lay.check_path("slim", "cas_hard", 2) == os.path.join(
        "experiments", "results", "exp001", "checks", "slim__cas_hard__img_2.json"
    )
    assert lay.manifest_path().endswith(os.path.join("exp001", "manifest.json"))
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'experiments'`）

- [ ] **Step 3: 实现**

```python
# experiments/config.py
"""实验配置加载。concurrency 硬上限 10（用户约束，独立于生产 task_concurrency）。"""
from dataclasses import dataclass

import yaml

MAX_CONCURRENCY = 10
_REQUIRED = ("exp_id", "benchmark", "variants", "images_per_cell",
             "concurrency", "review_shuffle_seed")


@dataclass(frozen=True)
class ExperimentConfig:
    exp_id: str
    benchmark: str
    variants: list
    images_per_cell: int
    concurrency: int
    review_shuffle_seed: int


def load_experiment_config(path: str) -> ExperimentConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    for key in _REQUIRED:
        if key not in raw:
            raise ValueError(f"实验配置缺少字段: {key}")
    concurrency = int(raw["concurrency"])
    if not 1 <= concurrency <= MAX_CONCURRENCY:
        raise ValueError(f"concurrency 必须在 1~{MAX_CONCURRENCY} 之间: {concurrency}")
    variants = [str(v) for v in raw["variants"]]
    if len(variants) < 2:
        raise ValueError("variants 至少需要 2 个（对照组 + 实验组）")
    return ExperimentConfig(
        exp_id=str(raw["exp_id"]),
        benchmark=str(raw["benchmark"]),
        variants=variants,
        images_per_cell=int(raw["images_per_cell"]),
        concurrency=concurrency,
        review_shuffle_seed=int(raw["review_shuffle_seed"]),
    )
```

```python
# experiments/layout.py
"""results 目录布局唯一事实源：runner/checker/report 均从这里取路径。"""
import os


class ExpLayout:
    def __init__(self, results_root: str, exp_id: str):
        self.root = os.path.join(results_root, exp_id)

    def prompts_dir(self, variant: str) -> str:
        return os.path.join(self.root, "prompts", variant)

    def prompt_path(self, variant: str, seed_id: str) -> str:
        return os.path.join(self.prompts_dir(variant), f"{seed_id}.txt")

    def image_dir(self, variant: str, seed_id: str) -> str:
        return os.path.join(self.root, "images", variant, seed_id)

    def image_path(self, variant: str, seed_id: str, k: int) -> str:
        return os.path.join(self.image_dir(variant, seed_id), f"img_{k}.png")

    def check_path(self, variant: str, seed_id: str, k: int) -> str:
        return os.path.join(self.root, "checks", f"{variant}__{seed_id}__img_{k}.json")

    def manifest_path(self) -> str:
        return os.path.join(self.root, "manifest.json")

    def metrics_path(self) -> str:
        return os.path.join(self.root, "metrics.json")

    def review_html_path(self) -> str:
        return os.path.join(self.root, "review.html")

    def final_report_path(self) -> str:
        return os.path.join(self.root, "final_report.md")
```

`.gitignore` 末尾追加：

```
# Experiments（运行产物不进 git，打包拷回本地）
experiments/results/
```

`requirements.txt` 末尾追加一行：`pyyaml>=6.0`

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/__init__.py experiments/config.py experiments/layout.py experiments/checker/__init__.py .gitignore requirements.txt
git add -f tests/experiments/__init__.py tests/experiments/test_config.py
git commit -m "feat(experiments): 实验层骨架 + 配置加载 + results 目录布局"
```

---

### Task 2: 基准集与锚点清单加载（Benchmark / AnchorList）

**Files:**
- Modify: `experiments/config.py`（追加 Benchmark 部分）
- Test: `tests/experiments/test_benchmark.py`

**Interfaces:**
- Consumes: 无（纯解析）
- Produces:
  - `SeedCase(seed_id: str, character_id: str, difficulty: str, aspect_ratio: str, text: str)`
  - `Benchmark(characters: dict[str, dict], seeds: list[SeedCase])`，`characters` 键为角色 key（如 `castorice`），值含 `character_id` 与 `anchors`（fixtures 相对路径）
  - `load_benchmark(path: str) -> Benchmark`
  - `Anchor(anchor_id: str, question: str, ref_slot: str)` 与 `load_anchor_list(path: str) -> list[Anchor]`；`ref_slot` 取值限 `full_front / full_side / half_front / half_side / face_close`（对应 `standard_photo_slots/` 5 个槽位文件名）

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_benchmark.py
import os
import pytest

from experiments.config import load_anchor_list, load_benchmark

BENCH = """
characters:
  castorice:
    character_id: mchar_3695c70ca7
    anchors: experiments/fixtures/anchors/castorice.yaml
seeds:
  - seed_id: cas_easy
    character: castorice
    difficulty: easy
    aspect_ratio: "16:9"
    text: 角色安静地倚坐在窗边
  - seed_id: cas_hard
    character: castorice
    difficulty: hard
    aspect_ratio: "4:3"
    text: 角色以鸭子坐姿势坐在地毯上
"""

ANCHORS = """
anchors:
  - anchor_id: crown
    question: 对比两图：第一张图中人物是否佩戴与第二张图相同的黑荆棘粉白花冠？
    ref_slot: face_close
  - anchor_id: elf_ears
    question: 对比两图：第一张图中人物是否具有与第二张图相同的尖长精灵耳？
    ref_slot: face_close
"""


def _write(tmp_path, name, text):
    p = os.path.join(str(tmp_path), name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def test_load_benchmark(tmp_path):
    b = load_benchmark(_write(tmp_path, "bench.yaml", BENCH))
    assert b.characters["castorice"]["character_id"] == "mchar_3695c70ca7"
    assert len(b.seeds) == 2
    s = b.seeds[1]
    assert (s.seed_id, s.character_id, s.difficulty, s.aspect_ratio) == (
        "cas_hard", "mchar_3695c70ca7", "hard", "4:3",
    )
    assert "鸭子坐" in s.text


def test_benchmark_unknown_character_raises(tmp_path):
    bad = BENCH.replace("character: castorice\n    difficulty: easy",
                        "character: nobody\n    difficulty: easy")
    with pytest.raises(ValueError, match="nobody"):
        load_benchmark(_write(tmp_path, "bench.yaml", bad))


def test_benchmark_duplicate_seed_id_raises(tmp_path):
    bad = BENCH.replace("seed_id: cas_hard", "seed_id: cas_easy")
    with pytest.raises(ValueError, match="cas_easy"):
        load_benchmark(_write(tmp_path, "bench.yaml", bad))


def test_load_anchor_list(tmp_path):
    anchors = load_anchor_list(_write(tmp_path, "a.yaml", ANCHORS))
    assert [a.anchor_id for a in anchors] == ["crown", "elf_ears"]
    assert anchors[0].ref_slot == "face_close"


def test_anchor_bad_ref_slot_raises(tmp_path):
    bad = ANCHORS.replace("ref_slot: face_close", "ref_slot: nonexistent", 1)
    with pytest.raises(ValueError, match="ref_slot"):
        load_anchor_list(_write(tmp_path, "a.yaml", bad))
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_benchmark.py -v`
Expected: FAIL（`ImportError: cannot import name 'load_benchmark'`）

- [ ] **Step 3: 实现（追加到 experiments/config.py 末尾）**

```python
_VALID_REF_SLOTS = {"full_front", "full_side", "half_front", "half_side", "face_close"}


@dataclass(frozen=True)
class SeedCase:
    seed_id: str
    character_id: str
    difficulty: str
    aspect_ratio: str
    text: str


@dataclass(frozen=True)
class Benchmark:
    characters: dict
    seeds: list


@dataclass(frozen=True)
class Anchor:
    anchor_id: str
    question: str
    ref_slot: str


def load_benchmark(path: str) -> Benchmark:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    characters = raw.get("characters") or {}
    if not characters:
        raise ValueError("benchmark 缺少 characters")
    seeds = []
    seen_ids = set()
    for item in raw.get("seeds") or []:
        char_key = str(item.get("character", ""))
        if char_key not in characters:
            raise ValueError(f"seed 引用了未定义的角色: {char_key}")
        seed_id = str(item.get("seed_id", ""))
        if not seed_id or seed_id in seen_ids:
            raise ValueError(f"seed_id 缺失或重复: {seed_id}")
        seen_ids.add(seed_id)
        seeds.append(SeedCase(
            seed_id=seed_id,
            character_id=str(characters[char_key]["character_id"]),
            difficulty=str(item.get("difficulty", "")),
            aspect_ratio=str(item.get("aspect_ratio", "")),
            text=str(item.get("text", "")),
        ))
    if not seeds:
        raise ValueError("benchmark 缺少 seeds")
    return Benchmark(characters=dict(characters), seeds=seeds)


def load_anchor_list(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    anchors = []
    for item in raw.get("anchors") or []:
        ref_slot = str(item.get("ref_slot", ""))
        if ref_slot not in _VALID_REF_SLOTS:
            raise ValueError(f"非法 ref_slot: {ref_slot}（允许: {sorted(_VALID_REF_SLOTS)}）")
        anchors.append(Anchor(
            anchor_id=str(item["anchor_id"]),
            question=str(item["question"]),
            ref_slot=ref_slot,
        ))
    if not anchors:
        raise ValueError("锚点清单为空")
    return anchors
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_benchmark.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/config.py
git add -f tests/experiments/test_benchmark.py
git commit -m "feat(experiments): 基准集与锚点清单加载"
```

---

### Task 3: checker 应答解析纯函数（parsers.py）

设计依据 spec §5：一次只问一个问题；计数题只回答数字；结构题「是/否 + 一句话理由」；锚点题「是/否/无法判断」。LLM 输出不可控，解析必须宽容（容忍标点、前后缀废话），解析失败返回明确的 `parse_error` 而非抛异常（单图核对失败不应中断整轮）。

**Files:**
- Create: `experiments/checker/parsers.py`
- Test: `tests/experiments/test_parsers.py`

**Interfaces:**
- Produces:
  - `parse_count_answer(text: str) -> Optional[int]`（提取第一个整数，含中文数字零～十；无法提取返回 None）
  - `parse_yes_no_reason(text: str) -> dict`：`{"verdict": "yes"|"no"|None, "reason": str}`（识别 是/否/yes/no 开头，剩余文本为 reason）
  - `parse_anchor_answer(text: str) -> str`：返回 `"yes" | "no" | "unsure"`（「无法判断/不确定/unsure」→ unsure；识别不了 → unsure）

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_parsers.py
from experiments.checker.parsers import (
    parse_anchor_answer,
    parse_count_answer,
    parse_yes_no_reason,
)


def test_count_plain_digit():
    assert parse_count_answer("2") == 2


def test_count_with_noise():
    assert parse_count_answer("图中人物有 3 条腿。") == 3


def test_count_chinese_numeral():
    assert parse_count_answer("两条") == 2
    assert parse_count_answer("四") == 4


def test_count_unparseable():
    assert parse_count_answer("看不清楚") is None


def test_yes_no_reason_yes():
    r = parse_yes_no_reason("是。画面中出现了两个躯干，上下重叠。")
    assert r["verdict"] == "yes"
    assert "躯干" in r["reason"]


def test_yes_no_reason_no():
    r = parse_yes_no_reason("否，颈部与腰部曲线自然，无扭曲。")
    assert r["verdict"] == "no"


def test_yes_no_reason_unparseable():
    r = parse_yes_no_reason("这个问题很有意思")
    assert r["verdict"] is None


def test_anchor_yes():
    assert parse_anchor_answer("是，佩戴了相同的花冠") == "yes"


def test_anchor_no():
    assert parse_anchor_answer("否") == "no"


def test_anchor_unsure():
    assert parse_anchor_answer("无法判断，头部被遮挡") == "unsure"
    assert parse_anchor_answer("嗯……") == "unsure"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_parsers.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# experiments/checker/parsers.py
"""视觉 LLM 应答解析。宽容解析：失败返回 None/unsure，不抛异常。"""
import re
from typing import Optional

_CN_NUM = {"零": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4,
           "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_YES_PAT = re.compile(r"^\s*[\*\s（(【\[]*\s*(是|yes)", re.IGNORECASE)
_NO_PAT = re.compile(r"^\s*[\*\s（(【\[]*\s*(否|不是|没有|no)", re.IGNORECASE)
_UNSURE_PAT = re.compile(r"无法判断|不确定|难以判断|unsure|cannot", re.IGNORECASE)


def parse_count_answer(text: str) -> Optional[int]:
    s = (text or "").strip()
    m = re.search(r"\d+", s)
    if m:
        return int(m.group())
    for ch in s:
        if ch in _CN_NUM:
            return _CN_NUM[ch]
    return None


def parse_yes_no_reason(text: str) -> dict:
    s = (text or "").strip()
    verdict = None
    if _NO_PAT.match(s):
        verdict = "no"
    elif _YES_PAT.match(s):
        verdict = "yes"
    reason = re.sub(r"^\s*(是|否|不是|没有|yes|no)[，。,.:：\s]*", "", s,
                    count=1, flags=re.IGNORECASE).strip()
    return {"verdict": verdict, "reason": reason}


def parse_anchor_answer(text: str) -> str:
    s = (text or "").strip()
    if _UNSURE_PAT.search(s):
        return "unsure"
    if _NO_PAT.match(s):
        return "no"
    if _YES_PAT.match(s):
        return "yes"
    return "unsure"
```

注意 `_NO_PAT` 判定必须先于 `_YES_PAT`（「不是」以「不」开头，但「是」模式会匹配到句中——用行首锚定 + 先 no 后 yes 消除歧义）。

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_parsers.py -v`
Expected: 10 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/checker/parsers.py
git add -f tests/experiments/test_parsers.py
git commit -m "feat(experiments): checker 应答解析纯函数"
```

---

### Task 4: 结构检查 + 锚点核对（checks.py）

spec §5.1/§5.2 的核心：4 个结构检查项每项独立一次视觉 LLM 调用、只喂生成图；锚点核对每锚点一次调用、喂生成图 + 1 张参考图。全部走 `yibu_gemini_infer` 多模态通道。

**Files:**
- Create: `experiments/checker/checks.py`
- Test: `tests/experiments/test_checks.py`

**Interfaces:**
- Consumes: `parsers.parse_count_answer / parse_yes_no_reason / parse_anchor_answer`（Task 3）、`Anchor`（Task 2）、`yibu_gemini_infer`
- Produces:
  - `STRUCTURE_CHECKS: list[dict]` — 4 项定义（check_id / kind / question）
  - `run_structure_checks(image_path: str, infer=yibu_gemini_infer) -> dict`：`{check_id: {...}}`，多腿项 `{"kind": "count", "value": int|None, "pass": bool|None, "raw": str}`（真值 2，`pass = value == 2`，解析失败 pass=None）；其余 3 项 `{"kind": "yes_no", "verdict": ..., "reason": ..., "pass": bool|None, "raw": str}`（问题问「是否存在异常」，`pass = verdict == "no"`）
  - `run_anchor_checks(image_path: str, character_id: str, anchors: list[Anchor], infer=yibu_gemini_infer) -> dict`：`{anchor_id: {"answer": "yes"|"no"|"unsure", "raw": str}}`
  - 单项调用抛异常时该项记 `{"error": str(e)}`，不中断其余项

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_checks.py
from experiments.checker.checks import (
    STRUCTURE_CHECKS,
    run_anchor_checks,
    run_structure_checks,
)
from experiments.config import Anchor


def test_structure_checks_definition():
    ids = [c["check_id"] for c in STRUCTURE_CHECKS]
    assert ids == ["leg_count", "torso_dup", "neck_waist_twist", "furniture_broken"]
    assert STRUCTURE_CHECKS[0]["kind"] == "count"
    assert all(c["kind"] == "yes_no" for c in STRUCTURE_CHECKS[1:])


def test_run_structure_checks_all_pass():
    answers = {
        "leg_count": "2",
        "torso_dup": "否，只有一个躯干。",
        "neck_waist_twist": "否，颈腰姿态自然。",
        "furniture_broken": "否，家具结构正常。",
    }

    def fake_infer(prompt, image_path=None, **kw):
        assert image_path == ["fake.png"]
        for c in STRUCTURE_CHECKS:
            if c["question"] in prompt:
                return answers[c["check_id"]]
        raise AssertionError("未知问题: " + prompt)

    out = run_structure_checks("fake.png", infer=fake_infer)
    assert out["leg_count"]["value"] == 2 and out["leg_count"]["pass"] is True
    assert out["torso_dup"]["pass"] is True
    assert out["torso_dup"]["reason"]


def test_run_structure_checks_multileg_fail():
    def fake_infer(prompt, image_path=None, **kw):
        return "3" if "几条腿" in prompt else "否"

    out = run_structure_checks("fake.png", infer=fake_infer)
    assert out["leg_count"]["value"] == 3 and out["leg_count"]["pass"] is False


def test_run_structure_checks_error_isolated():
    calls = []

    def fake_infer(prompt, image_path=None, **kw):
        calls.append(prompt)
        if "几条腿" in prompt:
            raise RuntimeError("API down")
        return "否"

    out = run_structure_checks("fake.png", infer=fake_infer)
    assert "error" in out["leg_count"]
    assert out["torso_dup"]["pass"] is True  # 其余项照常执行
    assert len(calls) == 4


def test_run_anchor_checks(monkeypatch):
    import experiments.checker.checks as mod
    monkeypatch.setattr(
        mod, "_resolve_ref_slot_path", lambda cid, slot: f"/refs/{cid}/{slot}.png"
    )
    seen = []

    def fake_infer(prompt, image_path=None, **kw):
        seen.append(image_path)
        return "是，佩戴相同花冠"

    anchors = [Anchor(anchor_id="crown", question="是否佩戴相同的花冠？",
                      ref_slot="face_close")]
    out = run_anchor_checks("gen.png", "mchar_x", anchors, infer=fake_infer)
    assert out["crown"]["answer"] == "yes"
    assert seen == [["gen.png", "/refs/mchar_x/face_close.png"]]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_checks.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# experiments/checker/checks.py
"""第一层结构完整性检查 + 第二层锚点核对。每项独立一次视觉 LLM 调用（spec §5）。"""
import logging

from app.services.material_service.material_file_service import (
    get_standard_slot_image_path,
)
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

from experiments.checker.parsers import (
    parse_anchor_answer,
    parse_count_answer,
    parse_yes_no_reason,
)

logger = logging.getLogger(__name__)

_SYSTEM = "你是一位严谨的图像质检员，只回答被问到的问题本身，不要输出任何多余内容。"

STRUCTURE_CHECKS = [
    {
        "check_id": "leg_count",
        "kind": "count",
        "question": "图中人物有几条腿？只回答数字。",
    },
    {
        "check_id": "torso_dup",
        "kind": "yes_no",
        "question": "图中是否出现一个以上的上半身/躯干，或躯干与头部数量不匹配？"
                    "请回答“是”或“否”，并给出一句话理由。",
    },
    {
        "check_id": "neck_waist_twist",
        "kind": "yes_no",
        "question": "图中人物的颈部或腰部是否存在违反人体结构的异常扭曲、拉伸或错位？"
                    "请回答“是”或“否”，并给出一句话理由。",
    },
    {
        "check_id": "furniture_broken",
        "kind": "yes_no",
        "question": "图中家具是否存在结构性错误（椅腿数量异常、结构穿插、透视崩塌）？"
                    "请回答“是”或“否”，并给出一句话理由。",
    },
]


def run_structure_checks(image_path: str, infer=yibu_gemini_infer) -> dict:
    out = {}
    for check in STRUCTURE_CHECKS:
        cid = check["check_id"]
        try:
            raw = infer(check["question"], image_path=[image_path],
                        system_instruction=_SYSTEM, thinking_level="low",
                        temperature=0.1)
        except Exception as e:  # 单项失败不阻断其余项
            logger.warning("结构检查 %s 调用失败: %s", cid, e)
            out[cid] = {"kind": check["kind"], "error": str(e) or type(e).__name__}
            continue
        if check["kind"] == "count":
            value = parse_count_answer(raw)
            out[cid] = {"kind": "count", "value": value,
                        "pass": (value == 2) if value is not None else None,
                        "raw": raw}
        else:
            parsed = parse_yes_no_reason(raw)
            verdict = parsed["verdict"]
            out[cid] = {"kind": "yes_no", "verdict": verdict,
                        "reason": parsed["reason"],
                        "pass": (verdict == "no") if verdict else None,
                        "raw": raw}
    return out


def _resolve_ref_slot_path(character_id: str, ref_slot: str) -> str:
    p = get_standard_slot_image_path(character_id, ref_slot)
    if not p:
        raise ValueError(f"角色 {character_id} 缺少参考图槽位 {ref_slot}")
    return p


def run_anchor_checks(image_path: str, character_id: str, anchors,
                      infer=yibu_gemini_infer) -> dict:
    out = {}
    for anchor in anchors:
        try:
            ref = _resolve_ref_slot_path(character_id, anchor.ref_slot)
            prompt = (
                "第一张图是 AI 生成图，第二张图是该角色的官方参考图。"
                f"{anchor.question}"
                "请只回答“是”、“否”或“无法判断”。"
            )
            raw = infer(prompt, image_path=[image_path, ref],
                        system_instruction=_SYSTEM, thinking_level="low",
                        temperature=0.1)
            out[anchor.anchor_id] = {"answer": parse_anchor_answer(raw), "raw": raw}
        except Exception as e:
            logger.warning("锚点核对 %s 调用失败: %s", anchor.anchor_id, e)
            out[anchor.anchor_id] = {"error": str(e) or type(e).__name__}
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_checks.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/checker/checks.py
git add -f tests/experiments/test_checks.py
git commit -m "feat(experiments): 结构完整性检查与锚点核对"
```

---

### Task 5: 逐图全量核对 CLI（run_checks.py）

扫描 results 下已生成的图片，对每张图跑 4 结构检查 + 该角色全部锚点，逐图落一个 JSON 到 `checks/`。并发 ≤ 10（ThreadPoolExecutor，粒度为「图」——单图内 8–12 次调用串行，与 spec §5.5 成本估算一致且实现最简单）。已存在的 check JSON 默认跳过（断点续跑），`--force` 重跑。

**Files:**
- Create: `experiments/checker/run_checks.py`
- Test: `tests/experiments/test_run_checks.py`

**Interfaces:**
- Consumes: `load_experiment_config / load_benchmark / load_anchor_list`（Task 1/2）、`ExpLayout`（Task 1）、`run_structure_checks / run_anchor_checks`（Task 4）、manifest.json（Task 9 产出，结构见下）
- Produces:
  - `check_one_image(entry: dict, anchors_by_char: dict, layout: ExpLayout, infer) -> dict` — 单图核对并写 JSON，返回该 JSON dict
  - `run_all_checks(config_path: str, results_root: str = "experiments/results", force: bool = False, infer=yibu_gemini_infer) -> dict` — 返回 `{"checked": int, "skipped": int, "failed": int}`
  - CLI: `python -m experiments.checker.run_checks --config experiments/configs/exp001.yaml [--force]`
  - 逐图 JSON 结构（report.py 依赖）：

```json
{
  "variant": "slim", "seed_id": "cas_hard", "image_index": 1,
  "image_path": "images/slim/cas_hard/img_1.png",
  "character_id": "mchar_3695c70ca7",
  "structure": {"leg_count": {"kind": "count", "value": 2, "pass": true, "raw": "2"}, "...": {}},
  "anchors": {"crown": {"answer": "yes", "raw": "是"}}
}
```

manifest.json 结构（Task 9 写入、本任务读取）：`{"entries": [{"variant", "seed_id", "image_index", "character_id", "image_path"(相对 exp 根), "aspect_ratio", "ok": true}]}`

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_run_checks.py
import json
import os

from experiments.checker.run_checks import run_all_checks
from experiments.layout import ExpLayout

CFG = """
exp_id: exp001
benchmark: {bench}
variants: [baseline, slim]
images_per_cell: 1
concurrency: 2
review_shuffle_seed: 1
"""

BENCH = """
characters:
  castorice:
    character_id: mchar_x
    anchors: {anchors}
seeds:
  - seed_id: s1
    character: castorice
    difficulty: easy
    aspect_ratio: "16:9"
    text: 种子一
"""

ANCHORS = """
anchors:
  - anchor_id: crown
    question: 是否佩戴相同的花冠？
    ref_slot: face_close
"""


def _setup(tmp_path):
    root = str(tmp_path)
    anchors_p = os.path.join(root, "anchors.yaml")
    bench_p = os.path.join(root, "bench.yaml")
    cfg_p = os.path.join(root, "exp.yaml")
    with open(anchors_p, "w", encoding="utf-8") as f:
        f.write(ANCHORS)
    with open(bench_p, "w", encoding="utf-8") as f:
        f.write(BENCH.format(anchors=anchors_p.replace("\\", "/")))
    with open(cfg_p, "w", encoding="utf-8") as f:
        f.write(CFG.format(bench=bench_p.replace("\\", "/")))
    results_root = os.path.join(root, "results")
    lay = ExpLayout(results_root, "exp001")
    entries = []
    for variant in ("baseline", "slim"):
        img = lay.image_path(variant, "s1", 1)
        os.makedirs(os.path.dirname(img), exist_ok=True)
        with open(img, "wb") as f:
            f.write(b"fake-png")
        entries.append({
            "variant": variant, "seed_id": "s1", "image_index": 1,
            "character_id": "mchar_x",
            "image_path": os.path.relpath(img, lay.root).replace("\\", "/"),
            "aspect_ratio": "16:9", "ok": True,
        })
    os.makedirs(os.path.dirname(lay.manifest_path()), exist_ok=True)
    with open(lay.manifest_path(), "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f)
    return cfg_p, results_root, lay


def _fake_infer(prompt, image_path=None, **kw):
    if "几条腿" in prompt:
        return "2"
    if "花冠" in prompt:
        return "是"
    return "否，正常。"


def test_run_all_checks_writes_json(tmp_path, monkeypatch):
    import experiments.checker.checks as checks_mod
    monkeypatch.setattr(checks_mod, "_resolve_ref_slot_path",
                        lambda cid, slot: __file__)
    cfg_p, results_root, lay = _setup(tmp_path)
    stats = run_all_checks(cfg_p, results_root=results_root, infer=_fake_infer)
    assert stats == {"checked": 2, "skipped": 0, "failed": 0}
    with open(lay.check_path("slim", "s1", 1), encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["structure"]["leg_count"]["pass"] is True
    assert doc["anchors"]["crown"]["answer"] == "yes"
    assert doc["character_id"] == "mchar_x"


def test_run_all_checks_skips_existing(tmp_path, monkeypatch):
    import experiments.checker.checks as checks_mod
    monkeypatch.setattr(checks_mod, "_resolve_ref_slot_path",
                        lambda cid, slot: __file__)
    cfg_p, results_root, lay = _setup(tmp_path)
    run_all_checks(cfg_p, results_root=results_root, infer=_fake_infer)
    stats2 = run_all_checks(cfg_p, results_root=results_root, infer=_fake_infer)
    assert stats2 == {"checked": 0, "skipped": 2, "failed": 0}
    stats3 = run_all_checks(cfg_p, results_root=results_root, force=True,
                            infer=_fake_infer)
    assert stats3["checked"] == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_run_checks.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# experiments/checker/run_checks.py
"""对 manifest 中每张生成图执行全量核对。并发粒度=图，上限来自配置（≤10）。"""
import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

from experiments.config import (
    load_anchor_list,
    load_benchmark,
    load_experiment_config,
)
from experiments.layout import ExpLayout
from experiments.checker.checks import run_anchor_checks, run_structure_checks

logger = logging.getLogger(__name__)


def check_one_image(entry: dict, anchors_by_char: dict, layout: ExpLayout,
                    infer) -> dict:
    image_abs = os.path.join(layout.root, entry["image_path"])
    character_id = entry["character_id"]
    doc = {
        "variant": entry["variant"],
        "seed_id": entry["seed_id"],
        "image_index": entry["image_index"],
        "image_path": entry["image_path"],
        "character_id": character_id,
        "structure": run_structure_checks(image_abs, infer=infer),
        "anchors": run_anchor_checks(
            image_abs, character_id, anchors_by_char[character_id], infer=infer
        ),
    }
    out_path = layout.check_path(
        entry["variant"], entry["seed_id"], entry["image_index"]
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return doc


def run_all_checks(config_path: str, results_root: str = "experiments/results",
                   force: bool = False, infer=yibu_gemini_infer) -> dict:
    cfg = load_experiment_config(config_path)
    bench = load_benchmark(cfg.benchmark)
    anchors_by_char = {
        c["character_id"]: load_anchor_list(c["anchors"])
        for c in bench.characters.values()
    }
    layout = ExpLayout(results_root, cfg.exp_id)
    with open(layout.manifest_path(), "r", encoding="utf-8") as f:
        entries = [e for e in json.load(f)["entries"] if e.get("ok")]

    todo, skipped = [], 0
    for e in entries:
        cp = layout.check_path(e["variant"], e["seed_id"], e["image_index"])
        if os.path.isfile(cp) and not force:
            skipped += 1
        else:
            todo.append(e)

    checked = failed = 0
    with ThreadPoolExecutor(max_workers=cfg.concurrency) as pool:
        futures = {
            pool.submit(check_one_image, e, anchors_by_char, layout, infer): e
            for e in todo
        }
        for fut in as_completed(futures):
            e = futures[fut]
            try:
                fut.result()
                checked += 1
            except Exception as exc:
                failed += 1
                logger.error("核对失败 %s/%s#%s: %s", e["variant"],
                             e["seed_id"], e["image_index"], exc, exc_info=True)
    stats = {"checked": checked, "skipped": skipped, "failed": failed}
    logger.info("核对完成: %s", stats)
    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="逐图全量核对")
    ap.add_argument("--config", required=True)
    ap.add_argument("--results-root", default="experiments/results")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    stats = run_all_checks(args.config, results_root=args.results_root,
                           force=args.force)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_run_checks.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/checker/run_checks.py
git add -f tests/experiments/test_run_checks.py
git commit -m "feat(experiments): 逐图全量核对 CLI（并发受限、断点续跑）"
```

---

### Task 6: checker 校准 CLI（calibrate.py）

spec §5.4 上线门槛：用生产历史已知崩坏/正常图（用户挑选标注真值）验证各检查项准确率，不达标项降级人工评判。校准集是一个用户手工编写的 YAML：每条含图片路径 + 各检查项真值。

**Files:**
- Create: `experiments/checker/calibrate.py`
- Test: `tests/experiments/test_calibrate.py`

**Interfaces:**
- Consumes: `run_structure_checks`（Task 4）
- Produces:
  - `load_calibration_set(path: str) -> list[dict]` — 每条 `{"image": str, "truth": {check_id: bool}}`（truth 值为「该项应 pass」）
  - `run_calibration(calib_path: str, out_path: str, infer=yibu_gemini_infer, concurrency: int = 10) -> dict` — 返回并写出 `{check_id: {"total", "correct", "unparsed", "accuracy"}}`；解析失败（pass=None）计入 unparsed、不算 correct
  - CLI: `python -m experiments.checker.calibrate --calib experiments/fixtures/calibration_v1.yaml --out experiments/results/calibration_report.json`

校准集 YAML 格式（执行阶段由用户提供图片与标注，本任务只实现工具）：

```yaml
cases:
  - image: data/calibration/multileg_01.png
    truth: {leg_count: false, torso_dup: true, neck_waist_twist: true, furniture_broken: true}
  - image: data/calibration/normal_01.png
    truth: {leg_count: true, torso_dup: true, neck_waist_twist: true, furniture_broken: true}
```

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_calibrate.py
import json
import os

from experiments.checker.calibrate import load_calibration_set, run_calibration

CALIB = """
cases:
  - image: {img1}
    truth: {{leg_count: false, torso_dup: true, neck_waist_twist: true, furniture_broken: true}}
  - image: {img2}
    truth: {{leg_count: true, torso_dup: true, neck_waist_twist: true, furniture_broken: true}}
"""


def _setup(tmp_path):
    root = str(tmp_path)
    img1 = os.path.join(root, "bad.png")
    img2 = os.path.join(root, "good.png")
    for p in (img1, img2):
        with open(p, "wb") as f:
            f.write(b"x")
    calib_p = os.path.join(root, "calib.yaml")
    with open(calib_p, "w", encoding="utf-8") as f:
        f.write(CALIB.format(img1=img1.replace("\\", "/"),
                             img2=img2.replace("\\", "/")))
    return calib_p, img1, img2


def test_load_calibration_set(tmp_path):
    calib_p, img1, _ = _setup(tmp_path)
    cases = load_calibration_set(calib_p)
    assert len(cases) == 2
    assert cases[0]["truth"]["leg_count"] is False


def test_run_calibration_accuracy(tmp_path):
    calib_p, img1, img2 = _setup(tmp_path)

    def fake_infer(prompt, image_path=None, **kw):
        # bad.png 判 3 条腿（正确检出），good.png 判 2 条；其余项全部答否（正常）
        if "几条腿" in prompt:
            return "3" if image_path == [img1] else "2"
        return "否，正常。"

    out_path = os.path.join(str(tmp_path), "report.json")
    report = run_calibration(calib_p, out_path, infer=fake_infer, concurrency=2)
    assert report["leg_count"] == {
        "total": 2, "correct": 2, "unparsed": 0, "accuracy": 1.0
    }
    assert report["torso_dup"]["accuracy"] == 1.0
    with open(out_path, encoding="utf-8") as f:
        assert json.load(f) == report


def test_run_calibration_counts_miss(tmp_path):
    calib_p, img1, img2 = _setup(tmp_path)

    def fake_infer(prompt, image_path=None, **kw):
        if "几条腿" in prompt:
            return "2"  # bad.png 也答 2 → 漏检
        return "否"

    report = run_calibration(calib_p, os.path.join(str(tmp_path), "r.json"),
                             infer=fake_infer, concurrency=1)
    assert report["leg_count"]["correct"] == 1
    assert report["leg_count"]["accuracy"] == 0.5
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_calibrate.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# experiments/checker/calibrate.py
"""checker 校准：对已知真值图片跑结构检查，输出各项准确率（spec §5.4 上线门槛）。"""
import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import yaml

from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

from experiments.checker.checks import STRUCTURE_CHECKS, run_structure_checks

logger = logging.getLogger(__name__)


def load_calibration_set(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    cases = []
    for item in raw.get("cases") or []:
        image = str(item["image"])
        if not os.path.isfile(image):
            raise ValueError(f"校准图片不存在: {image}")
        truth = {str(k): bool(v) for k, v in (item.get("truth") or {}).items()}
        cases.append({"image": image, "truth": truth})
    if not cases:
        raise ValueError("校准集为空")
    return cases


def run_calibration(calib_path: str, out_path: str,
                    infer=yibu_gemini_infer, concurrency: int = 10) -> dict:
    cases = load_calibration_set(calib_path)
    with ThreadPoolExecutor(max_workers=min(concurrency, 10)) as pool:
        results = list(pool.map(
            lambda c: run_structure_checks(c["image"], infer=infer), cases
        ))

    report = {}
    for check in STRUCTURE_CHECKS:
        cid = check["check_id"]
        total = correct = unparsed = 0
        for case, result in zip(cases, results):
            if cid not in case["truth"]:
                continue
            total += 1
            got = result.get(cid, {}).get("pass")
            if got is None:
                unparsed += 1
            elif got == case["truth"][cid]:
                correct += 1
        report[cid] = {
            "total": total, "correct": correct, "unparsed": unparsed,
            "accuracy": round(correct / total, 4) if total else None,
        }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="checker 校准")
    ap.add_argument("--calib", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()
    report = run_calibration(args.calib, args.out, concurrency=args.concurrency)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_calibrate.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/checker/calibrate.py
git add -f tests/experiments/test_calibrate.py
git commit -m "feat(experiments): checker 校准工具"
```

---

### Task 7: exp001 fixtures（基准集 + 锚点清单 + 实验配置）

数据性任务：起草 benchmark_v1（6 种子）、两角色锚点清单、exp001.yaml。种子与锚点是「Claude 起草、**用户审定后冻结**」（spec §5.2/§7）——本任务产出初稿并提交，任务完成后必须提醒用户审定。种子来源：case1/case2 高危回归种子按生产 prompt 还原；简单/中等种子从两角色既有 `seed_draft.json` 挑选改写（Castorice: `data/material/characters/mchar_3695c70ca7/seed_prompt_tasks/daa8a900-.../seed_draft.json`；Hysilens: `data/material/characters/mchar_50c51e6e37/seed_prompt_tasks/ab052c8f-.../seed_draft.json`）。

**Files:**
- Create: `experiments/fixtures/benchmark_v1.yaml`
- Create: `experiments/fixtures/anchors/castorice.yaml`
- Create: `experiments/fixtures/anchors/hysilens.yaml`
- Create: `experiments/configs/exp001.yaml`
- Test: `tests/experiments/test_fixtures.py`

**Interfaces:**
- Consumes: `load_benchmark / load_anchor_list / load_experiment_config`（Task 1/2）
- Produces: 供 Task 8/9/10 直接消费的真实 fixtures 文件

- [ ] **Step 1: 写失败测试（fixtures 存在性 + 结构合法性 + spec 约束）**

```python
# tests/experiments/test_fixtures.py
from experiments.config import (
    load_anchor_list,
    load_benchmark,
    load_experiment_config,
)


def test_exp001_config_loads():
    cfg = load_experiment_config("experiments/configs/exp001.yaml")
    assert cfg.exp_id == "exp001"
    assert cfg.variants == ["baseline", "slim"]
    assert cfg.images_per_cell == 3          # 用户指定：每种子每组 3 张
    assert cfg.concurrency <= 10


def test_benchmark_v1_structure():
    b = load_benchmark("experiments/fixtures/benchmark_v1.yaml")
    assert b.characters["castorice"]["character_id"] == "mchar_3695c70ca7"
    assert b.characters["hysilens"]["character_id"] == "mchar_50c51e6e37"
    assert len(b.seeds) == 6                 # 每角色 3 条
    by_char = {}
    for s in b.seeds:
        by_char.setdefault(s.character_id, []).append(s.difficulty)
    for diffs in by_char.values():
        assert sorted(diffs) == ["easy", "hard", "medium"]  # 难度梯度覆盖
    # case1/case2 高危回归种子的画幅与生产一致
    ar = {s.seed_id: s.aspect_ratio for s in b.seeds}
    assert ar["cas_hard_wsit"] == "4:3"
    assert ar["hys_hard_bubble"] == "16:9"


def test_anchor_lists_load_and_are_bounded():
    for path in ("experiments/fixtures/anchors/castorice.yaml",
                 "experiments/fixtures/anchors/hysilens.yaml"):
        anchors = load_anchor_list(path)
        assert 3 <= len(anchors) <= 6        # 可判定视觉事实，不过度展开
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_fixtures.py -v`
Expected: FAIL（FileNotFoundError）

- [ ] **Step 3: 写 fixtures**

```yaml
# experiments/configs/exp001.yaml
exp_id: exp001
benchmark: experiments/fixtures/benchmark_v1.yaml
variants: [baseline, slim]
images_per_cell: 3
concurrency: 10
review_shuffle_seed: 20260705
```

```yaml
# experiments/fixtures/benchmark_v1.yaml
# 基准集 v1（spec §7）。种子文本 Claude 起草、用户审定后冻结。
# 难度梯度：easy=普通坐/倚靠, medium=盘腿/侧坐, hard=case1/case2 高危回归。
characters:
  castorice:
    character_id: mchar_3695c70ca7
    anchors: experiments/fixtures/anchors/castorice.yaml
  hysilens:
    character_id: mchar_50c51e6e37
    anchors: experiments/fixtures/anchors/hysilens.yaml

seeds:
  - seed_id: cas_easy_window
    character: castorice
    difficulty: easy
    aspect_ratio: "16:9"
    text: 明亮的开放式影音室里，角色整个人陷在巨大的白色懒人沙发中，双腿微微蜷缩。她穿着不对称设计的浅色休闲服，裸露的右臂随意伸展，充满水光感的亮紫瞳安静地看着上方的镜头。
  - seed_id: cas_med_squat
    character: castorice
    difficulty: medium
    aspect_ratio: "4:3"
    text: 角色乖巧地蹲在满是阳光的玄关处，穿着简单的居家白裙，嘴角挂着若有似无的浅笑。她褪去一半左手的黑色长手套，正用指尖试探性地温柔抚摸着一只趴在鞋柜上的毛绒白猫，展现出极致的信任感。
  - seed_id: cas_hard_wsit
    character: castorice
    difficulty: hard
    aspect_ratio: "4:3"
    text: 阳光明媚的客厅里，角色穿着宽大的浅紫色针织衫鸭子坐在地毯上，正用裸露的右手小心翼翼地半褪下左手的黑色长手套。她紫色的眼眸温柔地注视着镜头，头顶的黑荆棘花冠与现代家居形成奇妙的反差萌。
  - seed_id: hys_easy_recline
    character: hysilens
    difficulty: easy
    aspect_ratio: "16:9"
    text: 在客厅低矮沙发中，角色穿着真丝吊带裙慵懒地躺在松软的靠枕上，双腿交叠微微弯曲，神态放松。一侧的苍白肩膀从松垮开衫中滑落。
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
```

```yaml
# experiments/fixtures/anchors/castorice.yaml
# 锚点=可判定视觉事实（spec §5.2）。用户审定后冻结；ref_slot 指向最能看清该锚点的参考图。
anchors:
  - anchor_id: thorn_crown
    question: 对比两图：第一张图中人物是否佩戴与第二张图相同的、由黑色荆棘与粉白小花交织的花冠？
    ref_slot: face_close
  - anchor_id: forehead_gem
    question: 对比两图：第一张图中人物额前是否垂有与第二张图相同的水滴形深紫色宝石？
    ref_slot: face_close
  - anchor_id: elf_ears
    question: 对比两图：第一张图中人物是否具有与第二张图相同的尖长精灵耳？
    ref_slot: face_close
  - anchor_id: hair_color
    question: 对比两图：第一张图中人物的发色是否与第二张图相同（银紫/丁香紫色长发）？
    ref_slot: half_front
  - anchor_id: left_glove
    question: 对比两图：第一张图中人物的左臂是否与第二张图一样戴着深黑色织物长手套？
    ref_slot: full_front
```

```yaml
# experiments/fixtures/anchors/hysilens.yaml
anchors:
  - anchor_id: lace_choker
    question: 对比两图：第一张图中人物颈部是否佩戴与第二张图相同的黑色蕾丝项圈（中央有红珊瑚底座托举的蓝宝石）？
    ref_slot: face_close
  - anchor_id: coral_crown
    question: 对比两图：第一张图中人物发冠左侧是否有与第二张图相同的白色珊瑚状刺冠？
    ref_slot: face_close
  - anchor_id: hair_gradient
    question: 对比两图：第一张图中人物是否与第二张图一样为极长黑褐直发且发尾渐变为品红色？
    ref_slot: half_front
  - anchor_id: hime_bangs
    question: 对比两图：第一张图中人物是否与第二张图一样为姬发式齐刘海？
    ref_slot: face_close
  - anchor_id: wrist_cord
    question: 对比两图：第一张图中人物右手腕是否与第二张图一样系有深红色编织手绳？
    ref_slot: full_front
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_fixtures.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交，并提醒用户审定**

```bash
git add experiments/configs/exp001.yaml experiments/fixtures/
git add -f tests/experiments/test_fixtures.py
git commit -m "feat(experiments): exp001 基准集/锚点清单/实验配置初稿（待用户审定）"
```

完成后向用户输出：「基准集 6 种子与两角色锚点清单为初稿，请审定 `experiments/fixtures/` 下三个 YAML；审定通过后视为冻结。」

---

### Task 8: 基线 Prompt 生成冻结 CLI（baseline_gen.py）

spec §4 决策 4：对照组与实验组共用同一批基线 Prompt，基线走现有 step1→step2 生成一次、**冻结进 git**（`experiments/variants/exp001/baseline/<seed_id>.txt`）。case1/case2 对应种子不重新生成，直接用生产原文（`--from-file` 支持）。生成时同步产出每种子的 composition 信息并入 benchmark 校验（画幅必须与 benchmark 声明一致，不一致以 benchmark 为准并 warn——出图画幅由 benchmark 的 aspect_ratio 控制，保证 A/B 同画幅）。

**Files:**
- Create: `experiments/baseline_gen.py`
- Test: `tests/experiments/test_baseline_gen.py`

**Interfaces:**
- Consumes: `load_experiment_config / load_benchmark`（Task 1/2）、`_build_step1_prompt / _parse_step1_composition`、`prompt_step2`、`good_template1`、`yibu_gemini_infer`、`read_chara_profile_markdown`
- Produces:
  - `generate_baseline_for_seed(seed: SeedCase, chara_profile: str, infer=yibu_gemini_infer) -> str` — 跑 step1→step2 返回最终 Prompt 全文
  - `run_baseline_gen(config_path: str, only: Optional[list[str]] = None, infer=yibu_gemini_infer) -> dict` — 对 benchmark 每种子生成并写 `experiments/variants/<exp_id>/baseline/<seed_id>.txt`；已存在的跳过（冻结语义：绝不覆盖）；返回 `{"generated": [...], "skipped": [...]}`
  - CLI: `python -m experiments.baseline_gen --config experiments/configs/exp001.yaml [--only cas_easy_window,...]`
  - variants 文件路径约定（Task 9 消费）：`experiments/variants/<exp_id>/<variant>/<seed_id>.txt`

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_baseline_gen.py
import os

import experiments.baseline_gen as bg
from experiments.baseline_gen import run_baseline_gen

CFG = """
exp_id: exp001
benchmark: {bench}
variants: [baseline, slim]
images_per_cell: 3
concurrency: 10
review_shuffle_seed: 1
"""

BENCH = """
characters:
  castorice:
    character_id: mchar_x
    anchors: {anchors}
seeds:
  - seed_id: s1
    character: castorice
    difficulty: easy
    aspect_ratio: "16:9"
    text: 种子一
"""

ANCHORS = """
anchors:
  - anchor_id: a1
    question: q?
    ref_slot: face_close
"""


def _setup(tmp_path, monkeypatch):
    root = str(tmp_path)
    paths = {}
    for name, content in (("anchors.yaml", ANCHORS), ):
        p = os.path.join(root, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        paths[name] = p
    bench_p = os.path.join(root, "bench.yaml")
    with open(bench_p, "w", encoding="utf-8") as f:
        f.write(BENCH.format(anchors=paths["anchors.yaml"].replace("\\", "/")))
    cfg_p = os.path.join(root, "exp.yaml")
    with open(cfg_p, "w", encoding="utf-8") as f:
        f.write(CFG.format(bench=bench_p.replace("\\", "/")))
    variants_root = os.path.join(root, "variants")
    monkeypatch.setattr(bg, "VARIANTS_ROOT", variants_root)
    monkeypatch.setattr(bg, "_load_profile", lambda cid: "角色档案全文")
    return cfg_p, variants_root


def test_baseline_gen_writes_and_freezes(tmp_path, monkeypatch):
    cfg_p, variants_root = _setup(tmp_path, monkeypatch)
    calls = []

    def fake_infer(prompt, **kw):
        calls.append(prompt)
        if len(calls) % 2 == 1:  # step1
            return "**[COMPOSITION_DECISION]**\naspect_ratio: 16:9\n\n模板正文"
        return "step2 最终 Prompt 全文"

    out = run_baseline_gen(cfg_p, infer=fake_infer)
    assert out["generated"] == ["s1"] and out["skipped"] == []
    target = os.path.join(variants_root, "exp001", "baseline", "s1.txt")
    with open(target, encoding="utf-8") as f:
        assert f.read() == "step2 最终 Prompt 全文"
    assert len(calls) == 2  # step1 + step2 各一次

    # 冻结语义：重复运行不覆盖、不再调 LLM
    out2 = run_baseline_gen(cfg_p, infer=fake_infer)
    assert out2 == {"generated": [], "skipped": ["s1"]}
    assert len(calls) == 2


def test_baseline_gen_only_filter(tmp_path, monkeypatch):
    cfg_p, _ = _setup(tmp_path, monkeypatch)
    out = run_baseline_gen(cfg_p, only=["nonexistent"],
                           infer=lambda *a, **k: "x")
    assert out == {"generated": [], "skipped": []}
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_baseline_gen.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# experiments/baseline_gen.py
"""基线 Prompt 生成冻结：每种子走生产 step1→step2 一次，写入 variants/ 进 git。
已存在的文件绝不覆盖（冻结语义）；case1/case2 生产原文可手工放入后自动跳过。"""
import argparse
import json
import logging
import os

from app.prompts.creation.prompt_precreation import prompt_step2
from app.prompts.creation.prompt_template import good_template1
from app.services.creation_service.prompt_precreation_service import (
    _build_step1_prompt,
    _parse_step1_composition,
)
from app.services.material_service.material_file_service import (
    read_chara_profile_markdown,
)
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

from experiments.config import load_benchmark, load_experiment_config

logger = logging.getLogger(__name__)

VARIANTS_ROOT = os.path.join("experiments", "variants")


def _load_profile(character_id: str) -> str:
    md = read_chara_profile_markdown(character_id, "chara_profile_final.md")
    if not md or not md.strip():
        raise ValueError(f"角色 {character_id} 缺少 chara_profile_final.md")
    return md.strip()


def generate_baseline_for_seed(seed, chara_profile: str,
                               infer=yibu_gemini_infer) -> str:
    p1 = _build_step1_prompt(chara_profile=chara_profile, seed_prompt=seed.text)
    step1_result = infer(p1, thinking_level="high", temperature=1.0)
    comp = _parse_step1_composition(step1_result)
    decided_ar = comp.get("aspect_ratio")
    if decided_ar and decided_ar != seed.aspect_ratio:
        logger.warning(
            "种子 %s: step1 决策画幅 %s 与 benchmark 声明 %s 不一致，出图以 benchmark 为准",
            seed.seed_id, decided_ar, seed.aspect_ratio,
        )
    p2 = prompt_step2.format(
        init_template=step1_result,
        good_template=good_template1,
        chara_profile=chara_profile,
        seed_prompt=seed.text,
    )
    return infer(p2, thinking_level="high", temperature=1.0)


def run_baseline_gen(config_path: str, only=None, infer=yibu_gemini_infer) -> dict:
    cfg = load_experiment_config(config_path)
    bench = load_benchmark(cfg.benchmark)
    out_dir = os.path.join(VARIANTS_ROOT, cfg.exp_id, "baseline")
    os.makedirs(out_dir, exist_ok=True)

    generated, skipped = [], []
    profiles = {}
    for seed in bench.seeds:
        if only and seed.seed_id not in only:
            continue
        target = os.path.join(out_dir, f"{seed.seed_id}.txt")
        if os.path.isfile(target):
            logger.info("已冻结，跳过: %s", target)
            skipped.append(seed.seed_id)
            continue
        if seed.character_id not in profiles:
            profiles[seed.character_id] = _load_profile(seed.character_id)
        logger.info("生成基线: %s", seed.seed_id)
        text = generate_baseline_for_seed(
            seed, profiles[seed.character_id], infer=infer
        )
        with open(target, "w", encoding="utf-8") as f:
            f.write(text)
        generated.append(seed.seed_id)
    return {"generated": generated, "skipped": skipped}


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="基线 Prompt 生成冻结")
    ap.add_argument("--config", required=True)
    ap.add_argument("--only", help="逗号分隔的 seed_id 列表，缺省为全部")
    args = ap.parse_args()
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    print(json.dumps(run_baseline_gen(args.config, only=only),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_baseline_gen.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/baseline_gen.py
git add -f tests/experiments/test_baseline_gen.py
git commit -m "feat(experiments): 基线 Prompt 生成冻结 CLI"
```

---

### Task 9: 出图执行器（runner.py）

exp001 主循环：对每 variant × 每种子，读 `experiments/variants/<exp_id>/<variant>/<seed_id>.txt`，用与生产 quick_create 完全一致的多模态装配（Prompt 全文 + 参考图指引文案 + 5 张标准参考图）调 Nano Banana，出 `images_per_cell` 张图。画幅取 benchmark 的 `seed.aspect_ratio`（A/B 同画幅，唯一变量是 Prompt 文本）。发送全文存档进 `prompts/`，每张图记入 manifest。断点续跑：已存在且 manifest 标记 ok 的图不重出。

**Files:**
- Create: `experiments/runner.py`
- Test: `tests/experiments/test_runner.py`

**Interfaces:**
- Consumes: `load_experiment_config / load_benchmark`、`ExpLayout`、`generate_image_with_nano_banana_pro`、`standard_reference_paths_for_multimodal_prompt`、`VARIANTS_ROOT`（Task 8）
- Produces:
  - `run_experiment(config_path: str, results_root: str = "experiments/results", gen_image=generate_image_with_nano_banana_pro) -> dict` — 返回 `{"generated": int, "skipped": int, "failed": int}`
  - manifest.json（Task 5 消费）：`{"entries": [{"variant", "seed_id", "image_index"(1-based), "character_id", "image_path"(相对 exp 根、"/"分隔), "aspect_ratio", "ok": bool}]}`
  - CLI: `python -m experiments.runner --config experiments/configs/exp001.yaml`

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_runner.py
import json
import os

import experiments.runner as rn
from experiments.layout import ExpLayout
from experiments.runner import run_experiment

CFG = """
exp_id: exp001
benchmark: {bench}
variants: [baseline, slim]
images_per_cell: 2
concurrency: 3
review_shuffle_seed: 1
"""

BENCH = """
characters:
  castorice:
    character_id: mchar_x
    anchors: {anchors}
seeds:
  - seed_id: s1
    character: castorice
    difficulty: easy
    aspect_ratio: "4:3"
    text: 种子一
"""

ANCHORS = "anchors:\n  - {anchor_id: a1, question: q?, ref_slot: face_close}\n"


def _setup(tmp_path, monkeypatch):
    root = str(tmp_path)
    anchors_p = os.path.join(root, "anchors.yaml")
    with open(anchors_p, "w", encoding="utf-8") as f:
        f.write(ANCHORS)
    bench_p = os.path.join(root, "bench.yaml")
    with open(bench_p, "w", encoding="utf-8") as f:
        f.write(BENCH.format(anchors=anchors_p.replace("\\", "/")))
    cfg_p = os.path.join(root, "exp.yaml")
    with open(cfg_p, "w", encoding="utf-8") as f:
        f.write(CFG.format(bench=bench_p.replace("\\", "/")))
    variants_root = os.path.join(root, "variants")
    for variant in ("baseline", "slim"):
        d = os.path.join(variants_root, "exp001", variant)
        os.makedirs(d)
        with open(os.path.join(d, "s1.txt"), "w", encoding="utf-8") as f:
            f.write(f"{variant} 的 Prompt 全文")
    monkeypatch.setattr(rn, "VARIANTS_ROOT", variants_root)
    monkeypatch.setattr(rn, "_resolve_refs", lambda cid: ["r1.png", "r2.png"])
    return cfg_p, os.path.join(root, "results")


def test_run_experiment_generates_all_cells(tmp_path, monkeypatch):
    cfg_p, results_root = _setup(tmp_path, monkeypatch)
    calls = []

    def fake_gen(Content, output_path, file_name, aspect_ratio="16:9", **kw):
        calls.append((Content[0]["text"], aspect_ratio))
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, file_name), "wb") as f:
            f.write(b"png")
        return True

    stats = run_experiment(cfg_p, results_root=results_root, gen_image=fake_gen)
    assert stats == {"generated": 4, "skipped": 0, "failed": 0}  # 2 variants × 1 seed × 2 张
    assert all(ar == "4:3" for _, ar in calls)                   # 画幅取 benchmark
    texts = {t for t, _ in calls}
    assert texts == {"baseline 的 Prompt 全文", "slim 的 Prompt 全文"}

    lay = ExpLayout(results_root, "exp001")
    with open(lay.manifest_path(), encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    assert len(entries) == 4
    assert {e["variant"] for e in entries} == {"baseline", "slim"}
    assert all(e["ok"] for e in entries)
    assert all("\\" not in e["image_path"] for e in entries)
    # 发送全文存档
    with open(lay.prompt_path("slim", "s1"), encoding="utf-8") as f:
        assert f.read() == "slim 的 Prompt 全文"


def test_run_experiment_resumes(tmp_path, monkeypatch):
    cfg_p, results_root = _setup(tmp_path, monkeypatch)
    n_calls = {"n": 0}

    def fake_gen(Content, output_path, file_name, **kw):
        n_calls["n"] += 1
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, file_name), "wb") as f:
            f.write(b"png")
        return True

    run_experiment(cfg_p, results_root=results_root, gen_image=fake_gen)
    stats2 = run_experiment(cfg_p, results_root=results_root, gen_image=fake_gen)
    assert stats2 == {"generated": 0, "skipped": 4, "failed": 0}
    assert n_calls["n"] == 4  # 第二轮零调用


def test_run_experiment_records_failure(tmp_path, monkeypatch):
    cfg_p, results_root = _setup(tmp_path, monkeypatch)
    stats = run_experiment(cfg_p, results_root=results_root,
                           gen_image=lambda **kw: False)
    assert stats["failed"] == 4 and stats["generated"] == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_runner.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# experiments/runner.py
"""exp 出图执行器：variant × seed × images_per_cell，多模态装配与生产 quick_create 一致。
并发粒度=单张图；断点续跑以 manifest ok 标记 + 文件存在为准。"""
import argparse
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.material_service.material_file_service import (
    standard_reference_paths_for_multimodal_prompt,
)
from app.tools.llm.nano_banana_pro import generate_image_with_nano_banana_pro

from experiments.baseline_gen import VARIANTS_ROOT
from experiments.config import load_benchmark, load_experiment_config
from experiments.layout import ExpLayout

logger = logging.getLogger(__name__)

# 与 quick_create_service.run_quick_create_task_sync 中的参考图指引文案保持一致
_REF_GUIDE_TEXT = "以下是角色参考图，作为你修补任务的重要参考"


def _resolve_refs(character_id: str) -> list:
    refs = standard_reference_paths_for_multimodal_prompt(character_id)
    if not refs:
        raise ValueError(f"角色 {character_id} 标准参考图不足 5 张")
    return refs


def _load_manifest(layout: ExpLayout) -> dict:
    if os.path.isfile(layout.manifest_path()):
        with open(layout.manifest_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": []}


def _save_manifest(layout: ExpLayout, manifest: dict) -> None:
    os.makedirs(os.path.dirname(layout.manifest_path()), exist_ok=True)
    with open(layout.manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _cell_done(manifest: dict, layout: ExpLayout, variant: str,
               seed_id: str, k: int) -> bool:
    for e in manifest["entries"]:
        if (e["variant"], e["seed_id"], e["image_index"]) == (variant, seed_id, k):
            return bool(e.get("ok")) and os.path.isfile(
                os.path.join(layout.root, e["image_path"])
            )
    return False


def _generate_one(job: dict, layout: ExpLayout, gen_image) -> dict:
    content = [{"text": job["prompt_text"]}, {"text": _REF_GUIDE_TEXT}]
    for p in job["refs"]:
        content.append({"picture": p})
    img_dir = layout.image_dir(job["variant"], job["seed_id"])
    file_name = f"img_{job['k']}.png"
    ok = gen_image(
        Content=content,
        output_path=img_dir,
        file_name=file_name,
        aspect_ratio=job["aspect_ratio"],
    )
    rel = os.path.relpath(
        os.path.join(img_dir, file_name), layout.root
    ).replace("\\", "/")
    return {
        "variant": job["variant"], "seed_id": job["seed_id"],
        "image_index": job["k"], "character_id": job["character_id"],
        "image_path": rel, "aspect_ratio": job["aspect_ratio"], "ok": bool(ok),
    }


def run_experiment(config_path: str, results_root: str = "experiments/results",
                   gen_image=generate_image_with_nano_banana_pro) -> dict:
    cfg = load_experiment_config(config_path)
    bench = load_benchmark(cfg.benchmark)
    layout = ExpLayout(results_root, cfg.exp_id)
    manifest = _load_manifest(layout)

    jobs, skipped = [], 0
    for variant in cfg.variants:
        for seed in bench.seeds:
            src = os.path.join(VARIANTS_ROOT, cfg.exp_id, variant,
                               f"{seed.seed_id}.txt")
            with open(src, "r", encoding="utf-8") as f:
                prompt_text = f.read()
            # 发送全文存档
            os.makedirs(layout.prompts_dir(variant), exist_ok=True)
            with open(layout.prompt_path(variant, seed.seed_id), "w",
                      encoding="utf-8") as f:
                f.write(prompt_text)
            refs = _resolve_refs(seed.character_id)
            for k in range(1, cfg.images_per_cell + 1):
                if _cell_done(manifest, layout, variant, seed.seed_id, k):
                    skipped += 1
                    continue
                jobs.append({
                    "variant": variant, "seed_id": seed.seed_id, "k": k,
                    "character_id": seed.character_id,
                    "aspect_ratio": seed.aspect_ratio,
                    "prompt_text": prompt_text, "refs": refs,
                })

    generated = failed = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=cfg.concurrency) as pool:
        futures = {pool.submit(_generate_one, j, layout, gen_image): j
                   for j in jobs}
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                entry = fut.result()
            except Exception as exc:
                logger.error("出图异常 %s/%s#%s: %s", j["variant"],
                             j["seed_id"], j["k"], exc, exc_info=True)
                entry = {
                    "variant": j["variant"], "seed_id": j["seed_id"],
                    "image_index": j["k"], "character_id": j["character_id"],
                    "image_path": "", "aspect_ratio": j["aspect_ratio"],
                    "ok": False,
                }
            with lock:
                manifest["entries"] = [
                    e for e in manifest["entries"]
                    if (e["variant"], e["seed_id"], e["image_index"])
                    != (entry["variant"], entry["seed_id"], entry["image_index"])
                ]
                manifest["entries"].append(entry)
                _save_manifest(layout, manifest)  # 逐张落盘，中断可续
            if entry["ok"]:
                generated += 1
            else:
                failed += 1

    stats = {"generated": generated, "skipped": skipped, "failed": failed}
    logger.info("出图完成: %s", stats)
    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="A/B 实验出图执行器")
    ap.add_argument("--config", required=True)
    ap.add_argument("--results-root", default="experiments/results")
    args = ap.parse_args()
    print(json.dumps(run_experiment(args.config,
                                    results_root=args.results_root),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_runner.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/runner.py
git add -f tests/experiments/test_runner.py
git commit -m "feat(experiments): A/B 出图执行器（并发≤10、断点续跑、全文存档）"
```

---

### Task 10: 自动指标聚合（report.py 第一部分）

聚合 `checks/` 下全部 JSON，按 variant 汇总 5 项自动指标（spec §5.2）：锚点保留率、多腿率、躯干重复率、颈腰扭曲率、背景崩坏率，并给出两组差值（pp）。结论只看 6 种子汇总后的组间差异（spec §7），但同时输出 per-seed 明细供消融排查。

**Files:**
- Create: `experiments/report.py`
- Test: `tests/experiments/test_report_metrics.py`

**Interfaces:**
- Consumes: `ExpLayout`（check JSON 结构见 Task 5）
- Produces:
  - `aggregate_metrics(layout: ExpLayout) -> dict`，结构：

```json
{
  "by_variant": {
    "baseline": {
      "images": 18,
      "multi_leg_rate": 0.22, "torso_dup_rate": 0.06,
      "neck_waist_twist_rate": 0.11, "furniture_broken_rate": 0.17,
      "anchor_retention_rate": 0.74,
      "unparsed": {"leg_count": 0, "torso_dup": 1, "...": 0}
    },
    "slim": {"...": "..."}
  },
  "delta_pp": {"multi_leg_rate": -11.1, "anchor_retention_rate": 8.3, "...": 0},
  "by_seed": {"cas_hard_wsit": {"baseline": {"...": "..."}, "slim": {"...": "..."}}}
}
```

  - 口径：`*_rate` 分母 = 该项解析成功（pass 非 None 且无 error）的图数，分子 = `pass == False` 的图数；`anchor_retention_rate` 分母 = 全部锚点判定次数中 answer 为 yes/no 的（unsure 与 error 不计入），分子 = yes 数。`delta_pp` = (slim − baseline) × 100，方向：崩坏率类负值 = 改善，锚点保留率正值 = 改善（判读交给 final report 与用户）。
  - `write_metrics(layout) -> dict` — 聚合并写 `metrics.json`
  - CLI 子命令（Task 11 一并挂）：`python -m experiments.report metrics --config ...`

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_report_metrics.py
import json
import os

from experiments.layout import ExpLayout
from experiments.report import aggregate_metrics


def _check_doc(variant, seed_id, k, leg_pass, anchors_yes, anchors_total):
    anchors = {}
    for i in range(anchors_total):
        anchors[f"a{i}"] = {"answer": "yes" if i < anchors_yes else "no",
                            "raw": ""}
    return {
        "variant": variant, "seed_id": seed_id, "image_index": k,
        "image_path": f"images/{variant}/{seed_id}/img_{k}.png",
        "character_id": "mchar_x",
        "structure": {
            "leg_count": {"kind": "count", "value": 2 if leg_pass else 4,
                          "pass": leg_pass, "raw": ""},
            "torso_dup": {"kind": "yes_no", "verdict": "no", "reason": "",
                          "pass": True, "raw": ""},
            "neck_waist_twist": {"kind": "yes_no", "verdict": "no",
                                 "reason": "", "pass": True, "raw": ""},
            "furniture_broken": {"kind": "yes_no", "verdict": None,
                                 "reason": "", "pass": None, "raw": ""},
        },
        "anchors": anchors,
    }


def _setup(tmp_path):
    lay = ExpLayout(str(tmp_path), "exp001")
    docs = [
        _check_doc("baseline", "s1", 1, False, 2, 4),  # 多腿；锚点 2/4
        _check_doc("baseline", "s1", 2, True, 4, 4),
        _check_doc("slim", "s1", 1, True, 4, 4),
        _check_doc("slim", "s1", 2, True, 3, 4),
    ]
    for d in docs:
        p = lay.check_path(d["variant"], d["seed_id"], d["image_index"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f)
    return lay


def test_aggregate_metrics(tmp_path):
    lay = _setup(tmp_path)
    m = aggregate_metrics(lay)
    base = m["by_variant"]["baseline"]
    slim = m["by_variant"]["slim"]
    assert base["images"] == 2 and slim["images"] == 2
    assert base["multi_leg_rate"] == 0.5          # 1/2
    assert slim["multi_leg_rate"] == 0.0
    assert base["anchor_retention_rate"] == 0.75  # (2+4)/8
    assert slim["anchor_retention_rate"] == 0.875 # (4+3)/8
    # furniture_broken 全部 pass=None → 分母 0，rate 为 None，unparsed=2
    assert base["furniture_broken_rate"] is None
    assert base["unparsed"]["furniture_broken"] == 2
    assert m["delta_pp"]["multi_leg_rate"] == -50.0
    assert m["delta_pp"]["anchor_retention_rate"] == 12.5
    assert "s1" in m["by_seed"]
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_report_metrics.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现（report.py 先只放聚合部分，CLI main 在 Task 11 补全）**

```python
# experiments/report.py
"""实验报告：自动指标聚合（本文件 Task 10 部分）+ 盲评页与合流报告（Task 11 追加）。"""
import glob
import json
import os

from experiments.layout import ExpLayout

_RATE_KEYS = {
    "leg_count": "multi_leg_rate",
    "torso_dup": "torso_dup_rate",
    "neck_waist_twist": "neck_waist_twist_rate",
    "furniture_broken": "furniture_broken_rate",
}


def _load_check_docs(layout: ExpLayout) -> list:
    docs = []
    pattern = os.path.join(layout.root, "checks", "*.json")
    for p in sorted(glob.glob(pattern)):
        with open(p, "r", encoding="utf-8") as f:
            docs.append(json.load(f))
    return docs


def _variant_metrics(docs: list) -> dict:
    out = {"images": len(docs), "unparsed": {}}
    for check_id, rate_key in _RATE_KEYS.items():
        parsed = fail = unparsed = 0
        for d in docs:
            item = d.get("structure", {}).get(check_id, {})
            p = item.get("pass")
            if "error" in item or p is None:
                unparsed += 1
            else:
                parsed += 1
                if p is False:
                    fail += 1
        out[rate_key] = round(fail / parsed, 4) if parsed else None
        out["unparsed"][check_id] = unparsed
    yes = judged = 0
    for d in docs:
        for a in d.get("anchors", {}).values():
            ans = a.get("answer")
            if ans in ("yes", "no"):
                judged += 1
                if ans == "yes":
                    yes += 1
    out["anchor_retention_rate"] = round(yes / judged, 4) if judged else None
    return out


def aggregate_metrics(layout: ExpLayout) -> dict:
    docs = _load_check_docs(layout)
    by_variant_docs, by_seed_docs = {}, {}
    for d in docs:
        by_variant_docs.setdefault(d["variant"], []).append(d)
        by_seed_docs.setdefault(d["seed_id"], {}).setdefault(
            d["variant"], []).append(d)

    by_variant = {v: _variant_metrics(ds) for v, ds in by_variant_docs.items()}
    delta_pp = {}
    base, slim = by_variant.get("baseline"), by_variant.get("slim")
    if base and slim:
        for key in list(_RATE_KEYS.values()) + ["anchor_retention_rate"]:
            b, s = base.get(key), slim.get(key)
            delta_pp[key] = (round((s - b) * 100, 1)
                             if b is not None and s is not None else None)
    by_seed = {
        seed_id: {v: _variant_metrics(ds) for v, ds in variants.items()}
        for seed_id, variants in by_seed_docs.items()
    }
    return {"by_variant": by_variant, "delta_pp": delta_pp, "by_seed": by_seed}


def write_metrics(layout: ExpLayout) -> dict:
    metrics = aggregate_metrics(layout)
    with open(layout.metrics_path(), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return metrics
```

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_report_metrics.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/report.py
git add -f tests/experiments/test_report_metrics.py
git commit -m "feat(experiments): 自动指标聚合（5 项指标 + 组间差值 + per-seed 明细）"
```

---

### Task 11: 人工盲评页 + 合流报告（report.py 第二部分）

spec §4 决策 5：review.html 纯静态单文件、图片相对路径、图片乱序且不显示所属变体（`review_shuffle_seed` 固定乱序保证可复现）、每图三组评分（脸部/锚点/腿脚袜各三档）+ 自由备注、导出 JSON。合流：`final` 子命令读 metrics.json + 用户盲评导出 JSON，反乱序映射回 variant，生成 final_report.md（含 spec §7 预注册结论标准表，供用户对照判读——工具不自动下结论）。

**Files:**
- Modify: `experiments/report.py`（追加 review/final/CLI）
- Test: `tests/experiments/test_report_review.py`

**Interfaces:**
- Consumes: `aggregate_metrics / write_metrics`（Task 10）、manifest.json、`load_experiment_config`
- Produces:
  - `build_review_html(layout, manifest_entries, shuffle_seed) -> str` — 写 review.html；图片按乱序编号**匿名复制**到 `review_images/R001.png ...`（原始路径含变体名会泄漏分组，绝不能直接引用）；同时写 `review_key.json`（`{"R001": {"variant","seed_id","image_index"}}` 的乱序编号→真实身份映射；该文件留在 results 内，盲评时用户不打开它）
  - 盲评导出 JSON 格式（review.html 内嵌 JS 生成下载）：`{"R001": {"face": "ok|minor|broken", "anchor": "full|partial|lost", "leg": "ok|minor|broken", "note": ""}}`
  - `build_final_report(layout, ratings_path: str) -> str` — 写 final_report.md，含：自动指标表、人工盲评按 variant 汇总表（脸部崩坏率 = face==broken 占比等）、预注册结论标准原文
  - CLI: `python -m experiments.report {metrics|review|final} --config ... [--ratings ...]`

- [ ] **Step 1: 写失败测试**

```python
# tests/experiments/test_report_review.py
import json
import os

from experiments.layout import ExpLayout
from experiments.report import build_final_report, build_review_html


def _entries():
    out = []
    for variant in ("baseline", "slim"):
        for k in (1, 2):
            out.append({
                "variant": variant, "seed_id": "s1", "image_index": k,
                "character_id": "mchar_x",
                "image_path": f"images/{variant}/s1/img_{k}.png",
                "aspect_ratio": "4:3", "ok": True,
            })
    return out


def test_build_review_html_blind_and_reproducible(tmp_path):
    lay = ExpLayout(str(tmp_path), "exp001")
    for e in _entries():  # 物理图片文件需存在（build 时会复制为匿名名）
        p = os.path.join(lay.root, e["image_path"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"png")
    html1 = build_review_html(lay, _entries(), shuffle_seed=42)
    html2 = build_review_html(lay, _entries(), shuffle_seed=42)
    assert html1 == html2                        # 同种子乱序可复现
    # 盲评：HTML 与图片引用路径均不得泄漏变体（原始路径含 variant 名，必须匿名化复制）
    assert "baseline" not in html1 and "slim" not in html1
    assert html1.count("review_images/") == 4
    assert os.path.isfile(os.path.join(lay.root, "review_images", "R001.png"))
    assert os.path.isfile(lay.review_html_path())
    with open(os.path.join(lay.root, "review_key.json"), encoding="utf-8") as f:
        key = json.load(f)
    assert len(key) == 4
    assert {v["variant"] for v in key.values()} == {"baseline", "slim"}


def test_build_final_report(tmp_path):
    lay = ExpLayout(str(tmp_path), "exp001")
    for e in _entries():
        p = os.path.join(lay.root, e["image_path"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"png")
    build_review_html(lay, _entries(), shuffle_seed=42)
    with open(lay.metrics_path(), "w", encoding="utf-8") as f:
        json.dump({"by_variant": {}, "delta_pp": {}, "by_seed": {}}, f)
    with open(os.path.join(lay.root, "review_key.json"), encoding="utf-8") as f:
        key = json.load(f)
    ratings = {}
    for rid, ident in key.items():
        broken = ident["variant"] == "baseline"
        ratings[rid] = {"face": "broken" if broken else "ok",
                        "anchor": "full", "leg": "ok", "note": ""}
    ratings_p = os.path.join(str(tmp_path), "ratings.json")
    with open(ratings_p, "w", encoding="utf-8") as f:
        json.dump(ratings, f)

    md = build_final_report(lay, ratings_p)
    assert os.path.isfile(lay.final_report_path())
    assert "预注册结论标准" in md
    assert "100.0%" in md   # baseline 脸部崩坏率 2/2
    assert "0.0%" in md     # slim 0/2
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/experiments/test_report_review.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现（追加到 experiments/report.py）**

```python
import argparse
import random

_RATING_GROUPS = [
    ("face", "脸部", [("ok", "正常"), ("minor", "轻微异常"), ("broken", "崩坏")]),
    ("anchor", "锚点", [("full", "齐全"), ("partial", "部分丢失"), ("lost", "严重丢失")]),
    ("leg", "腿脚袜", [("ok", "正常"), ("minor", "轻微异常"), ("broken", "崩坏")]),
]

_PREREG_TABLE = """## 预注册结论标准（spec §7，先于看数据承诺）

| 结果 | 判定 |
|---|---|
| 任一核心指标（脸部崩坏率/腿脚崩坏率/锚点保留率）改善 ≥ 20pp | 显著改善 → 采纳瘦身、进入第二阶段专项 |
| 主要指标全部改善 < 10pp | 改善有限 → 转入架构重写路线 |
| 任何指标恶化 ≥ 15pp | 触发对应规则的消融排查 |
| 中间情况 | 用户结合看图主观判断 |
"""


def build_review_html(layout: ExpLayout, manifest_entries: list,
                      shuffle_seed: int) -> str:
    entries = [e for e in manifest_entries if e.get("ok")]
    rng = random.Random(shuffle_seed)
    rng.shuffle(entries)
    # 盲评关键：原始 image_path 含变体名，必须复制为匿名文件名后引用
    review_img_dir = os.path.join(layout.root, "review_images")
    os.makedirs(review_img_dir, exist_ok=True)
    key = {}
    cards = []
    for i, e in enumerate(entries, start=1):
        rid = f"R{i:03d}"
        key[rid] = {"variant": e["variant"], "seed_id": e["seed_id"],
                    "image_index": e["image_index"]}
        src = os.path.join(layout.root, e["image_path"])
        shutil.copyfile(src, os.path.join(review_img_dir, f"{rid}.png"))
        radios = []
        for field, label, options in _RATING_GROUPS:
            opts = "".join(
                f'<label><input type="radio" name="{rid}_{field}" '
                f'value="{val}">{text}</label> '
                for val, text in options
            )
            radios.append(f"<div><b>{label}</b>：{opts}</div>")
        cards.append(
            f'<div class="card" id="{rid}"><h3>{rid}</h3>'
            f'<img src="review_images/{rid}.png" loading="lazy">'
            + "".join(radios)
            + f'<textarea name="{rid}_note" placeholder="备注"></textarea></div>'
        )
    html = (
        "<!DOCTYPE html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
        "<title>exp 盲评</title><style>"
        ".card{border:1px solid #ccc;margin:16px;padding:12px}"
        "img{max-width:720px;display:block;margin-bottom:8px}"
        "textarea{width:100%;margin-top:6px}"
        "</style></head><body><h1>盲评（图片已乱序，不显示分组）</h1>"
        "<p>逐图三组评分后点击底部按钮导出 JSON。</p>"
        + "".join(cards) +
        "<button onclick=\"exportRatings()\">导出评分 JSON</button>"
        "<script>\n"
        "function exportRatings(){\n"
        "  const out={};\n"
        "  document.querySelectorAll('.card').forEach(c=>{\n"
        "    const rid=c.id; const r={note:c.querySelector('textarea').value};\n"
        "    ['face','anchor','leg'].forEach(f=>{\n"
        "      const el=c.querySelector(`input[name='${rid}_${f}']:checked`);\n"
        "      r[f]=el?el.value:null;});\n"
        "    out[rid]=r;});\n"
        "  const a=document.createElement('a');\n"
        "  a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],"
        "{type:'application/json'}));\n"
        "  a.download='ratings.json'; a.click();\n"
        "}\n</script></body></html>"
    )
    with open(layout.review_html_path(), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(layout.root, "review_key.json"), "w",
              encoding="utf-8") as f:
        json.dump(key, f, ensure_ascii=False, indent=2)
    return html


def _rating_rates(ratings: dict, key: dict) -> dict:
    """按 variant 汇总人工盲评：崩坏率 = broken/lost 档占已评图数比例。"""
    by_variant = {}
    for rid, r in ratings.items():
        ident = key.get(rid)
        if not ident:
            continue
        d = by_variant.setdefault(ident["variant"],
                                  {"n": 0, "face_broken": 0,
                                   "anchor_lost": 0, "leg_broken": 0})
        d["n"] += 1
        if r.get("face") == "broken":
            d["face_broken"] += 1
        if r.get("anchor") == "lost":
            d["anchor_lost"] += 1
        if r.get("leg") == "broken":
            d["leg_broken"] += 1
    out = {}
    for v, d in by_variant.items():
        n = d["n"] or 1
        out[v] = {
            "rated": d["n"],
            "face_broken_rate": d["face_broken"] / n,
            "anchor_lost_rate": d["anchor_lost"] / n,
            "leg_broken_rate": d["leg_broken"] / n,
        }
    return out


def build_final_report(layout: ExpLayout, ratings_path: str) -> str:
    with open(layout.metrics_path(), "r", encoding="utf-8") as f:
        metrics = json.load(f)
    with open(os.path.join(layout.root, "review_key.json"), "r",
              encoding="utf-8") as f:
        key = json.load(f)
    with open(ratings_path, "r", encoding="utf-8") as f:
        ratings = json.load(f)

    human = _rating_rates(ratings, key)
    lines = ["# 实验合流报告", "", "## 自动指标（checker）", "",
             "```json", json.dumps(metrics, ensure_ascii=False, indent=2),
             "```", "", "## 人工盲评汇总", "",
             "| 变体 | 已评图数 | 脸部崩坏率 | 锚点严重丢失率 | 腿脚袜崩坏率 |",
             "|---|---|---|---|---|"]
    for v in sorted(human):
        d = human[v]
        lines.append(
            f"| {v} | {d['rated']} | {d['face_broken_rate']:.1%} "
            f"| {d['anchor_lost_rate']:.1%} | {d['leg_broken_rate']:.1%} |"
        )
    lines += ["", _PREREG_TABLE, "",
              "> 结论判读：请将上表数据对照预注册标准，由用户结合盲评观感最终定论。"]
    md = "\n".join(lines)
    with open(layout.final_report_path(), "w", encoding="utf-8") as f:
        f.write(md)
    return md


def main() -> None:
    from experiments.config import load_experiment_config

    ap = argparse.ArgumentParser(description="实验报告工具")
    ap.add_argument("command", choices=["metrics", "review", "final"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--results-root", default="experiments/results")
    ap.add_argument("--ratings", help="final 命令：盲评导出的 ratings.json 路径")
    args = ap.parse_args()
    cfg = load_experiment_config(args.config)
    layout = ExpLayout(args.results_root, cfg.exp_id)

    if args.command == "metrics":
        print(json.dumps(write_metrics(layout), ensure_ascii=False, indent=2))
    elif args.command == "review":
        with open(layout.manifest_path(), "r", encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        build_review_html(layout, entries, cfg.review_shuffle_seed)
        print(f"盲评页已生成: {layout.review_html_path()}")
    else:
        if not args.ratings:
            ap.error("final 需要 --ratings")
        build_final_report(layout, args.ratings)
        print(f"合流报告已生成: {layout.final_report_path()}")


if __name__ == "__main__":
    main()
```

（`import argparse` / `import random` / `import shutil` 放到文件顶部与既有 import 合并。）

- [ ] **Step 4: 运行确认通过**

Run: `pytest tests/experiments/test_report_review.py tests/experiments/test_report_metrics.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add experiments/report.py
git add -f tests/experiments/test_report_review.py
git commit -m "feat(experiments): 人工盲评页与合流报告（乱序盲评+预注册标准）"
```

---

### Task 12: 收尾——全量回归 + 文档 + 使用说明

**Files:**
- Create: `experiments/README.md`
- Modify: `docs/creation_pipeline.md`（§12 关联文档追加一行）

**Interfaces:** 无新代码。

- [ ] **Step 1: 全量测试回归**

Run: `pytest tests/experiments/ -v && pytest -q`
Expected: experiments 全部通过；既有测试无回归（基线失败数与改动前一致）。

- [ ] **Step 2: 写 experiments/README.md**

```markdown
# experiments/ — 出图质量 A/B 实验层

设计文档：`docs/superpowers/specs/2026-07-05-creation-prompt-ab-experiment-design.md`

## exp001 完整操作顺序（生产环境执行 1–4，本地执行 5–7）

1. checker 校准（首次）：准备校准集 YAML（历史崩坏/正常图 + 真值标注）后
   `python -m experiments.checker.calibrate --calib <calib.yaml> --out experiments/results/calibration_report.json`
   不达标项（如多腿检出 < 90%）降级人工评判。
2. 基线冻结：`python -m experiments.baseline_gen --config experiments/configs/exp001.yaml`
   产物 `experiments/variants/exp001/baseline/*.txt` 需 git 提交；瘦身版由人工改写后放入
   `experiments/variants/exp001/slim/`（同名文件），经用户过目后提交。
3. 出图：`python -m experiments.runner --config experiments/configs/exp001.yaml`
   （并发 ≤ 10；中断后重跑自动续）
4. 核对：`python -m experiments.checker.run_checks --config experiments/configs/exp001.yaml`
5. 把 `experiments/results/exp001/` 整目录打包拷回本地。
6. 本地：`python -m experiments.report metrics --config ...` →
   `python -m experiments.report review --config ...` → 浏览器打开 review.html 盲评并导出 ratings.json
   （盲评期间不要打开 review_key.json）。
7. 合流：`python -m experiments.report final --config ... --ratings <ratings.json>`
   → `final_report.md` 对照预注册标准定论。

所有命令从仓库根运行（依赖 `app.*` 导入与 `app/tools/llm/config.py`）。
```

- [ ] **Step 3: docs/creation_pipeline.md §12 关联文档追加**

```markdown
- 出图质量 A/B 实验体系（experiments/ 层）：[`docs/superpowers/specs/2026-07-05-creation-prompt-ab-experiment-design.md`](superpowers/specs/2026-07-05-creation-prompt-ab-experiment-design.md)，操作手册见仓库根 `experiments/README.md`
```

- [ ] **Step 4: 提交**

```bash
git add experiments/README.md docs/creation_pipeline.md
git commit -m "docs(experiments): exp001 操作手册与流程文档关联"
```

---

## 计划外（执行阶段人工/用户环节，非编码任务）

1. **用户审定** fixtures（Task 7 产物：6 种子 + 两角色锚点清单）。
2. **用户挑选并标注**校准集图片（每类崩坏/正常 10–20 张），写 calibration YAML。
3. **Claude 离线人工改写**瘦身版 Prompt（6 规则逐份应用，红线不破），产物放 `experiments/variants/exp001/slim/`，**用户过目后**提交。case1/case2 基线用生产原文，直接落 `baseline/cas_hard_wsit.txt` 与 `baseline/hys_hard_bubble.txt`（baseline_gen 冻结语义自动跳过它们）。
4. 生产环境跑 exp001 → 打包拷回 → 盲评 → 合流定论 → 决定第二阶段路线。

## Self-Review 结论

- **Spec 覆盖**：§4 运行器（Task 1/8/9）、§5.1–5.2 checker（Task 3/4/5）、§5.4 校准（Task 6）、§5.5 并发（config 上限 + ThreadPoolExecutor）、§6 瘦身（执行阶段人工环节 3）、§7 基准集/对照/预注册标准（Task 7/9/11）、盲评防偏见（Task 11 乱序 + 不显示变体）——全部有对应任务。§4 决策 1（git 同步生产运行）由 .gitignore + README 操作顺序承载。
- **一致性**：manifest/check JSON 字段名在 Task 5/9/10/11 间已交叉核对（`variant/seed_id/image_index/image_path/character_id/ok`）；`ExpLayout` 方法名在各任务引用一致；`VARIANTS_ROOT` 由 Task 8 定义、Task 9 消费。
- **占位符**：无 TBD/TODO；所有代码步骤含完整代码。
