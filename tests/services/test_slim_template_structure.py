"""slim 化模板的轻量结构断言：防止后续误删关键指令或倒退回华丽风格。"""
from app.prompts.creation.prompt_template import good_template1, init_template


class TestInitTemplateSlim:
    def test_no_enum_backfill_lines(self):
        assert "[SHOOTING_ANGLE]" not in init_template
        assert "[CAMERA_HEIGHT]" not in init_template
        assert "[GAZE_DIRECTION]" not in init_template

    def test_camera_field_requires_natural_language_opening(self):
        assert "自然语言" in init_template

    def test_fixed_fields_untouched(self):
        assert "**【固定】任务目标**" in init_template
        assert "{aspect_ratio}" in init_template
        assert "{subject_area_min_pct}" in init_template
        assert "**【重要，必须遵守】角色的面部五官细节、面部神韵、发型发色、发饰、整体气质、核心装饰物需要与参考图完全一致，不要改脸。**" in init_template
        assert "3D toon shader + 细腻 cel shading" in init_template

    def test_thirteen_field_skeleton_preserved(self):
        for field in (
            "**角色视觉锚点**", "**背景场景**", "**角色姿势", "**角色服装**",
            "**角色脚部/袜子细节**", "**角色神态**", "**镜头与构图",
            "**构图硬约束**", "**光影", "**材质与质感", "**Negative Prompt**",
        ):
            assert field in init_template, f"缺少字段: {field}"

    def test_expression_whitelist_in_expression_field(self):
        for word in ("平静", "柔和微笑", "闭眼", "微微含笑", "专注"):
            assert word in init_template
        assert "单一主表情" in init_template
        assert "视线方向" in init_template

    def test_leg_foot_exposure_preserved(self):
        assert "自然展示腿部与脚部，但不低俗" in init_template
        assert "穿着袜子，不得穿鞋、赤足" in init_template

    def test_negative_field_caps_at_3_to_5(self):
        assert "3-5" in init_template.split("**Negative Prompt**")[1]


class TestGoodTemplateSlim:
    def test_based_on_slim_cas_med_squat(self):
        assert "淡紫色薄纱短袜" in good_template1
        assert "白猫" in good_template1
        assert "3:4" in good_template1

    def test_no_machine_code(self):
        assert "[SHOOTING_ANGLE]" not in good_template1
        assert "[COMPOSITION_DECISION]" not in good_template1

    def test_camera_opens_with_natural_language(self):
        assert "3/4 正面视角，机位略高做轻微俯拍" in good_template1

    def test_anchors_bound_to_reference(self):
        assert "（见参考图）" in good_template1

    def test_negative_is_short_noun_list(self):
        neg = good_template1.split("**Negative Prompt**")[1]
        assert len([p for p in neg.replace("：", "").split("、") if p.strip()]) <= 5

    def test_pro_photography_vocab_retained(self):
        for term in ("Key Light", "Fill Light", "Rim Light", "Eye Glint", "50mm"):
            assert term in good_template1

    def test_old_ornate_exemplar_removed(self):
        assert "纯白色丝袜" not in good_template1  # 旧窗台款特征
        assert "飘窗" not in good_template1
