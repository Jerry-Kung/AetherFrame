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


def test_start_job_rejects_when_pending():
    from app.services.video_service.prompt_service import VideoPromptService
    import pytest as _pytest

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        _seed_draft(repo, "vid_pj_pending")
        svc = VideoPromptService(db)
        # 模拟第一次点击已把作业置为 pending（尚未跑到 running）
        repo.update("vid_pj_pending", {"prompt_job_status": "pending"})
        with _pytest.raises(ValueError):
            svc.start_job("vid_pj_pending", "recommend", None, background_tasks=None)
    finally:
        repo.delete("vid_pj_pending")
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


def test_submit_conflict_when_inflight():
    from app.services.video_service.video_service import VideoService
    from app.services.video_service.exceptions import VideoConflictError
    import pytest as _pytest

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        # 一个占位 in-flight 任务
        repo.create({
            "id": "vid_inflight", "source_kind": "upload",
            "ref_image_path": "x", "image_role": "first_frame",
            "duration": 8, "generate_audio": False, "ratio": "3:4",
            "status": "generating",
        })
        # 另一个 draft，尝试提交应 409
        repo.create({
            "id": "vid_draft", "source_kind": "upload",
            "ref_image_path": "x", "image_role": "first_frame",
            "duration": 8, "generate_audio": False, "ratio": "3:4",
            "status": "draft",
        })
        svc = VideoService(db)
        with _pytest.raises(VideoConflictError):
            svc.submit(
                "vid_draft", video_prompt_text="p", image_role="first_frame",
                duration=8, generate_audio=False, ratio="3:4", prompt_mode="manual",
                background_tasks=None,
            )
    finally:
        repo.delete("vid_inflight")
        repo.delete("vid_draft")
        db.close()


def test_import_from_quick_create_rejects_path_traversal(tmp_path):
    from app.services.video_service.video_service import VideoService
    from app.services.video_service.exceptions import VideoNotFoundError
    from app.repositories.creation_repository import CreationQuickCreateRepository
    from app.repositories.material_repository import MaterialCharacterRepository
    import pytest as _pytest

    init_db()
    db = SessionLocal()
    source_task = None
    char = None
    result = None
    try:
        mrepo = MaterialCharacterRepository(db)
        char = mrepo.create({"id": "mchar_vid_traversal", "name": "video-traversal-test-char"})
        quick_repo = CreationQuickCreateRepository(db)
        source_task = quick_repo.create(
            character_id=char.id,
            seed_prompt="p",
            n=1,
            aspect_ratio="1:1",
            selected_prompts=[],
        )
        work_dir = source_task.work_dir
        os.makedirs(work_dir, exist_ok=True)
        real_img = os.path.join(work_dir, "real.png")
        with open(real_img, "wb") as f:
            f.write(b"fake-png-bytes")

        # 位于 work_dir 之外的秘密文件（模拟任意文件读取目标）
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        secret_path = outside_dir / "secret.txt"
        secret_path.write_text("top secret")

        svc = VideoService(db)
        from app.models.video import VideoCreationTask

        before_count = db.query(VideoCreationTask).count()

        # 相对路径穿越
        with _pytest.raises(VideoNotFoundError):
            svc.import_from_quick_create(
                source_task.id, "../../../../../../../../etc/passwd", None
            )

        # 绝对路径直接指向 work_dir 之外的文件
        with _pytest.raises(VideoNotFoundError):
            svc.import_from_quick_create(source_task.id, str(secret_path), None)

        # 未创建任何 video 任务、也未拷贝任何文件（穿越应在拷贝前被拦截）
        assert db.query(VideoCreationTask).count() == before_count

        # 合法路径仍应正常工作（回归）
        result = svc.import_from_quick_create(source_task.id, "real.png", None)
        assert result["task_id"]
        assert result["ratio"]
        from app.services import directory_service

        copied_path = os.path.join(
            directory_service.get_video_task_dir(result["task_id"]), "ref.png"
        )
        assert os.path.isfile(copied_path)
    finally:
        try:
            if result:
                video_repo = VideoRepository(db)
                video_repo.delete(result["task_id"])
        except Exception:
            pass
        try:
            if source_task is not None:
                db.query(source_task.__class__).filter(
                    source_task.__class__.id == source_task.id
                ).delete()
                db.commit()
        except Exception:
            pass
        try:
            if char is not None:
                db.query(char.__class__).filter(char.__class__.id == char.id).delete()
                db.commit()
        except Exception:
            pass
        db.close()


def test_delete_running_task_rejected():
    from app.services.video_service.video_service import VideoService
    from app.services.video_service.exceptions import VideoConflictError
    import pytest as _pytest

    init_db()
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        repo.create({
            "id": "vid_del_run", "source_kind": "upload",
            "ref_image_path": "x", "image_role": "first_frame",
            "duration": 8, "generate_audio": False, "ratio": "3:4",
            "status": "downloading",
        })
        svc = VideoService(db)
        with _pytest.raises(VideoConflictError):
            svc.delete_task("vid_del_run")
    finally:
        repo.delete("vid_del_run")
        db.close()
