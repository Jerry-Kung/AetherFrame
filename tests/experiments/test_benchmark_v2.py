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
