import uuid

import pytest
from fastapi.testclient import TestClient

from app.models.material import MaterialCharacter


@pytest.fixture
def api_client(db_session):
    from app.main import app
    from app.models.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _create_character(db_session) -> str:
    char_id = f"mchar_{uuid.uuid4().hex[:10]}"
    db_session.add(
        MaterialCharacter(
            id=char_id,
            name="Old",
            display_name="Old",
            status="idle",
            setting_text="",
        )
    )
    db_session.commit()
    return char_id


def test_old_advice_start_returns_404(api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.post(f"/api/material/characters/{char_id}/creation-advice/start")
    assert r.status_code == 404


def test_old_advice_status_returns_404(api_client, db_session):
    char_id = _create_character(db_session)
    r = api_client.get(f"/api/material/characters/{char_id}/creation-advice/status")
    assert r.status_code == 404


def test_openapi_does_not_include_old_advice(api_client):
    r = api_client.get("/openapi.json")
    paths = r.json()["paths"]
    assert "/api/material/characters/{character_id}/creation-advice/start" not in paths
    assert "/api/material/characters/{character_id}/creation-advice/status" not in paths
