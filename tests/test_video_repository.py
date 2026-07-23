from app.models.database import SessionLocal, init_db
from app.repositories.video_repository import VideoRepository


def _make_task(repo, task_id, status="draft"):
    return repo.create(
        {
            "id": task_id,
            "source_kind": "upload",
            "ref_image_path": f"data/video/tasks/{task_id}/ref.png",
            "image_role": "first_frame",
            "duration": 8,
            "generate_audio": False,
            "ratio": "3:4",
            "status": status,
        }
    )


def test_create_and_get():
    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _make_task(repo, "vid_repo_a")
        row = repo.get_by_id("vid_repo_a")
        assert row is not None
        assert row.source_kind == "upload"
        assert row.status == "draft"
        assert row.generate_audio is False
    finally:
        repo.delete("vid_repo_a")
        db.close()


def test_get_inflight_only_matches_running_states():
    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _make_task(repo, "vid_repo_b", status="generating")
        assert repo.get_inflight() is not None
        repo.update("vid_repo_b", {"status": "completed"})
        assert repo.get_inflight() is None
    finally:
        repo.delete("vid_repo_b")
        db.close()
