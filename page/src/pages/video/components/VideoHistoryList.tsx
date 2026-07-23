import { useState, useEffect, useCallback } from "react";
import type { VideoTask, VideoStatus } from "@/types/video";
import * as videoApi from "@/services/videoApi";

interface VideoHistoryListProps {
  onSelect: (task: VideoTask) => void;
}

const STATUS_LABEL: Record<VideoStatus, string> = {
  draft: "草稿",
  pending: "等待中",
  uploading: "上传中",
  generating: "生成中",
  downloading: "下载中",
  completed: "已完成",
  failed: "失败",
};

const STATUS_COLOR: Record<VideoStatus, string> = {
  draft: "#9ca3af",
  pending: "#fbbf24",
  uploading: "#60a5fa",
  generating: "#f472b6",
  downloading: "#60a5fa",
  completed: "#34d399",
  failed: "#f87171",
};

export default function VideoHistoryList({ onSelect }: VideoHistoryListProps) {
  const [tasks, setTasks] = useState<VideoTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await videoApi.listTasks();
      setTasks(list);
    } catch {
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await videoApi.deleteTask(id);
      void load();
    } catch {
      // ignore, list will just retain stale entry until next refresh
    }
  };

  const handleCardClick = (task: VideoTask) => {
    if (task.status === "completed") {
      setPlayingId((prev) => (prev === task.task_id ? null : task.task_id));
      return;
    }
    onSelect(task);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6 text-rose-300/60 text-sm">
        <i className="ri-loader-4-line animate-spin mr-2"></i>加载历史…
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="flex items-center justify-center py-6 text-rose-300/50 text-sm">
        暂无历史任务
      </div>
    );
  }

  return (
    <div>
      <div className="text-sm font-medium text-rose-500 mb-2" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
        <i className="ri-history-line mr-1"></i>历史任务
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {tasks.map((task) => (
          <div
            key={task.task_id}
            onClick={() => handleCardClick(task)}
            className="relative flex flex-col rounded-2xl overflow-hidden border border-rose-100/80 cursor-pointer hover:shadow-md transition-shadow"
            style={{ background: "rgba(255,255,255,0.7)" }}
          >
            <div className="relative w-full" style={{ aspectRatio: "1 / 1", background: "rgba(253,164,175,0.08)" }}>
              <img
                src={videoApi.imageUrl(task.task_id)}
                alt="参考图"
                className="absolute inset-0 w-full h-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
              <span
                className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded-md text-[10px] text-white"
                style={{ background: STATUS_COLOR[task.status] }}
              >
                {STATUS_LABEL[task.status]}
              </span>
              <button
                type="button"
                onClick={(e) => handleDelete(task.task_id, e)}
                className="absolute top-1.5 right-1.5 w-5 h-5 flex items-center justify-center rounded-full text-white text-xs"
                style={{ background: "rgba(0,0,0,0.4)" }}
                aria-label="删除任务"
              >
                <i className="ri-close-line"></i>
              </button>
            </div>
            {playingId === task.task_id && task.status === "completed" && (
              <video
                controls
                autoPlay
                src={videoApi.videoUrl(task.task_id)}
                className="w-full"
                style={{ maxHeight: 120 }}
              />
            )}
            <div className="px-2 py-1.5 flex flex-col gap-0.5">
              <span className="text-[10px] text-gray-400 truncate">
                {task.created_at ? new Date(task.created_at).toLocaleString() : ""}
              </span>
              {(task.status === "draft" || task.status === "failed") && (
                <span className="text-[10px] text-rose-400">
                  {task.status === "draft" ? "继续编辑" : "重新提交"}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
