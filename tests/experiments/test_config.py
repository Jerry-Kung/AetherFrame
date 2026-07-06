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
