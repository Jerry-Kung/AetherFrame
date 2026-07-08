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


def test_build_review_html_has_progress_persistence(tmp_path):
    """盲评页须支持保存进度：localStorage 按实验 ID 隔离、自动恢复、可导入续评。"""
    lay = ExpLayout(str(tmp_path), "exp001")
    for e in _entries():
        p = os.path.join(lay.root, e["image_path"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"png")
    html = build_review_html(lay, _entries(), shuffle_seed=42)
    # 存储 key 含实验 ID（多实验共用浏览器时进度互不覆盖）
    assert "blindReview:exp001" in html
    # 自动保存 + 打开自动恢复 + 导入导出 + 清空
    assert "localStorage.setItem" in html
    assert "localStorage.getItem" in html
    assert "importRatings" in html and "exportRatings" in html
    assert "clearProgress" in html
    # 进度计数用实际条目数
    assert "TOTAL=4" in html


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
