from app.services.creation_service.prompt_precreation_service import strip_machine_code


COMPOSITION_BLOCK = (
    "**[COMPOSITION_DECISION]**\n"
    "aspect_ratio: 3:4\n"
    "subject_area_min: pct_65\n"
    "shooting_angle: three_quarter\n"
    "camera_height: slight_up\n"
    "gaze_direction: to_camera\n"
)

BODY = (
    "**【固定】任务目标**：生成一张 **3:4** 的插画。\n"
    "\n"
    "**镜头与构图（让人一眼“WoW”）**：3/4 正面视角，机位略高做轻微俯拍。\n"
)


def test_strips_composition_decision_block():
    result = strip_machine_code(COMPOSITION_BLOCK + "\n" + BODY)
    assert "[COMPOSITION_DECISION]" not in result
    assert "aspect_ratio:" not in result
    assert "**【固定】任务目标**" in result
    assert "3/4 正面视角" in result


def test_strips_legacy_enum_backfill_lines():
    legacy = (
        "**镜头与构图**：\n"
        "`[SHOOTING_ANGLE]` three_quarter (3/4 正面)\n"
        "`[CAMERA_HEIGHT]` slight_up (略仰)\n"
        "`[GAZE_DIRECTION]` to_camera (看镜头)\n"
        "使用等效 35mm 焦段。\n"
    )
    result = strip_machine_code(legacy)
    assert "[SHOOTING_ANGLE]" not in result
    assert "[CAMERA_HEIGHT]" not in result
    assert "[GAZE_DIRECTION]" not in result
    assert "使用等效 35mm 焦段。" in result


def test_no_machine_code_returns_unchanged():
    assert strip_machine_code(BODY) == BODY


def test_idempotent():
    once = strip_machine_code(COMPOSITION_BLOCK + "\n" + BODY)
    assert strip_machine_code(once) == once


def test_empty_string():
    assert strip_machine_code("") == ""
