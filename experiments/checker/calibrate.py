"""checker 校准：对已知真值图片跑结构检查，输出各项准确率（spec §5.4 上线门槛）。"""
import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import yaml

from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

from experiments.checker.checks import STRUCTURE_CHECKS, run_structure_checks

logger = logging.getLogger(__name__)


def load_calibration_set(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    cases = []
    for item in raw.get("cases") or []:
        image = str(item["image"])
        if not os.path.isfile(image):
            raise ValueError(f"校准图片不存在: {image}")
        truth = {str(k): bool(v) for k, v in (item.get("truth") or {}).items()}
        cases.append({"image": image, "truth": truth})
    if not cases:
        raise ValueError("校准集为空")
    return cases


def run_calibration(calib_path: str, out_path: str,
                    infer=yibu_gemini_infer, concurrency: int = 10) -> dict:
    cases = load_calibration_set(calib_path)
    with ThreadPoolExecutor(max_workers=min(concurrency, 10)) as pool:
        results = list(pool.map(
            lambda c: run_structure_checks(c["image"], infer=infer), cases
        ))

    report = {}
    for check in STRUCTURE_CHECKS:
        cid = check["check_id"]
        total = correct = unparsed = 0
        for case, result in zip(cases, results):
            if cid not in case["truth"]:
                continue
            total += 1
            got = result.get(cid, {}).get("pass")
            if got is None:
                unparsed += 1
            elif got == case["truth"][cid]:
                correct += 1
        report[cid] = {
            "total": total, "correct": correct, "unparsed": unparsed,
            "accuracy": round(correct / total, 4) if total else None,
        }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="checker 校准")
    ap.add_argument("--calib", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()
    report = run_calibration(args.calib, args.out, concurrency=args.concurrency)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
