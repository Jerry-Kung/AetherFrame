import uuid

from app.models.material import (
    MaterialCharacter,
    MaterialCreativeDirectionTask,
    MaterialSeedPromptTask,
)
from app.services.material_service.task_concurrency import (
    CharacterConcurrencyError,
    SeedPromptPerDirectionLimitExceededError,
    SeedPromptTotalLimitExceededError,
    assert_can_start_task,
    count_inflight_tasks_for_character,
    get_global_llm_semaphore,
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


def test_count_inflight_zero(db_session):
    char = _make_character(db_session)
    assert count_inflight_tasks_for_character(db_session, char.id) == 0


def test_count_inflight_processing_pending_counted(db_session):
    char = _make_character(db_session)
    tasks = [
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="pending",
            divergence="low",
        ),
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="processing",
            divergence="mid",
        ),
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="completed",
            divergence="high",
        ),
    ]
    db_session.add_all(tasks)
    db_session.commit()
    assert count_inflight_tasks_for_character(db_session, char.id) == 2


def test_assert_passes_under_limit(db_session):
    char = _make_character(db_session)
    db_session.add(
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="pending",
            divergence="low",
        )
    )
    db_session.commit()
    assert_can_start_task(db_session, char.id)


def test_assert_raises_at_limit(db_session):
    char = _make_character(db_session)
    for _ in range(2):
        db_session.add(
            MaterialCreativeDirectionTask(
                id=str(uuid.uuid4()),
                character_id=char.id,
                status="processing",
                divergence="low",
            )
        )
    db_session.commit()
    try:
        assert_can_start_task(db_session, char.id)
        assert False, "expected CharacterConcurrencyError"
    except CharacterConcurrencyError:
        pass


def test_global_semaphore_singleton():
    a = get_global_llm_semaphore()
    b = get_global_llm_semaphore()
    assert a is b


def test_count_inflight_unions_direction_and_seed(db_session):
    char = _make_character(db_session)
    db_session.add(
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="pending",
            divergence="low",
        )
    )
    db_session.add(
        MaterialSeedPromptTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="processing",
        )
    )
    db_session.commit()
    assert count_inflight_tasks_for_character(db_session, char.id) == 2


def test_assert_passes_with_mixed_one_each(db_session):
    char = _make_character(db_session)
    db_session.add(
        MaterialCreativeDirectionTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="pending",
            divergence="low",
        )
    )
    db_session.add(
        MaterialSeedPromptTask(
            id=str(uuid.uuid4()),
            character_id=char.id,
            status="processing",
        )
    )
    db_session.commit()
    try:
        assert_can_start_task(db_session, char.id)
        assert False, "expected CharacterConcurrencyError"
    except CharacterConcurrencyError:
        pass


def test_seed_per_direction_limit_exceeded_class():
    exc = SeedPromptPerDirectionLimitExceededError()
    try:
        raise exc
    except SeedPromptPerDirectionLimitExceededError:
        pass


def test_seed_total_limit_exceeded_class():
    exc = SeedPromptTotalLimitExceededError()
    try:
        raise exc
    except SeedPromptTotalLimitExceededError:
        pass
