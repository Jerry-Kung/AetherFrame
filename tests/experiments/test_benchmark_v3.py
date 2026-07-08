"""benchmark_v3（12 角色广覆盖）与 exp002 指向校验。角色档案存在性依赖
MATERIAL_CHARACTERS_DIR 指向生产拷贝，仅在该目录存在时校验（本地/CI 无数据时跳过）。"""
import os

import pytest

from experiments.config import load_benchmark, load_experiment_config

BENCH = "experiments/fixtures/benchmark_v3.yaml"
CFG = "experiments/configs/exp002.yaml"
PROD_CHARS = os.path.join("data", "material", "characters_production", "characters")


def test_benchmark_v3_loads_and_validates():
    bench = load_benchmark(BENCH)
    assert len(bench.seeds) == 12
    assert len(bench.characters) == 12


def test_benchmark_v3_one_seed_per_character():
    bench = load_benchmark(BENCH)
    assert len({s.character_id for s in bench.seeds}) == 12


def test_benchmark_v3_covers_difficulty_gradient():
    bench = load_benchmark(BENCH)
    by_diff = {}
    for s in bench.seeds:
        by_diff[s.difficulty] = by_diff.get(s.difficulty, 0) + 1
    assert by_diff == {"easy": 3, "medium": 4, "hard": 5}


def test_benchmark_v3_keeps_continuity_seeds():
    bench = load_benchmark(BENCH)
    ids = {s.seed_id for s in bench.seeds}
    assert {"cas_hard_kneel_sock", "hys_hard_bubble"} <= ids


def test_benchmark_v3_every_seed_mentions_socks():
    bench = load_benchmark(BENCH)
    # hys_hard_bubble 为 v1 冻结连续性文本（不含袜子描述，袜型由模板强制项兜底），豁免
    exempt = {"hys_hard_bubble"}
    for s in bench.seeds:
        if s.seed_id in exempt:
            continue
        assert "袜" in s.text, f"种子 {s.seed_id} 未指定袜子（腿脚高危基准必填）"


def test_exp002_config_points_to_v3():
    cfg = load_experiment_config(CFG)
    assert cfg.benchmark == BENCH
    assert cfg.variants == ["control", "rulepack"]
    assert cfg.images_per_cell == 5


@pytest.mark.skipif(not os.path.isdir(PROD_CHARS),
                    reason="生产角色拷贝目录不存在（仅数据就位的机器上校验）")
def test_benchmark_v3_characters_have_profile_and_slots():
    bench = load_benchmark(BENCH)
    for cid in {s.character_id for s in bench.seeds}:
        profile = os.path.join(PROD_CHARS, cid, "chara_profile",
                               "chara_profile_final.md")
        slots = os.path.join(PROD_CHARS, cid, "standard_photo_slots")
        assert os.path.isfile(profile), f"{cid} 缺 chara_profile_final.md"
        assert os.path.isdir(slots) and len(os.listdir(slots)) == 5, \
            f"{cid} 标准参考图槽位不足 5"
