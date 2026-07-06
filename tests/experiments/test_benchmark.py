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
