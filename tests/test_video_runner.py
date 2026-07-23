import os

from app.models.database import SessionLocal, init_db
from app.repositories.video_repository import VideoRepository


class FakeStorage:
    def __init__(self):
        self.deleted = []
    def upload_and_presign(self, local_path, object_key=None):
        return ("obj/key.png", "https://signed.example/ref.png")
    def delete(self, object_key):
        self.deleted.append(object_key)


class FakeClient:
    def __init__(self, statuses):
        self._statuses = list(statuses)
        self.submitted = None
    def submit(self, prompt, image_url, *, image_role, duration, generate_audio, ratio):
        self.submitted = {"image_role": image_role, "ratio": ratio, "duration": duration}
        return "seed-123"
    def poll(self, task_id):
        from app.tools.llm.seedance import SeedanceResult
        return self._statuses.pop(0)


def _seed(repo, task_id, tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"x")
    return repo.create({
        "id": task_id, "source_kind": "upload", "ref_image_path": str(ref),
        "video_prompt_text": "温暖居家", "image_role": "first_frame",
        "duration": 8, "generate_audio": False, "ratio": "3:4", "status": "pending",
    })


def test_runner_success_downloads_and_cleans_tos(tmp_path, monkeypatch):
    from app.services.video_service import runner
    from app.services import directory_service
    from app.tools.llm.seedance import SeedanceResult

    monkeypatch.setattr(directory_service, "DATA_DIR", str(tmp_path))
    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed(repo, "vid_run_a", tmp_path)
        storage = FakeStorage()
        client = FakeClient([
            SeedanceResult(status="running"),
            SeedanceResult(status="succeeded", video_url="https://v.example/out.mp4"),
        ])
        downloaded = {}
        def fake_download(url, dest):
            downloaded["dest"] = dest
            with open(dest, "wb") as f:
                f.write(b"mp4")
        runner.run_video_task_sync(
            "vid_run_a", SessionLocal, storage=storage, client=client,
            downloader=fake_download, poll_interval=0,
        )
        row = repo.get_by_id("vid_run_a")
        assert row.status == "completed"
        assert row.video_filename == "output.mp4"
        assert storage.deleted == ["obj/key.png"]
        assert os.path.basename(downloaded["dest"]) == "output.mp4"
    finally:
        repo.delete("vid_run_a")
        db.close()


def test_runner_failure_records_error_and_cleans(tmp_path, monkeypatch):
    from app.services.video_service import runner
    from app.services import directory_service
    from app.tools.llm.seedance import SeedanceResult

    monkeypatch.setattr(directory_service, "DATA_DIR", str(tmp_path))
    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed(repo, "vid_run_b", tmp_path)
        storage = FakeStorage()
        client = FakeClient([SeedanceResult(status="failed", error="模型拒绝")])
        runner.run_video_task_sync(
            "vid_run_b", SessionLocal, storage=storage, client=client,
            downloader=lambda u, d: None, poll_interval=0,
        )
        row = repo.get_by_id("vid_run_b")
        assert row.status == "failed"
        assert "模型拒绝" in row.error_message
        assert storage.deleted == ["obj/key.png"]
    finally:
        repo.delete("vid_run_b")
        db.close()
