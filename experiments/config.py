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
