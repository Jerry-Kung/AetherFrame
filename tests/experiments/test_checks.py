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
