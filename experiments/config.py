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
