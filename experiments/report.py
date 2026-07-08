"""实验报告：自动指标聚合（本文件 Task 10 部分）+ 盲评页与合流报告（Task 11 追加）。"""
import argparse
import glob
import json
import os
import random
import shutil

from experiments.layout import ExpLayout

_RATE_KEYS = {
    "leg_count": "multi_leg_rate",
    "torso_dup": "torso_dup_rate",
    "neck_waist_twist": "neck_waist_twist_rate",
    "furniture_broken": "furniture_broken_rate",
}


def _load_check_docs(layout: ExpLayout) -> list:
    docs = []
    pattern = os.path.join(layout.root, "checks", "*.json")
    for p in sorted(glob.glob(pattern)):
        with open(p, "r", encoding="utf-8") as f:
            docs.append(json.load(f))
    return docs


def _variant_metrics(docs: list) -> dict:
    out = {"images": len(docs), "unparsed": {}}
    for check_id, rate_key in _RATE_KEYS.items():
        parsed = fail = unparsed = 0
        for d in docs:
            item = d.get("structure", {}).get(check_id, {})
            p = item.get("pass")
            if "error" in item or p is None:
                unparsed += 1
            else:
                parsed += 1
                if p is False:
                    fail += 1
        out[rate_key] = round(fail / parsed, 4) if parsed else None
        out["unparsed"][check_id] = unparsed
    yes = judged = 0
    for d in docs:
        for a in d.get("anchors", {}).values():
            ans = a.get("answer")
            if ans in ("yes", "no"):
                judged += 1
                if ans == "yes":
                    yes += 1
    out["anchor_retention_rate"] = round(yes / judged, 4) if judged else None
    return out


def aggregate_metrics(layout: ExpLayout) -> dict:
    docs = _load_check_docs(layout)
    by_variant_docs, by_seed_docs = {}, {}
    for d in docs:
        by_variant_docs.setdefault(d["variant"], []).append(d)
        by_seed_docs.setdefault(d["seed_id"], {}).setdefault(
            d["variant"], []).append(d)

    by_variant = {v: _variant_metrics(ds) for v, ds in by_variant_docs.items()}
    delta_pp = {}
    base, slim = by_variant.get("baseline"), by_variant.get("slim")
    if base and slim:
        for key in list(_RATE_KEYS.values()) + ["anchor_retention_rate"]:
            b, s = base.get(key), slim.get(key)
            delta_pp[key] = (round((s - b) * 100, 1)
                             if b is not None and s is not None else None)
    by_seed = {
        seed_id: {v: _variant_metrics(ds) for v, ds in variants.items()}
        for seed_id, variants in by_seed_docs.items()
    }
    return {"by_variant": by_variant, "delta_pp": delta_pp, "by_seed": by_seed}


def write_metrics(layout: ExpLayout) -> dict:
    metrics = aggregate_metrics(layout)
    with open(layout.metrics_path(), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return metrics


_RATING_GROUPS = [
    ("face", "脸部", [("ok", "正常"), ("minor", "轻微异常"), ("broken", "崩坏")]),
    ("anchor", "锚点", [("full", "齐全"), ("partial", "部分丢失"), ("lost", "严重丢失")]),
    ("leg", "腿脚袜", [("ok", "正常"), ("minor", "轻微异常"), ("broken", "崩坏")]),
]

_PREREG_TABLE = """## 预注册结论标准（spec §7，先于看数据承诺）

| 结果 | 判定 |
|---|---|
| 任一核心指标（脸部崩坏率/腿脚崩坏率/锚点保留率）改善 ≥ 20pp | 显著改善 → 采纳瘦身、进入第二阶段专项 |
| 主要指标全部改善 < 10pp | 改善有限 → 转入架构重写路线 |
| 任何指标恶化 ≥ 15pp | 触发对应规则的消融排查 |
| 中间情况 | 用户结合看图主观判断 |
"""


# 盲评页脚本：评分实时自动保存到浏览器 localStorage（按实验 ID 隔离），
# 重新打开页面自动恢复；也可通过"导入评分 JSON"从此前导出的文件续评。
_REVIEW_SCRIPT = """
const KEY='blindReview:__EXP_ID__';
const TOTAL=__TOTAL__;
function collectRatings(){
  const out={};
  document.querySelectorAll('.card').forEach(c=>{
    const rid=c.id; const r={note:c.querySelector('textarea').value};
    ['face','anchor','leg'].forEach(f=>{
      const el=c.querySelector(`input[name='${rid}_${f}']:checked`);
      r[f]=el?el.value:null;});
    out[rid]=r;});
  return out;
}
function applyRatings(data){
  for(const [rid,r] of Object.entries(data)){
    const c=document.getElementById(rid); if(!c) continue;
    c.querySelector('textarea').value=r.note||'';
    ['face','anchor','leg'].forEach(f=>{
      if(!r[f]) return;
      const el=c.querySelector(`input[name='${rid}_${f}'][value='${r[f]}']`);
      if(el) el.checked=true;});
  }
}
function saveProgress(){
  try{localStorage.setItem(KEY,JSON.stringify(collectRatings()));}
  catch(e){document.getElementById('status').textContent='自动保存失败：'+e;return;}
  updateStatus();
}
function updateStatus(){
  let done=0;
  Object.values(collectRatings()).forEach(r=>{
    if(r.face&&r.anchor&&r.leg)done++;});
  document.getElementById('status').textContent=
    `已完成 ${done}/${TOTAL}（进度实时自动保存，可关页续评）`;
}
function importRatings(ev){
  const f=ev.target.files[0]; if(!f) return;
  const rd=new FileReader();
  rd.onload=()=>{
    try{applyRatings(JSON.parse(rd.result));}
    catch(e){alert('导入失败：'+e);return;}
    saveProgress();};
  rd.readAsText(f);
  ev.target.value='';
}
function clearProgress(){
  if(!confirm('确定清空本页所有评分与备注？此操作不可撤销。'))return;
  localStorage.removeItem(KEY);
  document.querySelectorAll('.card input[type=radio]').forEach(el=>el.checked=false);
  document.querySelectorAll('.card textarea').forEach(el=>el.value='');
  updateStatus();
}
function exportRatings(){
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([JSON.stringify(collectRatings(),null,2)],{type:'application/json'}));
  a.download='ratings.json'; a.click();
}
window.addEventListener('load',()=>{
  const s=localStorage.getItem(KEY);
  if(s){try{applyRatings(JSON.parse(s));}catch(e){}}
  updateStatus();
  document.body.addEventListener('change',saveProgress);
  document.body.addEventListener('input',ev=>{
    if(ev.target.tagName==='TEXTAREA')saveProgress();});
});
"""


def build_review_html(layout: ExpLayout, manifest_entries: list,
                      shuffle_seed: int) -> str:
    entries = [e for e in manifest_entries if e.get("ok")]
    rng = random.Random(shuffle_seed)
    rng.shuffle(entries)
    # 盲评关键：原始 image_path 含变体名，必须复制为匿名文件名后引用
    review_img_dir = os.path.join(layout.root, "review_images")
    os.makedirs(review_img_dir, exist_ok=True)
    key = {}
    cards = []
    for i, e in enumerate(entries, start=1):
        rid = f"R{i:03d}"
        key[rid] = {"variant": e["variant"], "seed_id": e["seed_id"],
                    "image_index": e["image_index"]}
        src = os.path.join(layout.root, e["image_path"])
        shutil.copyfile(src, os.path.join(review_img_dir, f"{rid}.png"))
        radios = []
        for field, label, options in _RATING_GROUPS:
            opts = "".join(
                f'<label><input type="radio" name="{rid}_{field}" '
                f'value="{val}">{text}</label> '
                for val, text in options
            )
            radios.append(f"<div><b>{label}</b>：{opts}</div>")
        cards.append(
            f'<div class="card" id="{rid}"><h3>{rid}</h3>'
            f'<img src="review_images/{rid}.png" loading="lazy">'
            + "".join(radios)
            + f'<textarea name="{rid}_note" placeholder="备注"></textarea></div>'
        )
    exp_id = os.path.basename(layout.root)
    script = (_REVIEW_SCRIPT
              .replace("__EXP_ID__", exp_id)
              .replace("__TOTAL__", str(len(entries))))
    html = (
        "<!DOCTYPE html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
        "<title>exp 盲评</title><style>"
        ".card{border:1px solid #ccc;margin:16px;padding:12px}"
        "img{max-width:720px;display:block;margin-bottom:8px}"
        "textarea{width:100%;margin-top:6px}"
        "#toolbar{position:sticky;top:0;background:#fff;padding:8px 16px;"
        "border-bottom:1px solid #ccc;z-index:1}"
        "</style></head><body>"
        "<div id=\"toolbar\"><span id=\"status\"></span> "
        "<button onclick=\"exportRatings()\">导出评分 JSON</button> "
        "<label style=\"cursor:pointer\"><u>导入评分 JSON</u>"
        "<input type=\"file\" accept=\".json\" style=\"display:none\" "
        "onchange=\"importRatings(event)\"></label> "
        "<button onclick=\"clearProgress()\">清空评分</button></div>"
        "<h1>盲评（图片已乱序，不显示分组）</h1>"
        "<p>逐图三组评分，进度实时自动保存在本浏览器；全部评完后点击「导出评分 JSON」。</p>"
        + "".join(cards) +
        "<button onclick=\"exportRatings()\">导出评分 JSON</button>"
        "<script>" + script + "</script></body></html>"
    )
    with open(layout.review_html_path(), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(layout.root, "review_key.json"), "w",
              encoding="utf-8") as f:
        json.dump(key, f, ensure_ascii=False, indent=2)
    return html


def _rating_rates(ratings: dict, key: dict) -> dict:
    """按 variant 汇总人工盲评：崩坏率 = broken/lost 档占已评图数比例。"""
    by_variant = {}
    for rid, r in ratings.items():
        ident = key.get(rid)
        if not ident:
            continue
        d = by_variant.setdefault(ident["variant"],
                                  {"n": 0, "face_broken": 0,
                                   "anchor_lost": 0, "leg_broken": 0})
        d["n"] += 1
        if r.get("face") == "broken":
            d["face_broken"] += 1
        if r.get("anchor") == "lost":
            d["anchor_lost"] += 1
        if r.get("leg") == "broken":
            d["leg_broken"] += 1
    out = {}
    for v, d in by_variant.items():
        n = d["n"] or 1
        out[v] = {
            "rated": d["n"],
            "face_broken_rate": d["face_broken"] / n,
            "anchor_lost_rate": d["anchor_lost"] / n,
            "leg_broken_rate": d["leg_broken"] / n,
        }
    return out


def build_final_report(layout: ExpLayout, ratings_path: str) -> str:
    with open(layout.metrics_path(), "r", encoding="utf-8") as f:
        metrics = json.load(f)
    with open(os.path.join(layout.root, "review_key.json"), "r",
              encoding="utf-8") as f:
        key = json.load(f)
    with open(ratings_path, "r", encoding="utf-8") as f:
        ratings = json.load(f)

    human = _rating_rates(ratings, key)
    lines = ["# 实验合流报告", "", "## 自动指标（checker）", "",
             "```json", json.dumps(metrics, ensure_ascii=False, indent=2),
             "```", "", "## 人工盲评汇总", "",
             "| 变体 | 已评图数 | 脸部崩坏率 | 锚点严重丢失率 | 腿脚袜崩坏率 |",
             "|---|---|---|---|---|"]
    for v in sorted(human):
        d = human[v]
        lines.append(
            f"| {v} | {d['rated']} | {d['face_broken_rate']:.1%} "
            f"| {d['anchor_lost_rate']:.1%} | {d['leg_broken_rate']:.1%} |"
        )
    lines += ["", _PREREG_TABLE, "",
              "> 结论判读：请将上表数据对照预注册标准，由用户结合盲评观感最终定论。"]
    md = "\n".join(lines)
    with open(layout.final_report_path(), "w", encoding="utf-8") as f:
        f.write(md)
    return md


def main() -> None:
    from experiments.config import load_experiment_config

    ap = argparse.ArgumentParser(description="实验报告工具")
    ap.add_argument("command", choices=["metrics", "review", "final"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--results-root", default="experiments/results")
    ap.add_argument("--ratings", help="final 命令：盲评导出的 ratings.json 路径")
    args = ap.parse_args()
    cfg = load_experiment_config(args.config)
    layout = ExpLayout(args.results_root, cfg.exp_id)

    if args.command == "metrics":
        print(json.dumps(write_metrics(layout), ensure_ascii=False, indent=2))
    elif args.command == "review":
        with open(layout.manifest_path(), "r", encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        build_review_html(layout, entries, cfg.review_shuffle_seed)
        print(f"盲评页已生成: {layout.review_html_path()}")
    else:
        if not args.ratings:
            ap.error("final 需要 --ratings")
        build_final_report(layout, args.ratings)
        print(f"合流报告已生成: {layout.final_report_path()}")


if __name__ == "__main__":
    main()
