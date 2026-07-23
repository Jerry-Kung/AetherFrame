from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_tasks_ok():
    r = client.get("/api/video/tasks")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_status_404_for_unknown():
    r = client.get("/api/video/tasks/vid_nope/status")
    assert r.status_code == 404


def test_upload_creates_draft(tmp_path):
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (300, 400), "pink").save(buf, format="PNG")
    buf.seek(0)
    r = client.post(
        "/api/video/tasks/upload",
        files={"file": ("ref.png", buf, "image/png")},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "draft"
    assert data["recommended_ratio"] == "3:4"
    # 清理
    client.delete(f"/api/video/tasks/{data['task_id']}")
