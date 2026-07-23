import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { VideoTask, ImageRole } from "@/types/video";
import { ApiError } from "@/services/api";
import * as videoApi from "@/services/videoApi";
import VideoHistoryList from "./components/VideoHistoryList";

const RATIOS = ["1:1", "4:3", "3:4", "16:9", "9:16"];

export default function VideoPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [task, setTask] = useState<VideoTask | null>(null);
  const [prompt, setPrompt] = useState("");
  const [imageRole, setImageRole] = useState<ImageRole>("first_frame");
  const [duration, setDuration] = useState(8);
  const [generateAudio, setGenerateAudio] = useState(false);
  const [ratio, setRatio] = useState("16:9");
  const [uploading, setUploading] = useState(false);
  const [promptLoading, setPromptLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const applyTask = useCallback((t: VideoTask) => {
    setTask(t);
    if (t.video_prompt_text) setPrompt(t.video_prompt_text);
    if (t.recommended_ratio) setRatio(t.recommended_ratio);
    if (t.image_role) setImageRole(t.image_role);
    if (t.duration) setDuration(t.duration);
    if (typeof t.generate_audio === "boolean") setGenerateAudio(t.generate_audio);
  }, []);

  // Restore draft from ?task= param
  useEffect(() => {
    const id = searchParams.get("task");
    if (!id) return;
    videoApi.getStatus(id).then(applyTask).catch(() => {});
  }, [searchParams, applyTask]);

  // Poll task status when generating
  useEffect(() => {
    if (!task) return;
    const taskId = task.task_id;
    const active = ["pending", "uploading", "generating", "downloading"].includes(task.status);
    if (!active) { stopPoll(); return; }
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const updated = await videoApi.getStatus(taskId);
        setTask(updated);
        if (!["pending", "uploading", "generating", "downloading"].includes(updated.status)) {
          stopPoll();
          setSubmitting(false);
          setHistoryKey((k) => k + 1);
        }
      } catch { stopPoll(); setSubmitting(false); }
    }, 3000);
    return stopPoll;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task?.task_id, task?.status]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const t = await videoApi.uploadImage(file);
      applyTask(t);
      setHistoryKey((k) => k + 1);
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const pollPromptJob = async (taskId: string) => {
    return new Promise<void>((resolve, reject) => {
      const iv = setInterval(async () => {
        try {
          const t = await videoApi.getPromptJobStatus(taskId);
          if (t.prompt_job_status === "completed") {
            clearInterval(iv);
            if (t.prompt_job_result) setPrompt(t.prompt_job_result);
            setTask(t);
            resolve();
          } else if (t.prompt_job_status === "failed") {
            clearInterval(iv);
            reject(new Error(t.prompt_job_error ?? "Prompt 生成失败"));
          }
        } catch (e) { clearInterval(iv); reject(e); }
      }, 2000);
    });
  };

  const handleRecommend = async () => {
    if (!task) return;
    setPromptLoading(true);
    try {
      await videoApi.startPromptJob(task.task_id, "recommend");
      await pollPromptJob(task.task_id);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "推荐失败");
    } finally { setPromptLoading(false); }
  };

  const handleOptimize = async () => {
    if (!task || !prompt.trim()) return;
    setPromptLoading(true);
    try {
      await videoApi.startPromptJob(task.task_id, "optimize", prompt);
      await pollPromptJob(task.task_id);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "优化失败");
    } finally { setPromptLoading(false); }
  };

  const handleSubmit = async () => {
    if (!task || !prompt.trim()) return;
    setSubmitting(true);
    try {
      const updated = await videoApi.submitVideo(task.task_id, {
        video_prompt_text: prompt,
        image_role: imageRole,
        duration,
        generate_audio: generateAudio,
        ratio,
      });
      setTask(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        showToast("已有视频任务进行中，请等待完成");
      } else {
        showToast(err instanceof ApiError ? err.message : "提交失败");
      }
      setSubmitting(false);
    }
  };

  const statusLabel: Record<string, string> = {
    pending: "等待中…", uploading: "上传中…", generating: "生成中…", downloading: "下载中…",
  };
  const isActive = task && ["pending", "uploading", "generating", "downloading"].includes(task.status);

  return (
    <div
      className="relative h-screen w-full overflow-hidden flex flex-col"
      style={{ background: "linear-gradient(145deg, #fff5f7 0%, #fffaf5 45%, #fef2f8 80%, #fff8f0 100%)" }}
    >
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl text-sm text-white shadow-lg"
          style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}>
          {toast}
        </div>
      )}

      <div className="relative z-10 flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center gap-3 px-7 pt-5 pb-4 shrink-0">
          <button type="button" onClick={() => navigate("/")}
            className="w-8 h-8 shrink-0 flex items-center justify-center rounded-xl cursor-pointer transition-all duration-200 hover:bg-rose-100/60"
            style={{ color: "#f472b6" }} aria-label="返回首页">
            <i className="ri-arrow-left-line text-base"></i>
          </button>
          <div className="w-7 h-7 shrink-0 flex items-center justify-center rounded-lg"
            style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}>
            <i className="ri-video-line text-white text-sm"></i>
          </div>
          <h1 className="text-base font-bold text-transparent bg-clip-text"
            style={{ backgroundImage: "linear-gradient(135deg, #f472b6 0%, #ec4899 100%)", fontFamily: "'ZCOOL KuaiLe', cursive" }}>
            视频创作
          </h1>
        </div>

        {/* Main content */}
        <div className="flex-1 flex flex-col px-6 pb-6 min-h-0 overflow-auto">
          <div className="rounded-3xl overflow-hidden border border-rose-100/80 flex flex-col gap-0"
            style={{ background: "rgba(255,255,255,0.55)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)" }}>
            <div className="h-[3px] w-full shrink-0 bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300 opacity-70" />

            <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-5">
              {/* Section 1: Reference image */}
              <div className="flex flex-col gap-3">
                <div className="text-sm font-medium text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                  <i className="ri-image-line mr-1"></i>参考图
                </div>
                <div
                  className="relative flex items-center justify-center rounded-2xl border-2 border-dashed border-rose-200/60 cursor-pointer hover:border-rose-300 transition-colors overflow-hidden"
                  style={{ minHeight: 180, background: "rgba(253,164,175,0.05)" }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {task ? (
                    <img src={videoApi.imageUrl(task.task_id)} alt="参考图"
                      className="w-full h-full object-cover rounded-2xl" style={{ maxHeight: 240 }} />
                  ) : (
                    <div className="flex flex-col items-center gap-2 text-rose-300/60">
                      <i className="ri-upload-cloud-line text-3xl"></i>
                      <span className="text-xs">{uploading ? "上传中…" : "点击上传参考图"}</span>
                    </div>
                  )}
                  {uploading && (
                    <div className="absolute inset-0 flex items-center justify-center rounded-2xl"
                      style={{ background: "rgba(255,255,255,0.7)" }}>
                      <i className="ri-loader-4-line animate-spin text-rose-400 text-2xl"></i>
                    </div>
                  )}
                </div>
                <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleUpload} />
              </div>

              {/* Section 2: Prompt workbench */}
              <div className="flex flex-col gap-3">
                <div className="text-sm font-medium text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                  <i className="ri-quill-pen-line mr-1"></i>Prompt 工作台
                </div>
                <textarea
                  className="flex-1 w-full rounded-xl border border-rose-100 p-3 text-sm text-gray-700 resize-none focus:outline-none focus:border-rose-300 transition-colors"
                  style={{ minHeight: 120, background: "rgba(255,255,255,0.8)" }}
                  placeholder="输入或生成视频 Prompt…"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={promptLoading}
                />
                <div className="flex gap-2">
                  <button type="button" onClick={handleRecommend}
                    disabled={!task || promptLoading}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium text-white transition-all disabled:opacity-40"
                    style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}>
                    {promptLoading ? <i className="ri-loader-4-line animate-spin"></i> : <i className="ri-magic-line"></i>}
                    AI 推荐
                  </button>
                  <button type="button" onClick={handleOptimize}
                    disabled={!task || !prompt.trim() || promptLoading}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all disabled:opacity-40 border border-rose-200 text-rose-500 hover:bg-rose-50">
                    {promptLoading ? <i className="ri-loader-4-line animate-spin"></i> : <i className="ri-sparkling-line"></i>}
                    AI 优化
                  </button>
                </div>
              </div>

              {/* Section 3: Parameters + submit */}
              <div className="flex flex-col gap-3">
                <div className="text-sm font-medium text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                  <i className="ri-settings-3-line mr-1"></i>参数 & 提交
                </div>

                {/* image_role */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-14 shrink-0">图片角色</span>
                  <div className="flex gap-1">
                    {(["first_frame", "reference_image"] as ImageRole[]).map((r) => (
                      <button key={r} type="button"
                        onClick={() => setImageRole(r)}
                        className={`px-2.5 py-1 rounded-lg text-xs transition-all ${imageRole === r ? "text-white" : "border border-rose-200 text-rose-400 hover:bg-rose-50"}`}
                        style={imageRole === r ? { background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" } : {}}>
                        {r === "first_frame" ? "首帧" : "参考图"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* duration */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-14 shrink-0">时长 {duration}s</span>
                  <input type="range" min={4} max={15} value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    className="flex-1 accent-rose-400" />
                </div>

                {/* ratio */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-14 shrink-0">比例</span>
                  <select value={ratio} onChange={(e) => setRatio(e.target.value)}
                    className="flex-1 rounded-lg border border-rose-100 px-2 py-1 text-xs text-gray-700 focus:outline-none focus:border-rose-300"
                    style={{ background: "rgba(255,255,255,0.8)" }}>
                    {RATIOS.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>

                {/* audio */}
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={generateAudio} onChange={(e) => setGenerateAudio(e.target.checked)}
                    className="accent-rose-400" />
                  <span className="text-xs text-gray-500">生成音频</span>
                </label>

                {/* Submit */}
                <button type="button" onClick={handleSubmit}
                  disabled={!task || !prompt.trim() || submitting || !!isActive}
                  className="mt-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium text-white transition-all disabled:opacity-40"
                  style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)", fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                  {(submitting || isActive) ? <i className="ri-loader-4-line animate-spin"></i> : <i className="ri-video-line"></i>}
                  {isActive ? (statusLabel[task!.status] ?? "处理中…") : "生成视频"}
                </button>

                {/* Result */}
                {task?.status === "completed" && task.video_filename && (
                  <div className="flex flex-col gap-2 mt-1">
                    <video controls src={videoApi.videoUrl(task.task_id)}
                      className="w-full rounded-xl border border-rose-100" style={{ maxHeight: 160 }} />
                    <a href={videoApi.videoUrl(task.task_id)} download
                      className="text-xs text-center text-rose-400 hover:text-rose-500 underline">
                      下载视频
                    </a>
                  </div>
                )}
                {task?.status === "failed" && (
                  <div className="flex flex-col gap-2 mt-1">
                    <p className="text-xs text-red-400">{task.error_message ?? "生成失败"}</p>
                    <button type="button" onClick={handleSubmit}
                      className="text-xs text-rose-400 hover:text-rose-500 underline text-left">
                      重新提交
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* History */}
          <div className="mt-5">
            <VideoHistoryList key={historyKey} onSelect={applyTask} />
          </div>
        </div>
      </div>
    </div>
  );
}
