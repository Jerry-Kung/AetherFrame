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


def test_build_step1_prompt_renders_shooting_and_camera_enums():
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    for name in ("正面", "3/4 正面", "侧面", "3/4 背面", "背面(回眸)"):
        assert name in p, f"missing shooting_angle {name}"
    for name in ("略仰", "平视", "略俯", "大俯"):
        assert name in p, f"missing camera_height {name}"


def test_parse_step1_composition_includes_shooting_and_height():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
aspect_ratio: 1:1
subject_area_min: 0.65
shooting_angle: three_quarter
camera_height: slight_up
"""
    result = _parse_step1_composition(text)
    assert result == {
        "aspect_ratio": "1:1",
        "subject_area_min": "0.65",
        "shooting_angle": "three_quarter",
        "camera_height": "slight_up",
    }


def test_parse_step1_composition_rejects_shooting_out_of_enum():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
shooting_angle: from_below_between_legs
camera_height: eye_level
"""
    result = _parse_step1_composition(text)
    assert "shooting_angle" not in result
    assert result["camera_height"] == "eye_level"


def test_step1_camera_bias_placeholder_empty():
    """本轮 step1 的镜头组合分布偏好段渲染为空,占位符不残留;Negative Prompt 风险标签占位符同理。"""
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    assert "{camera_combo_distribution_bias}" not in p
    assert "{negative_prompt_risk_tags}" not in p


def test_build_step1_prompt_renders_gaze_enum():
    from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
    p = _build_step1_prompt(chara_profile="cp", seed_prompt="sp")
    for name in ("看镜头", "3/4 看出画", "侧面看", "看下方", "看远处"):
        assert name in p, f"missing gaze_direction {name}"


def test_parse_step1_composition_includes_gaze():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
aspect_ratio: 1:1
subject_area_min: 0.65
shooting_angle: front
camera_height: eye_level
gaze_direction: to_camera
"""
    result = _parse_step1_composition(text)
    assert result["gaze_direction"] == "to_camera"


def test_parse_step1_composition_rejects_gaze_out_of_enum():
    from app.services.creation_service.prompt_precreation_service import _parse_step1_composition
    text = """
**[COMPOSITION_DECISION]**
gaze_direction: sultry_stare
"""
    result = _parse_step1_composition(text)
    assert "gaze_direction" not in result
