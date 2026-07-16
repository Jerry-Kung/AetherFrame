"""feedback_kb 机制测试（设计文档 §12）：版本时间线、姿势字典、特征提取、
姿势打标、KB 构建幂等/过滤/排除、关联守门、紧迫度排序。"""
import json

import pytest

from experiments.feedback_kb import correlate as co
from experiments.feedback_kb import features
from experiments.feedback_kb import kb_build
from experiments.feedback_kb import pose_tagger
from experiments.feedback_kb.kb_query import load_kb
from experiments.feedback_kb.pose_taxonomy import load_pose_taxonomy
from experiments.feedback_kb.rank import rank_modes
from experiments.feedback_kb.versions import load_versions

# ---------- fixtures ----------

VERSIONS_YAML = """
versions:
  - {version: pre_slim, since: null, description: 基线}
  - {version: slim, since: "2026-07-06T15:33:00", description: slim}
  - {version: rulepack, since: "2026-07-07T19:06:00", description: rulepack}
"""

POSE_YAML = """
version: v1
families:
  sit_normal: 常规坐姿
  lie_side: 侧卧
  other: 兜底
aliases: {sit_old: sit_normal}
"""

FULL_PROMPT = """**[COMPOSITION_DECISION]**
aspect_ratio: 3:4
subject_area_min: 55%
shooting_angle: three_quarter
camera_height: slight_down
gaze_direction: to_camera

**【固定】任务目标**：生成一张 3:4 图。

**角色姿势（自然展示腿部与脚部，但不低俗）**：角色侧卧在床上，双腿自然伸展。

**角色服装**：白色大腿袜，袜口带蕾丝。

**角色脚部/袜子细节**：白色大腿袜服帖包裹双腿，袜口有蕾丝。足尖在袜面包裹下轮廓圆润柔和，弱化脚趾的分离感。仅脚踝处一处轻微褶皱。

**Negative Prompt**：裸露脚趾、多肢、袜子缺失。
"""


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def _export_v2(records):
    return {"schema": "aetherframe_feedback_v2",
            "exported_at": "2026-07-16T00:00:00+00:00",
            "records": records, "tag_config": {"version": 2, "tags": []}}


def _record(qc="qcreate_aabbccdd0011", created="2026-07-08T12:00:00",
            seed="seed-1", images=None, prompt_index=0):
    return {
        "batch_item_id": "bb_x", "quick_create_task_id": qc,
        "character_id": "mchar_x", "character_name": "Castorice",
        "seed_prompt_id": seed, "seed_section": "character_specific",
        "seed_prompt_text": "种子文本", "created_at": created,
        "prompt_groups": [{
            "prompt_id": "p-uuid", "prompt_index": prompt_index,
            "prompt_title": "t", "full_prompt": FULL_PROMPT,
            "total_images": 3,
            "images": images or [
                {"image_index": 0, "leg_foot_bad": True,
                 "selected_tags": [{"key": "foot_crude", "severity": "severe"}],
                 "selected_tag_labels": ["脚部简陋（严重）"], "feedback_text": ""},
            ],
        }],
    }


# ---------- versions ----------

def test_infer_version_boundaries(tmp_path):
    tl = load_versions(_write(tmp_path, "v.yaml", VERSIONS_YAML))
    assert tl.infer_version("2026-07-01T00:00:00") == "pre_slim"
    assert tl.infer_version("2026-07-06T15:33:00") == "slim"
    assert tl.infer_version("2026-07-07T19:05:59") == "slim"
    assert tl.infer_version("2026-07-08T12:00:00") == "rulepack"


def test_versions_must_ascend(tmp_path):
    bad = VERSIONS_YAML.replace('"2026-07-07T19:06:00"', '"2026-07-05T00:00:00"')
    with pytest.raises(ValueError):
        load_versions(_write(tmp_path, "v.yaml", bad))


# ---------- pose taxonomy ----------

def test_pose_taxonomy_normalize_and_guard(tmp_path):
    tx = load_pose_taxonomy(_write(tmp_path, "p.yaml", POSE_YAML))
    assert tx.normalize("sit_old") == "sit_normal"
    assert tx.is_valid("other")
    with pytest.raises(ValueError):
        tx.normalize("unknown_pose")
    with pytest.raises(ValueError):
        load_pose_taxonomy(_write(tmp_path, "p2.yaml",
                                  POSE_YAML.replace("  other: 兜底\n", "")))


# ---------- features ----------

def test_extract_composition_percent_and_float():
    comp = features.extract_composition(FULL_PROMPT)
    assert comp["aspect_ratio"] == "3:4"
    assert comp["subject_area_min"] == 0.55
    assert comp["gaze_direction"] == "to_camera"
    comp2 = features.extract_composition(
        FULL_PROMPT.replace("subject_area_min: 55%", "subject_area_min: 0.65"))
    assert comp2["subject_area_min"] == 0.65


def test_split_sections_and_pose_text():
    assert "侧卧" in features.get_pose_text(FULL_PROMPT)
    secs = features.split_sections(FULL_PROMPT)
    assert any("Negative" in t for t in secs)


def test_detect_rules_fingerprints():
    rules = features.detect_rules(FULL_PROMPT)
    assert rules == {"R1": True, "R2": True, "R3": True, "R4": True,
                     "R5": None, "R6": True}
    # R1 假：袜子段出现黑名单词
    broken = FULL_PROMPT.replace("服帖包裹双腿", "次表面散射的珠光质感")
    assert features.detect_rules(broken)["R1"] is False
    # R6 假：Negative 段无腿脚条目
    broken = FULL_PROMPT.replace("裸露脚趾、多肢、袜子缺失", "低质量")
    assert features.detect_rules(broken)["R6"] is False


# ---------- pose tagger ----------

def test_tag_pose_with_injected_llm(tmp_path):
    tx = load_pose_taxonomy(_write(tmp_path, "p.yaml", POSE_YAML))
    assert pose_tagger.tag_pose("角色侧卧", tx, infer_fn=lambda p: "lie_side") == "lie_side"
    # 越界输出回落 other；异常返回 None；空姿势段返回 None
    assert pose_tagger.tag_pose("x", tx, infer_fn=lambda p: "flying") == "other"
    assert pose_tagger.tag_pose("x", tx, infer_fn=lambda p: 1 / 0) is None
    assert pose_tagger.tag_pose("  ", tx, infer_fn=lambda p: "lie_side") is None


# ---------- kb_build ----------

def _build(tmp_path, exports, **kw):
    fdir = tmp_path / "feedbacks"
    fdir.mkdir(exist_ok=True)
    for name, data in exports.items():
        (fdir / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    kb_path = str(tmp_path / "kb.jsonl")
    v_path = _write(tmp_path, "v.yaml", VERSIONS_YAML)
    p_path = _write(tmp_path, "p.yaml", POSE_YAML)
    stats = kb_build.build_kb(str(fdir), kb_path, pose_taxonomy_path=p_path,
                              versions_path=v_path, **kw)
    return kb_path, stats


def test_kb_build_skips_v1_and_excluded_and_dedups(tmp_path):
    exports = {
        "feedback_export_a.json": {"schema": "aetherframe_feedback_v1", "records": []},
        "feedback_export_b.json": _export_v2([
            _record(),
            _record(qc="qcreate_3808a8be9915"),   # CASE_NOTES 约定排除的链路测试
        ]),
        # 全量重复导出：同 case 再次出现，应 upsert 不翻倍
        "feedback_export_c.json": _export_v2([_record()]),
    }
    calls = []
    kb_path, stats = _build(tmp_path, exports,
                            infer_fn=lambda p: calls.append(1) or "lie_side")
    kb = load_kb(kb_path)
    assert stats["skipped_files"] == 1
    assert len(kb) == 1 and kb[0]["case_key"] == "qc_aabbccdd0011__p0"
    assert kb[0]["case_id"] == "Case_prod_20260708_aabbccdd_0"
    assert kb[0]["version_inferred"] == "rulepack"
    assert kb[0]["pose_family"] == "lie_side"
    assert kb[0]["bad"] == 1 and kb[0]["images"][0]["severities"] == ["severe"]


def test_kb_build_idempotent_pose_cache(tmp_path):
    exports = {"feedback_export_b.json": _export_v2([_record()])}
    calls = []
    infer = lambda p: calls.append(1) or "lie_side"
    kb_path, s1 = _build(tmp_path, exports, infer_fn=infer)
    first = open(kb_path, encoding="utf-8").read()
    _, s2 = _build(tmp_path, exports, infer_fn=infer)
    assert s1["llm_calls"] == 1 and s2["llm_calls"] == 0  # 缓存命中不再调 LLM
    assert open(kb_path, encoding="utf-8").read() == first


def test_kb_build_no_llm_leaves_pending(tmp_path):
    kb_path, stats = _build(tmp_path,
                            {"feedback_export_b.json": _export_v2([_record()])},
                            no_llm=True)
    assert stats["pose_pending"] == 1
    assert load_kb(kb_path)[0]["pose_family"] is None


# ---------- correlate 守门 ----------

def _case(pose, seed, with_mode):
    tags = [{"key": "foot_crude", "severity": "moderate"}] if with_mode else []
    return {"case_key": f"k{id(object())}", "seed_id": seed,
            "version_inferred": "rulepack", "pose_family": pose,
            "composition": {"aspect_ratio": "3:4"},
            "images": [{"image_index": 0, "leg_foot_bad": with_mode,
                        "tag_keys": [t["key"] for t in tags],
                        "severities": [t["severity"] for t in tags],
                        "feedback_text": ""}]}


TAG_MAP = {"foot_crude": "脚部/简陋"}


def test_correlate_nmin_gate():
    kb = [_case("lie_side", f"s{i}", True) for i in range(3)] + \
         [_case("sit_normal", f"t{i}", False) for i in range(20)]
    rows = co.correlate(kb, "脚部/简陋", "pose_family", tag_map=TAG_MAP)
    lie = next(r for r in rows if r["value"] == "lie_side")
    assert lie["confidence"] == "insufficient" and lie["rr"] is None  # 暴露侧 3 < 8


def test_correlate_strong_and_single_seed_flag():
    kb = [_case("lie_side", f"s{i}", i < 6) for i in range(10)] + \
         [_case("sit_normal", f"t{i}", i < 1) for i in range(20)]
    rows = co.correlate(kb, "脚部/简陋", "pose_family", tag_map=TAG_MAP)
    lie = next(r for r in rows if r["value"] == "lie_side")
    assert lie["rr"] and lie["rr"] > co.STRONG_RR and lie["confidence"] == "strong"
    # 同样分布但崩坏全来自同一 seed → 降为 weak 并打标
    kb2 = [_case("lie_side", "same-seed" if i < 6 else f"s{i}", i < 6)
           for i in range(10)] + \
          [_case("sit_normal", f"t{i}", i < 1) for i in range(20)]
    lie2 = next(r for r in co.correlate(kb2, "脚部/简陋", "pose_family", tag_map=TAG_MAP)
                if r["value"] == "lie_side")
    assert lie2["confidence"] == "weak" and any("单种子" in f for f in lie2["flags"])


def test_correlate_zero_control():
    kb = [_case("lie_side", f"s{i}", i < 4) for i in range(10)] + \
         [_case("sit_normal", f"t{i}", False) for i in range(10)]
    lie = next(r for r in co.correlate(kb, "脚部/简陋", "pose_family", tag_map=TAG_MAP)
               if r["value"] == "lie_side")
    assert lie["rr"] is None and any("无对照" in f for f in lie["flags"])


# ---------- rank ----------

def test_rank_modes_severity_and_neutral_trend(tmp_path):
    tl = load_versions(_write(tmp_path, "v.yaml", VERSIONS_YAML))
    kb = [_case("lie_side", f"s{i}", True) for i in range(4)]
    rows = rank_modes(kb, tl, tag_map=TAG_MAP)
    assert rows[0]["mode"] == "脚部/简陋"
    assert rows[0]["freq"] == 4 and rows[0]["severity_weight"] == 2.0  # 全部中等
    assert rows[0]["trend"] == 1.0 and "单版本" in rows[0]["trend_note"]
    assert rows[0]["urgency"] == 8.0
