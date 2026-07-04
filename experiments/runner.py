"""exp 出图执行器：variant × seed × images_per_cell，多模态装配与生产 quick_create 一致。
并发粒度=单张图；断点续跑以 manifest ok 标记 + 文件存在为准。"""
import argparse
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.material_service.material_file_service import (
    standard_reference_paths_for_multimodal_prompt,
)
from app.tools.llm.nano_banana_pro import generate_image_with_nano_banana_pro

from experiments.baseline_gen import VARIANTS_ROOT
from experiments.config import load_benchmark, load_experiment_config
from experiments.layout import ExpLayout

logger = logging.getLogger(__name__)

# 与 quick_create_service.run_quick_create_task_sync 中的参考图指引文案保持一致
_REF_GUIDE_TEXT = "以下是角色参考图，作为你修补任务的重要参考"


def _resolve_refs(character_id: str) -> list:
    refs = standard_reference_paths_for_multimodal_prompt(character_id)
    if not refs:
        raise ValueError(f"角色 {character_id} 标准参考图不足 5 张")
    return refs


def _load_manifest(layout: ExpLayout) -> dict:
    if os.path.isfile(layout.manifest_path()):
        with open(layout.manifest_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": []}


def _save_manifest(layout: ExpLayout, manifest: dict) -> None:
    os.makedirs(os.path.dirname(layout.manifest_path()), exist_ok=True)
    tmp = layout.manifest_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, layout.manifest_path())


def _cell_done(manifest: dict, layout: ExpLayout, variant: str,
               seed_id: str, k: int) -> bool:
    for e in manifest["entries"]:
        if (e["variant"], e["seed_id"], e["image_index"]) == (variant, seed_id, k):
            return bool(e.get("ok")) and os.path.isfile(
                os.path.join(layout.root, e["image_path"])
            )
    return False


def _generate_one(job: dict, layout: ExpLayout, gen_image) -> dict:
    content = [{"text": job["prompt_text"]}, {"text": _REF_GUIDE_TEXT}]
    for p in job["refs"]:
        content.append({"picture": p})
    img_dir = layout.image_dir(job["variant"], job["seed_id"])
    file_name = f"img_{job['k']}.png"
    ok = gen_image(
        Content=content,
        output_path=img_dir,
        file_name=file_name,
        aspect_ratio=job["aspect_ratio"],
    )
    rel = os.path.relpath(
        os.path.join(img_dir, file_name), layout.root
    ).replace("\\", "/")
    return {
        "variant": job["variant"], "seed_id": job["seed_id"],
        "image_index": job["k"], "character_id": job["character_id"],
        "image_path": rel, "aspect_ratio": job["aspect_ratio"], "ok": bool(ok),
    }


def run_experiment(config_path: str, results_root: str = "experiments/results",
                   gen_image=generate_image_with_nano_banana_pro) -> dict:
    cfg = load_experiment_config(config_path)
    bench = load_benchmark(cfg.benchmark)
    layout = ExpLayout(results_root, cfg.exp_id)
    manifest = _load_manifest(layout)

    jobs, skipped = [], 0
    for variant in cfg.variants:
        for seed in bench.seeds:
            src = os.path.join(VARIANTS_ROOT, cfg.exp_id, variant,
                               f"{seed.seed_id}.txt")
            with open(src, "r", encoding="utf-8") as f:
                prompt_text = f.read()
            # 发送全文存档
            os.makedirs(layout.prompts_dir(variant), exist_ok=True)
            with open(layout.prompt_path(variant, seed.seed_id), "w",
                      encoding="utf-8") as f:
                f.write(prompt_text)
            refs = _resolve_refs(seed.character_id)
            for k in range(1, cfg.images_per_cell + 1):
                if _cell_done(manifest, layout, variant, seed.seed_id, k):
                    skipped += 1
                    continue
                jobs.append({
                    "variant": variant, "seed_id": seed.seed_id, "k": k,
                    "character_id": seed.character_id,
                    "aspect_ratio": seed.aspect_ratio,
                    "prompt_text": prompt_text, "refs": refs,
                })

    generated = failed = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=cfg.concurrency) as pool:
        futures = {pool.submit(_generate_one, j, layout, gen_image): j
                   for j in jobs}
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                entry = fut.result()
            except Exception as exc:
                logger.error("出图异常 %s/%s#%s: %s", j["variant"],
                             j["seed_id"], j["k"], exc, exc_info=True)
                entry = {
                    "variant": j["variant"], "seed_id": j["seed_id"],
                    "image_index": j["k"], "character_id": j["character_id"],
                    "image_path": "", "aspect_ratio": j["aspect_ratio"],
                    "ok": False,
                }
            with lock:
                manifest["entries"] = [
                    e for e in manifest["entries"]
                    if (e["variant"], e["seed_id"], e["image_index"])
                    != (entry["variant"], entry["seed_id"], entry["image_index"])
                ]
                manifest["entries"].append(entry)
                _save_manifest(layout, manifest)  # 逐张落盘，中断可续
            if entry["ok"]:
                generated += 1
            else:
                failed += 1

    stats = {"generated": generated, "skipped": skipped, "failed": failed}
    logger.info("出图完成: %s", stats)
    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="A/B 实验出图执行器")
    ap.add_argument("--config", required=True)
    ap.add_argument("--results-root", default="experiments/results")
    args = ap.parse_args()
    print(json.dumps(run_experiment(args.config,
                                    results_root=args.results_root),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
