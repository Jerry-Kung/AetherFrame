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
            return "3" if os.path.normpath(image_path[0]) == os.path.normpath(img1) else "2"
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
