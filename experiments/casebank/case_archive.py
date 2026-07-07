"""实验结果 → 结构化 Case 归档。图片不落盘；预填 [meta]+种子+出图 Prompt，
feedback/tags 留空待用户手工填写（设计文档 §2.1、feedback-case-data-first 记忆）。"""
import json
import os

from experiments.casebank.case_format import Case, serialize_cases


def _load_json(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_cases(layout, benchmark, source, date, ratings=None, key=None):
    with open(layout.manifest_path(), "r", encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    seed_by_id = {s.seed_id: s for s in benchmark.seeds}
    char_name = {}
    for name, meta in benchmark.characters.items():
        char_name[str(meta["character_id"])] = name

    # (variant, seed) -> ok 图数
    cell_images = {}
    for e in entries:
        if not e.get("ok"):
            continue
        cell_images.setdefault((e["variant"], e["seed_id"]), 0)
        cell_images[(e["variant"], e["seed_id"])] += 1

    # (variant, seed) -> [bad_count, [notes]]  由盲评 ratings+key 汇总
    cell_bad = {}
    cell_notes = {}
    if ratings and key:
        for rid, ident in key.items():
            r = ratings.get(rid, {})
            ck = (ident["variant"], ident["seed_id"])
            if r.get("leg") == "broken":
                cell_bad[ck] = cell_bad.get(ck, 0) + 1
            note = (r.get("note") or "").strip()
            if note:
                cell_notes.setdefault(ck, []).append(note)

    cases = []
    idx = 0
    for (variant, seed_id), n_img in sorted(cell_images.items()):
        idx += 1
        seed = seed_by_id.get(seed_id)
        with open(layout.prompt_path(variant, seed_id), "r",
                  encoding="utf-8") as f:
            final_prompt = f.read().rstrip("\n")
        ck = (variant, seed_id)
        cases.append(Case(
            case_id=f"Case_{source}_{idx:02d}",
            date=date, source=source,
            character=char_name.get(seed.character_id, "") if seed else "",
            seed_id=seed_id,
            difficulty=seed.difficulty if seed else "",
            variant=variant, images=n_img,
            bad=cell_bad.get(ck, 0), tags=[], taxonomy_version="v1",
            seed_prompt=seed.text if seed else "",
            final_prompt=final_prompt,
            feedback="\n".join(cell_notes.get(ck, [])),
        ))
    return cases


def archive_experiment(layout, benchmark, source, out_path, date,
                       ratings_path=None, key_path=None):
    cases = build_cases(
        layout, benchmark, source=source, date=date,
        ratings=_load_json(ratings_path), key=_load_json(key_path),
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(serialize_cases(cases))
    return out_path
