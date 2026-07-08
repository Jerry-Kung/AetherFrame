from experiments.casebank.case_format import Case, parse_cases, serialize_cases


def _sample():
    return Case(
        case_id="Case_exp002_01", date="2026-07-07", source="exp002",
        character="castorice", seed_id="cas_med_squat", difficulty="medium",
        variant="control", images=5, bad=2,
        tags=["袜子/上色感", "袜子/皱褶夸张"], taxonomy_version="v1",
        seed_prompt="角色乖巧地蹲在玄关。", final_prompt="**[COMPOSITION_DECISION]**\naspect_ratio: 3:4\n正文……",
        feedback="",
    )


def test_serialize_contains_all_sections():
    s = serialize_cases([_sample()])
    assert "Case_exp002_01:" in s
    assert "[meta]" in s
    assert "[seed_prompt]" in s
    assert "[final_prompt]" in s
    assert "[feed_back]" in s
    assert "variant: control" in s
    assert "tags: [袜子/上色感, 袜子/皱褶夸张]" in s


def test_round_trip_single_case():
    cases = [_sample()]
    assert parse_cases(serialize_cases(cases)) == cases


def test_round_trip_multiple_cases_and_empty_tags():
    c1 = _sample()
    c2 = _sample()
    c2.case_id = "Case_exp002_02"
    c2.variant = "rulepack"
    c2.tags = []
    c2.bad = 0
    c2.feedback = "三张均正常。\n腿脚袜表现良好。"   # 多行 feedback
    cases = [c1, c2]
    assert parse_cases(serialize_cases(cases)) == cases


def test_parse_preserves_multiline_final_prompt():
    c = _sample()
    c.final_prompt = "第一行\n第二行\n**Negative Prompt**：穿鞋、多指。"
    out = parse_cases(serialize_cases([c]))
    assert out[0].final_prompt == c.final_prompt


def test_parse_tolerates_feedback_with_brackets_free_text():
    c = _sample()
    c.feedback = "问题：脚部[轻微]崩坏"
    out = parse_cases(serialize_cases([c]))
    assert out[0].feedback == c.feedback


def test_round_trip_preserves_trailing_newline_in_fields():
    c = _sample()
    c.final_prompt = "line1\n\nline2\n"   # 值以换行结尾
    c.feedback = "问题描述\n\n"           # 值以空行结尾
    out = parse_cases(serialize_cases([c]))
    assert out[0].final_prompt == c.final_prompt
    assert out[0].feedback == c.feedback
