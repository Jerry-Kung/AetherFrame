import os

from app.services import directory_service


def test_video_task_dir_layout():
    d = directory_service.get_video_task_dir("vid_dir_x")
    assert d.replace("\\", "/").endswith("data/video/tasks/vid_dir_x")


def test_video_dirs_created_on_init(tmp_path, monkeypatch):
    monkeypatch.setattr(directory_service, "DATA_DIR", str(tmp_path))
    directory_service.initialize_data_directory()
    assert os.path.isdir(directory_service.get_video_tasks_dir())
