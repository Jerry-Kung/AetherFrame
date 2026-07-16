"""知识库构建（设计文档 §3）：导出 JSON → feature_kb.jsonl，case_key upsert 幂等。

- 只摄入 schema=aetherframe_feedback_v2 的导出（v1 跳过并提示，用户拍板排除）。
- 链路测试记录按 CASE_NOTES 既有约定排除（qcreate_3808a8be9915）。
- 姿势打标缓存：已有行 pose_family 非空且 pose_text 未变 → 跳过 LLM。
"""
import argparse
import glob
import json
import logging
import os
import re
import sys

from experiments.feedback_kb import features
from experiments.feedback_kb.pose_taxonomy import load_pose_taxonomy
from experiments.feedback_kb.pose_tagger import tag_pose
from experiments.feedback_kb.versions import load_versions

logger = logging.getLogger(__name__)

SCHEMA_V2 = "aetherframe_feedback_v2"
# CASE_NOTES.md 归档约定：2026-07-08 链路测试 feedback 不归档，全量导出再见到时继续跳过
EXCLUDED_QC_TASKS = {"qcreate_3808a8be9915"}

DEFAULT_POSE_TAXONOMY = "experiments/cases/pose_taxonomy.yaml"
DEFAULT_VERSIONS = "experiments/cases/prompt_versions.yaml"


def _qc_hex(qc_task_id: str) -> str:
    return re.sub(r"^qcreate_", "", qc_task_id)


def make_case_key(qc_task_id: str, prompt_index) -> str:
    return f"qc_{_qc_hex(qc_task_id)}__p{prompt_index}"


def make_case_id(qc_task_id: str, prompt_index, prompt_id: str, created_at: str) -> str:
    """与归档 case_id 派生规则一致（2026-07-08 spec §4），供与 production_cases.txt 互指。"""
    date = created_at[:10].replace("-", "")
    pkey = prompt_index if prompt_index != -1 else prompt_id[:8]
    return f"Case_prod_{date}_{_qc_hex(qc_task_id)[:8]}_{pkey}"


def build_case_row(record: dict, group: dict, exported_from: str, timeline) -> dict:
    """组装一行 KB（不含 pose_family——打标在 upsert 阶段按缓存决定）。"""
    full_prompt = group["full_prompt"]
    images = []
    for im in sorted(group["images"], key=lambda x: x["image_index"]):
        images.append({
            "image_index": im["image_index"],
            "leg_foot_bad": bool(im["leg_foot_bad"]),
            "tag_keys": [t["key"] for t in im.get("selected_tags", [])],
            "severities": [t.get("severity") or "" for t in im.get("selected_tags", [])],
            "feedback_text": (im.get("feedback_text") or "").strip(),
        })
    return {
        "case_key": make_case_key(record["quick_create_task_id"], group["prompt_index"]),
        "case_id": make_case_id(record["quick_create_task_id"], group["prompt_index"],
                                group.get("prompt_id", ""), record["created_at"]),
        "exported_from": exported_from,
        "created_at": record["created_at"],
        "version_inferred": timeline.infer_version(record["created_at"]),
        "character_id": record["character_id"],
        "character_name": record["character_name"],
        "seed_id": record["seed_prompt_id"],
        "seed_text": record["seed_prompt_text"],
        "composition": features.extract_composition(full_prompt),
        "rules": features.detect_rules(full_prompt),
        "pose_family": None,
        "pose_text": features.get_pose_text(full_prompt),
        "total_images": group["total_images"],
        "bad": sum(1 for im in images if im["leg_foot_bad"]),
        "images": images,
    }


def load_kb_rows(kb_path: str) -> dict:
    """kb jsonl -> {case_key: row}，文件不存在返回空。"""
    rows = {}
    if os.path.isfile(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    rows[row["case_key"]] = row
    return rows


def build_kb(feedbacks_dir: str, kb_path: str,
             pose_taxonomy_path: str = DEFAULT_POSE_TAXONOMY,
             versions_path: str = DEFAULT_VERSIONS,
             no_llm: bool = False, infer_fn=None) -> dict:
    """返回统计 {files, skipped_files, cases, new_cases, llm_calls, pose_pending}。"""
    taxonomy = load_pose_taxonomy(pose_taxonomy_path)
    timeline = load_versions(versions_path)
    existing = load_kb_rows(kb_path)

    stats = {"files": 0, "skipped_files": 0, "cases": 0, "new_cases": 0,
             "llm_calls": 0, "pose_pending": 0}
    fresh = {}
    for path in sorted(glob.glob(os.path.join(feedbacks_dir, "feedback_export_*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema") != SCHEMA_V2:
            print(f"[skip] 非 v2 导出（schema={data.get('schema')}）: {path}", file=sys.stderr)
            stats["skipped_files"] += 1
            continue
        stats["files"] += 1
        exported_from = os.path.basename(path)
        for record in data["records"]:
            if record["quick_create_task_id"] in EXCLUDED_QC_TASKS:
                logger.info("按 CASE_NOTES 约定排除链路测试记录: %s",
                            record["quick_create_task_id"])
                continue
            for group in record["prompt_groups"]:
                row = build_case_row(record, group, exported_from, timeline)
                fresh[row["case_key"]] = row  # 同 key 后出现的导出覆盖（全量导出语义）

    merged = {}
    for key, row in fresh.items():
        old = existing.get(key)
        if old is None:
            stats["new_cases"] += 1
        # 姿势标签缓存：pose_text 未变则沿用，避免重复 LLM 调用
        if old and old.get("pose_family") and old.get("pose_text") == row["pose_text"]:
            row["pose_family"] = old["pose_family"]
        elif no_llm:
            row["pose_family"] = None
        else:
            row["pose_family"] = tag_pose(row["pose_text"], taxonomy, infer_fn=infer_fn)
            stats["llm_calls"] += 1
        if row["pose_family"] is None:
            stats["pose_pending"] += 1
        merged[key] = row
    # 保留 KB 中已有但本次导出目录未覆盖的行（导出文件被移走不等于数据作废）
    for key, row in existing.items():
        merged.setdefault(key, row)

    stats["cases"] = len(merged)
    os.makedirs(os.path.dirname(os.path.abspath(kb_path)), exist_ok=True)
    with open(kb_path, "w", encoding="utf-8", newline="\n") as f:
        for key in sorted(merged):
            f.write(json.dumps(merged[key], ensure_ascii=False) + "\n")
    return stats


def main():
    ap = argparse.ArgumentParser(description="feedback 知识库构建（增量、幂等）")
    ap.add_argument("--feedbacks-dir", default="experiments/feedbacks")
    ap.add_argument("--kb", default="experiments/cases/feature_kb.jsonl")
    ap.add_argument("--pose-taxonomy", default=DEFAULT_POSE_TAXONOMY)
    ap.add_argument("--versions", default=DEFAULT_VERSIONS)
    ap.add_argument("--no-llm", action="store_true",
                    help="跳过姿势打标（pose_family 记 null 待补），用于纯确定性构建")
    args = ap.parse_args()
    stats = build_kb(args.feedbacks_dir, args.kb, args.pose_taxonomy,
                     args.versions, no_llm=args.no_llm)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
