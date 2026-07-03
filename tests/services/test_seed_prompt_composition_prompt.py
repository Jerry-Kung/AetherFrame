"""S2-1 单测:seed prompt 姿态家族均衡 + 背景联动 + fallback 注入。"""


def test_seed_prompt_renders_pose_family_enum():
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp",
        direction_text="direction",
        history_seed_prompts="none",
    )
    for name in ("坐姿", "躺姿", "跪姿", "蹲姿", "倚靠", "盘腿坐"):
        assert name in p, f"missing pose family: {name}"
    assert "≥4" in p or "至少 4" in p or "至少4" in p
    assert "不超过 3" in p or "不超过3" in p


def test_seed_prompt_folds_home_settings_from_direction():
    from app.services.material_service.seed_prompt_generation_service import (
        _fold_home_settings_into_direction_text,
    )
    text = _fold_home_settings_into_direction_text(
        title="T", description="D", home_settings=["卧室大床", "飘窗台"]
    )
    assert "卧室大床" in text and "飘窗台" in text
    assert "home_settings" in text or "居家背景" in text


def test_seed_prompt_fold_no_home_settings_passthrough():
    from app.services.material_service.seed_prompt_generation_service import (
        _fold_home_settings_into_direction_text,
    )
    text = _fold_home_settings_into_direction_text(
        title="T", description="D", home_settings=None
    )
    assert text == "T\n\nD"


def test_seed_prompt_distribution_bias_is_empty_this_round():
    """S2 本轮:分布偏好段渲染为空字符串,占位符不残留。"""
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp", direction_text="direction", history_seed_prompts="none",
    )
    assert "{pose_family_distribution_bias}" not in p


def test_seed_prompt_renders_home_setting_hint_table():
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp", direction_text="direction", history_seed_prompts="none",
    )
    assert "卧室大床" in p and "飘窗台" in p


def test_seed_prompt_includes_home_settings_fallback_when_missing():
    """当方向未提供 home_settings 时,注入 fallback 说明。"""
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp", direction_text="direction", history_seed_prompts="none",
        has_home_settings=False,
    )
    assert "未提供" in p or "自由选择" in p
    assert "{home_settings_fallback_note}" not in p


def test_seed_prompt_no_fallback_note_when_home_settings_present():
    from app.services.material_service.seed_prompt_generation_service import _build_seed_prompt
    p = _build_seed_prompt(
        chara_profile="cp", direction_text="direction", history_seed_prompts="none",
        has_home_settings=True,
    )
    assert "本方向未提供" not in p
