import pytest


def test_build_step1_prompt_renders_aspect_ratio_and_subject_area_enums():
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    for code in ("16:9", "4:3", "1:1", "3:4", "9:16", "2:3", "3:2", "4:5", "5:4"):
        assert code in p, f"missing aspect_ratio {code}"
    for code in ("0.45", "0.55", "0.65", "0.75"):
        assert code in p, f"missing subject_area_min {code}"
    assert "任务步骤 0" in p or "任务步骤0" in p or "先做构图决策" in p
    assert "aspect_ratio" in p and "subject_area_min" in p


def test_parse_step1_composition_from_output():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**【固定】任务目标**:...
**[COMPOSITION_DECISION]**
aspect_ratio: 1:1
subject_area_min: 0.65
**背景场景**:...
"""
    result = _parse_step1_composition(text)
    assert result == {"aspect_ratio": "1:1", "subject_area_min": "0.65"}


def test_parse_step1_composition_missing_returns_empty():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    result = _parse_step1_composition("no decision block here")
    assert result == {}


def test_parse_step1_composition_rejects_out_of_enum():
    """LLM 幻觉出枚举外的值,静默剔除该字段而不是 crash。"""
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
aspect_ratio: 7:11
subject_area_min: 0.65
"""
    result = _parse_step1_composition(text)
    assert "aspect_ratio" not in result
    assert result.get("subject_area_min") == "0.65"


def test_build_step1_prompt_contains_composition_output_requirement():
    """任务步骤末尾的 [COMPOSITION_DECISION] 输出说明段应该出现在 prompt 里。"""
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    assert "[COMPOSITION_DECISION]" in p
