import os

from app.services import directory_service
from app.models.database import SessionLocal, init_db
from app.repositories.video_repository import VideoRepository


def test_video_task_dir_layout():
    d = directory_service.get_video_task_dir("vid_dir_x")
    assert d.replace("\\", "/").endswith("data/video/tasks/vid_dir_x")


def test_video_dirs_created_on_init(tmp_path, monkeypatch):
    monkeypatch.setattr(directory_service, "DATA_DIR", str(tmp_path))
    directory_service.initialize_data_directory()
    assert os.path.isdir(directory_service.get_video_tasks_dir())


def _seed_draft(repo, task_id):
    return repo.create(
        {
            "id": task_id,
            "source_kind": "upload",
            "ref_image_path": f"data/video/tasks/{task_id}/ref.png",
            "image_role": "first_frame",
            "duration": 8,
            "generate_audio": False,
            "ratio": "3:4",
            "status": "draft",
        }
    )


def test_prompt_job_recommend_writes_result():
    from app.services.video_service.prompt_service import VideoPromptService

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed_draft(repo, "vid_pj_a")
        svc = VideoPromptService(db)
        svc.run_prompt_job_sync(
            "vid_pj_a", "recommend", None, SessionLocal,
            infer=lambda *a, **k: "温暖居家的动态镜头，脚尖轻点。",
        )
        row = repo.get_by_id("vid_pj_a")
        assert row.prompt_job_status == "completed"
        assert "脚尖" in row.prompt_job_result
    finally:
        repo.delete("vid_pj_a")
        db.close()


def test_prompt_job_optimize_uses_manual_prompt():
    from app.services.video_service.prompt_service import VideoPromptService

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed_draft(repo, "vid_pj_b")
        seen = {}
        def fake_infer(prompt, **k):
            seen["prompt"] = prompt
            return "优化后的 prompt"
        svc = VideoPromptService(db)
        svc.run_prompt_job_sync(
            "vid_pj_b", "optimize", "我的原始想法", SessionLocal, infer=fake_infer
        )
        assert "我的原始想法" in seen["prompt"]
        assert repo.get_by_id("vid_pj_b").prompt_job_status == "completed"
    finally:
        repo.delete("vid_pj_b")
        db.close()


def test_prompt_job_failure_records_error():
    from app.services.video_service.prompt_service import VideoPromptService

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed_draft(repo, "vid_pj_c")
        def boom(*a, **k):
            raise RuntimeError("LLM 挂了")
        svc = VideoPromptService(db)
        svc.run_prompt_job_sync("vid_pj_c", "recommend", None, SessionLocal, infer=boom)
        row = repo.get_by_id("vid_pj_c")
        assert row.prompt_job_status == "failed"
        assert "LLM 挂了" in row.prompt_job_error
    finally:
        repo.delete("vid_pj_c")
        db.close()
