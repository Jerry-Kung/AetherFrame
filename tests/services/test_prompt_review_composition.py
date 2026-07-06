def test_review_prompt_mentions_composition_diversity_dimensions():
    from app.services.creation_service.prompt_precreation_service import _build_review_prompt
    p = _build_review_prompt(
        input_content="[]", seed_prompt="sp", chara_profile="cp", num_best_prompts=2,
    )
    for kw in ("shooting_angle", "camera_height", "gaze_direction", "pose_family"):
        assert kw in p, f"missing dimension {kw} in review prompt"
    assert "差异" in p or "多样" in p


def test_review_prompt_weight_table_placeholder_rendered_empty():
    from app.services.creation_service.prompt_precreation_service import _build_review_prompt
    p = _build_review_prompt(
        input_content="[]", seed_prompt="sp", chara_profile="cp", num_best_prompts=2,
    )
    assert "{composition_weight_table}" not in p
    assert "{composition_diversity_criteria}" not in p


def test_review_prompt_separates_diversity_and_weight_sections():
    from app.services.creation_service.prompt_precreation_service import _build_review_prompt
    p = _build_review_prompt(
        input_content="[]", seed_prompt="sp", chara_profile="cp", num_best_prompts=2,
    )
    diversity_idx = p.find("维度差异")
    weight_idx = p.find("维度权重表")
    assert diversity_idx != -1 and weight_idx != -1
    assert diversity_idx < weight_idx, "diversity block must come before weight block"


def test_review_prompt_num_best_prompts_still_injected():
    from app.services.creation_service.prompt_precreation_service import _build_review_prompt
    p = _build_review_prompt(
        input_content="[]", seed_prompt="sp", chara_profile="cp", num_best_prompts=3,
    )
    assert "3" in p
