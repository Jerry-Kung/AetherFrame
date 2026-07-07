"""exp002 腿脚规则包结构断言：保证 R1-R6 在生产模板就位，且不破坏 slim 骨架。"""
from app.prompts.creation.prompt_precreation import prompt_step1
from app.prompts.creation.prompt_template import good_template1, init_template
from app.services.creation_service.prompt_precreation_service import _build_step1_prompt


class TestRulePackStep1:
    def _p(self):
        return _build_step1_prompt(chara_profile="档案", seed_prompt="种子")

    def test_r1_material_word_blacklist_declared(self):
        # 黑名单词与感性白名单指引同时出现在 step1 腿脚设计段
        assert "次表面散射" in prompt_step1
        assert "珠光" in prompt_step1 or "折射" in prompt_step1
        assert "感性" in prompt_step1 or "轻盈" in prompt_step1

    def test_r3_toe_protection_guidance(self):
        assert "脚趾根根分明" in prompt_step1
        assert "圆润" in prompt_step1 or "弱化脚趾" in prompt_step1

    def test_r4_single_wrinkle_restraint(self):
        assert "褶皱" in prompt_step1
        assert "一处" in prompt_step1 or "至多" in prompt_step1

    def test_r5_extreme_pose_backoff_but_keeps_exposure(self):
        assert "深度折叠" in prompt_step1 or "多重交叠" in prompt_step1
        # 第一原则护栏：退让措辞不得删掉腿脚展示要求
        assert "自然展示腿部与脚部，但不低俗" in prompt_step1

    def test_slim_leg_foot_guidance_still_present(self):
        # slim 基准不动摇：原腿脚设计目标未被删
        assert "不要写实化或包含过度的解剖细节" in prompt_step1


class TestRulePackGoodTemplate:
    def test_r2_sock_cuff_structure_anchor(self):
        # 范例袜口带结构特征（蕾丝/罗纹/缎带其一）
        assert any(k in good_template1 for k in ("蕾丝", "罗纹", "缎带"))

    def test_r3_toe_rounded_phrasing_in_exemplar(self):
        assert "圆润" in good_template1 or "轮廓柔和" in good_template1

    def test_r1_no_physics_material_words_in_good_template(self):
        for w in ("次表面散射", "透光率", "微孔织物", "折射率"):
            assert w not in good_template1

    def test_r6_negative_reserves_leg_foot_slots(self):
        neg = good_template1.split("**Negative Prompt**")[1]
        assert "脚趾" in neg or "多肢" in neg or "多余的手指" in neg
        # slim 上限不破：仍 ≤5 条
        assert len([p for p in neg.replace("：", "").split("、") if p.strip()]) <= 5

    def test_good_template_keeps_slim_skeleton(self):
        for field in ("**角色脚部/袜子细节**", "**Negative Prompt**",
                      "**光影", "**材质与质感"):
            assert field in good_template1


class TestRulePackInitTemplate:
    def test_sock_field_hint_mentions_structure_and_toe(self):
        seg = init_template.split("**角色脚部/袜子细节**")[1].split("**角色神态**")[0]
        assert "袜口" in seg or "蕾丝" in seg or "罗纹" in seg
        assert "脚趾" in seg

    def test_negative_field_hint_reserves_leg_foot(self):
        seg = init_template.split("**Negative Prompt**")[1]
        assert "脚趾" in seg or "腿脚" in seg
