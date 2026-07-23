import logging
import os
import time

from app.repositories.video_repository import VideoRepository
from app.services import directory_service
from app.tools.beautify.storage import CloudStorageClient, get_default_client
from app.tools.llm.seedance import (
    SeedanceClient,
    download_video,
    get_default_seedance_client,
)

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 30
_TIMEOUT_SECONDS = 20 * 60
_OUTPUT_FILENAME = "output.mp4"


def run_video_task_sync(
    task_id: str,
    session_factory,
    *,
    storage: CloudStorageClient | None = None,
    client: SeedanceClient | None = None,
    downloader=None,
    poll_interval: int = _POLL_INTERVAL_SECONDS,
) -> None:
    storage = storage or get_default_client()
    client = client or get_default_seedance_client()
    downloader = downloader or download_video
    db = session_factory()
    cloud_object_key: str | None = None
    try:
        repo = VideoRepository(db)
        task = repo.get_by_id(task_id)
        if not task:
            return

        # 1) 上传参考图到 TOS
        repo.update(task_id, {"status": "uploading", "error_message": None})
        cloud_object_key, signed_url = storage.upload_and_presign(task.ref_image_path)

        # 2) 提交 Seedance + 轮询
        repo.update(task_id, {"status": "generating"})
        seed_id = client.submit(
            task.video_prompt_text or "",
            signed_url,
            image_role=task.image_role,
            duration=task.duration,
            generate_audio=task.generate_audio,
            ratio=task.ratio,
        )
        repo.update(task_id, {"seedance_task_id": seed_id})
        video_url = _poll_until_done(client, seed_id, poll_interval)

        # 3) 下载落盘
        repo.update(task_id, {"status": "downloading"})
        task_dir = directory_service.get_video_task_dir(task_id)
        os.makedirs(task_dir, exist_ok=True)
        dest = os.path.join(task_dir, _OUTPUT_FILENAME)
        downloader(video_url, dest)

        repo.update(
            task_id,
            {"status": "completed", "video_filename": _OUTPUT_FILENAME, "error_message": None},
        )
        logger.info("video completed task_id=%s", task_id)
    except Exception as exc:
        db.rollback()
        db2 = session_factory()
        try:
            VideoRepository(db2).update(
                task_id, {"status": "failed", "error_message": str(exc)[:500]}
            )
        finally:
            db2.close()
        logger.exception("video task failed task_id=%s err=%s", task_id, exc)
    finally:
        db.close()
        if cloud_object_key:
            try:
                storage.delete(cloud_object_key)
                logger.info("video cleanup: deleted TOS object %s", cloud_object_key)
            except Exception as cleanup_err:
                logger.warning(
                    "video cleanup failed object_key=%s err=%s", cloud_object_key, cleanup_err
                )


def _poll_until_done(client: SeedanceClient, seed_id: str, poll_interval: int) -> str:
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        result = client.poll(seed_id)
        if result.status == "running":
            if poll_interval:
                time.sleep(poll_interval)
            continue
        if result.status == "succeeded":
            if not result.video_url:
                raise RuntimeError("视频生成成功但缺少 video_url")
            return result.video_url
        raise RuntimeError(result.error or "视频生成任务失败")
    raise TimeoutError("视频生成超时")
