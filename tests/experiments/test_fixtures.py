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
