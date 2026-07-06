import uuid
from datetime import datetime, timedelta, timezone

from app.models.material import MaterialCharacter, MaterialCreativeDirection
from app.services.material_service.history_creative_directions import (
    build_history_creative_direction_list,
)


def _make_character(db_session) -> MaterialCharacter:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    row = MaterialCharacter(
        id=char_id,
        name="Test",
        display_name="Test",
        status="idle",
        setting_text="",
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_empty_returns_placeholder(db_session):
    char = _make_character(db_session)
    assert build_history_creative_direction_list(db_session, char.id) == "（暂无历史创意主题）"


def test_multiple_directions_desc_order(db_session):
    char = _make_character(db_session)
    now = datetime.now(timezone.utc)
    rows = [
        MaterialCreativeDirection(
            id=str(uuid.uuid4()),
            character_id=char.id,
            title="Old",
            description="## 核心主题\n旧",
            divergence="low",
            created_at=now - timedelta(days=2),
        ),
        MaterialCreativeDirection(
            id=str(uuid.uuid4()),
            character_id=char.id,
            title="Mid",
            description="## 核心主题\n中",
            divergence="mid",
            created_at=now - timedelta(days=1),
        ),
        MaterialCreativeDirection(
            id=str(uuid.uuid4()),
            character_id=char.id,
            title="New",
            description="## 核心主题\n新",
            divergence="high",
            created_at=now,
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    text = build_history_creative_direction_list(db_session, char.id)
    assert text.index("New") < text.index("Mid") < text.index("Old")


def test_divergence_chinese_label(db_session):
    char = _make_character(db_session)
    for div, label in [("low", "低"), ("mid", "中"), ("high", "高")]:
        db_session.add(
            MaterialCreativeDirection(
                id=str(uuid.uuid4()),
                character_id=char.id,
                title=div,
                description="## 核心主题\nx",
                divergence=div,
            )
        )
    db_session.commit()
    text = build_history_creative_direction_list(db_session, char.id)
    assert "【低】" in text
    assert "【中】" in text
    assert "【高】" in text


def test_core_topic_extraction_standard(db_session):
    char = _make_character(db_session)
    db_session.add(
        MaterialCreativeDirection(
            id=str(uuid.uuid4()),
            character_id=char.id,
            title="T",
            description="## 核心主题\n这是核心主题描述\n## 推荐场景\n...",
            divergence="low",
        )
    )
    db_session.commit()
    text = build_history_creative_direction_list(db_session, char.id)
    assert "这是核心主题描述" in text


def test_core_topic_extraction_fallback(db_session):
    char = _make_character(db_session)
    free = "自由文本无小节标题" * 5
    db_session.add(
        MaterialCreativeDirection(
            id=str(uuid.uuid4()),
            character_id=char.id,
            title="T",
            description=free,
            divergence="low",
        )
    )
    db_session.commit()
    text = build_history_creative_direction_list(db_session, char.id)
    assert free[:80] in text
