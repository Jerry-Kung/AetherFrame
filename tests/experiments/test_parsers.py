from experiments.checker.parsers import (
    parse_anchor_answer,
    parse_count_answer,
    parse_yes_no_reason,
)


def test_count_plain_digit():
    assert parse_count_answer("2") == 2


def test_count_with_noise():
    assert parse_count_answer("图中人物有 3 条腿。") == 3


def test_count_chinese_numeral():
    assert parse_count_answer("两条") == 2
    assert parse_count_answer("四") == 4


def test_count_unparseable():
    assert parse_count_answer("看不清楚") is None


def test_yes_no_reason_yes():
    r = parse_yes_no_reason("是。画面中出现了两个躯干，上下重叠。")
    assert r["verdict"] == "yes"
    assert "躯干" in r["reason"]


def test_yes_no_reason_no():
    r = parse_yes_no_reason("否，颈部与腰部曲线自然，无扭曲。")
    assert r["verdict"] == "no"


def test_yes_no_reason_unparseable():
    r = parse_yes_no_reason("这个问题很有意思")
    assert r["verdict"] is None


def test_anchor_yes():
    assert parse_anchor_answer("是，佩戴了相同的花冠") == "yes"


def test_anchor_no():
    assert parse_anchor_answer("否") == "no"


def test_anchor_unsure():
    assert parse_anchor_answer("无法判断，头部被遮挡") == "unsure"
    assert parse_anchor_answer("嗯……") == "unsure"
