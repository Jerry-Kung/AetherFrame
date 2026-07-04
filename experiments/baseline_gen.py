"""基线 Prompt 生成冻结：每种子走生产 step1→step2 一次，写入 variants/ 进 git。
已存在的文件绝不覆盖（冻结语义）；case1/case2 生产原文可手工放入后自动跳过。"""
import argparse
import json
import logging
import os

from app.prompts.creation.prompt_precreation import prompt_step2
from app.prompts.creation.prompt_template import good_template1
from app.services.creation_service.prompt_precreation_service import (
    _build_step1_prompt,
    _parse_step1_composition,
)
from app.services.material_service.material_file_service import (
    read_chara_profile_markdown,
)
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

from experiments.config import load_benchmark, load_experiment_config

logger = logging.getLogger(__name__)

VARIANTS_ROOT = os.path.join("experiments", "variants")


def _load_profile(character_id: str) -> str:
    md = read_chara_profile_markdown(character_id, "chara_profile_final.md")
    if not md or not md.strip():
        raise ValueError(f"角色 {character_id} 缺少 chara_profile_final.md")
    return md.strip()


def generate_baseline_for_seed(seed, chara_profile: str,
                               infer=yibu_gemini_infer) -> str:
    p1 = _build_step1_prompt(chara_profile=chara_profile, seed_prompt=seed.text)
    step1_result = infer(p1, thinking_level="high", temperature=1.0)
    comp = _parse_step1_composition(step1_result)
    decided_ar = comp.get("aspect_ratio")
    if decided_ar and decided_ar != seed.aspect_ratio:
        logger.warning(
            "种子 %s: step1 决策画幅 %s 与 benchmark 声明 %s 不一致，出图以 benchmark 为准",
            seed.seed_id, decided_ar, seed.aspect_ratio,
        )
    p2 = prompt_step2.format(
        init_template=step1_result,
        good_template=good_template1,
        chara_profile=chara_profile,
        seed_prompt=seed.text,
    )
    return infer(p2, thinking_level="high", temperature=1.0)


def run_baseline_gen(config_path: str, only=None, infer=yibu_gemini_infer) -> dict:
    cfg = load_experiment_config(config_path)
    bench = load_benchmark(cfg.benchmark)
    out_dir = os.path.join(VARIANTS_ROOT, cfg.exp_id, "baseline")
    os.makedirs(out_dir, exist_ok=True)

    generated, skipped = [], []
    profiles = {}
    for seed in bench.seeds:
        if only and seed.seed_id not in only:
            continue
        target = os.path.join(out_dir, f"{seed.seed_id}.txt")
        if os.path.isfile(target):
            logger.info("已冻结，跳过: %s", target)
            skipped.append(seed.seed_id)
            continue
        if seed.character_id not in profiles:
            profiles[seed.character_id] = _load_profile(seed.character_id)
        logger.info("生成基线: %s", seed.seed_id)
        text = generate_baseline_for_seed(
            seed, profiles[seed.character_id], infer=infer
        )
        if not text.strip():
            raise RuntimeError(f"种子 {seed.seed_id} 生成的基线 Prompt 为空，拒绝冻结")
        with open(target, "w", encoding="utf-8") as f:
            f.write(text)
        generated.append(seed.seed_id)
    return {"generated": generated, "skipped": skipped}


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="基线 Prompt 生成冻结")
    ap.add_argument("--config", required=True)
    ap.add_argument("--only", help="逗号分隔的 seed_id 列表，缺省为全部")
    args = ap.parse_args()
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    print(json.dumps(run_baseline_gen(args.config, only=only),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
