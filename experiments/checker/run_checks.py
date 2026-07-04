"""对 manifest 中每张生成图执行全量核对。并发粒度=图，上限来自配置（≤10）。"""
import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

from experiments.config import (
    load_anchor_list,
    load_benchmark,
    load_experiment_config,
)
from experiments.layout import ExpLayout
from experiments.checker.checks import run_anchor_checks, run_structure_checks

logger = logging.getLogger(__name__)


def check_one_image(entry: dict, anchors_by_char: dict, layout: ExpLayout,
                    infer) -> dict:
    image_abs = os.path.join(layout.root, entry["image_path"])
    character_id = entry["character_id"]
    doc = {
        "variant": entry["variant"],
        "seed_id": entry["seed_id"],
        "image_index": entry["image_index"],
        "image_path": entry["image_path"],
        "character_id": character_id,
        "structure": run_structure_checks(image_abs, infer=infer),
        "anchors": run_anchor_checks(
            image_abs, character_id, anchors_by_char[character_id], infer=infer
        ),
    }
    out_path = layout.check_path(
        entry["variant"], entry["seed_id"], entry["image_index"]
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return doc


def run_all_checks(config_path: str, results_root: str = "experiments/results",
                   force: bool = False, infer=yibu_gemini_infer) -> dict:
    cfg = load_experiment_config(config_path)
    bench = load_benchmark(cfg.benchmark)
    anchors_by_char = {
        c["character_id"]: load_anchor_list(c["anchors"])
        for c in bench.characters.values()
    }
    layout = ExpLayout(results_root, cfg.exp_id)
    with open(layout.manifest_path(), "r", encoding="utf-8") as f:
        entries = [e for e in json.load(f)["entries"] if e.get("ok")]

    todo, skipped = [], 0
    for e in entries:
        cp = layout.check_path(e["variant"], e["seed_id"], e["image_index"])
        if os.path.isfile(cp) and not force:
            skipped += 1
        else:
            todo.append(e)

    checked = failed = 0
    with ThreadPoolExecutor(max_workers=cfg.concurrency) as pool:
        futures = {
            pool.submit(check_one_image, e, anchors_by_char, layout, infer): e
            for e in todo
        }
        for fut in as_completed(futures):
            e = futures[fut]
            try:
                fut.result()
                checked += 1
            except Exception as exc:
                failed += 1
                logger.error("核对失败 %s/%s#%s: %s", e["variant"],
                             e["seed_id"], e["image_index"], exc, exc_info=True)
    stats = {"checked": checked, "skipped": skipped, "failed": failed}
    logger.info("核对完成: %s", stats)
    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="逐图全量核对")
    ap.add_argument("--config", required=True)
    ap.add_argument("--results-root", default="experiments/results")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    stats = run_all_checks(args.config, results_root=args.results_root,
                           force=args.force)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
