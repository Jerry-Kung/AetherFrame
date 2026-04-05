import { useState, useCallback, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useRepairTasks } from "@/hooks/useRepairTasks";
import { useRepairTask } from "@/hooks/useRepairTask";
import type { RepairTask, EditorState } from "@/types/repair";
import TaskList from "./components/TaskList";
import TaskEditor from "./components/TaskEditor";
import ResultDisplay from "./components/ResultDisplay";
import CuteConfirmModal from "./components/CuteConfirmModal";

/* ── Background decoration data ───────────────────────── */
const decorations = [
  { size: 280, top: "-6%", left: "-5%", opacity: 0.15, delay: "0s" },
  { size: 180, top: "65%", left: "-3%", opacity: 0.1, delay: "1.4s" },
  { size: 220, top: "-4%", right: "-5%", opacity: 0.13, delay: "0.7s" },
  { size: 140, top: "72%", right: "-3%", opacity: 0.09, delay: "2s" },
];

const sparkles = [
  { top: "8%", left: "14%", size: 12, delay: "0s" },
  { top: "20%", right: "18%", size: 9, delay: "0.9s" },
  { top: "72%", left: "9%", size: 7, delay: "1.6s" },
  { top: "82%", right: "14%", size: 11, delay: "2.3s" },
];

const defaultEditorState = (): EditorState => ({
  mainImage: "",
  prompt: "",
  referenceImages: [],
  outputCount: 1,
});

const PROMPT_SYNC_DEBOUNCE_MS = 350;

export default function RepairPage() {
  const navigate = useNavigate();
  const {
    tasks,
    loading: tasksLoading,
    error: tasksError,
    createTask,
    deleteTask,
    applyTaskSnapshot,
  } = useRepairTasks();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { 
    task: currentTask, 
    loading: taskLoading, 
    error: taskError,
    updateTask,
    uploadMainImage,
    uploadReferenceImages,
    deleteMainImage,
    deleteReferenceImage,
    startRepair,
    isUploading,
    fetchTask
  } = useRepairTask(selectedId);
  
  const [editorState, setEditorState] = useState<EditorState>(defaultEditorState());
  const [localError, setLocalError] = useState<string | null>(null);
  const [deleteConfirmTask, setDeleteConfirmTask] = useState<{ id: string; name: string } | null>(
    null
  );
  const [restartConfirmOpen, setRestartConfirmOpen] = useState(false);
  const promptSyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingPromptRef = useRef<string>("");
  const editorStateRef = useRef(editorState);
  editorStateRef.current = editorState;

  // 当选中任务变化时，更新编辑器状态
  useEffect(() => {
    if (currentTask) {
      setEditorState({
        mainImage: currentTask.mainImage,
        prompt: currentTask.prompt,
        referenceImages: currentTask.referenceImages,
        outputCount: currentTask.outputCount,
      });
    } else {
      setEditorState(defaultEditorState());
    }
  }, [currentTask?.id]);

  // 当任务列表加载完成后，自动选择第一个任务
  useEffect(() => {
    if (tasks.length > 0 && !selectedId) {
      setSelectedId(tasks[0].id);
    }
  }, [tasks, selectedId]);

  // 详情 / 轮询更新 currentTask 时同步左侧列表中的状态与结果，避免侧栏一直显示「未开始」
  useEffect(() => {
    if (currentTask) applyTaskSnapshot(currentTask);
  }, [currentTask, applyTaskSnapshot]);

  useEffect(() => {
    return () => {
      if (promptSyncTimerRef.current) {
        clearTimeout(promptSyncTimerRef.current);
        promptSyncTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (promptSyncTimerRef.current) {
      clearTimeout(promptSyncTimerRef.current);
      promptSyncTimerRef.current = null;
    }
  }, [selectedId]);

  // 显示错误提示（稳定引用，避免子组件中依赖它的 effect / callback 被无意义重建）
  const showError = useCallback((message: string) => {
    setLocalError(message);
    setTimeout(() => setLocalError(null), 5000);
  }, []);

  /* ── Task actions ─── */
  const handleSelect = useCallback((id: string) => setSelectedId(id), []);

  const openDeleteConfirm = useCallback(
    (id: string) => {
      const task = tasks.find((t) => t.id === id);
      setDeleteConfirmTask({ id, name: task?.name ?? id });
    },
    [tasks]
  );

  const handleDeleteCancel = useCallback(() => setDeleteConfirmTask(null), []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteConfirmTask) return;
    const id = deleteConfirmTask.id;
    try {
      await deleteTask(id);
      setDeleteConfirmTask(null);
      if (selectedId === id) {
        setSelectedId(tasks.find((t) => t.id !== id)?.id ?? null);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除任务失败";
      showError(message);
    }
  }, [deleteConfirmTask, deleteTask, selectedId, tasks, showError]);

  const handleNew = useCallback(async () => {
    try {
      const taskNum = tasks.length + 1;
      const newTask = await createTask(`新任务 #${taskNum}`);
      setSelectedId(newTask.id);
    } catch (err) {
      const message = err instanceof Error ? err.message : "创建任务失败";
      showError(message);
    }
  }, [createTask, tasks.length]);

  /* ── Editor change ─── */
  const handleEditorChange = useCallback(
    (next: Partial<EditorState>) => {
      if (!selectedId || !currentTask) return;

      setEditorState((prev) => ({ ...prev, ...next }));

      if (next.outputCount !== undefined) {
        void updateTask({ outputCount: next.outputCount });
      }

      if (next.prompt !== undefined) {
        pendingPromptRef.current = next.prompt;
        if (promptSyncTimerRef.current) clearTimeout(promptSyncTimerRef.current);
        promptSyncTimerRef.current = setTimeout(() => {
          promptSyncTimerRef.current = null;
          void updateTask({ prompt: pendingPromptRef.current }).catch((err) => {
            console.error("更新任务失败:", err);
          });
        }, PROMPT_SYNC_DEBOUNCE_MS);
      }
    },
    [selectedId, currentTask, updateTask]
  );

  // 处理主图上传
  const handleMainImageUpload = useCallback(async (file: File) => {
    if (!selectedId) return;
    try {
      // 先本地预览
      const reader = new FileReader();
      reader.onload = async (e) => {
        setEditorState(prev => ({ ...prev, mainImage: e.target?.result as string }));
      };
      reader.readAsDataURL(file);
      
      // 上传到后端
      await uploadMainImage(file);
    } catch (err) {
      const message = err instanceof Error ? err.message : "上传主图失败";
      showError(message);
    }
  }, [selectedId, uploadMainImage]);

  // 处理参考图上传
  const handleRefImagesUpload = useCallback(async (files: File[]) => {
    if (!selectedId) return;
    try {
      // 先本地预览
      const newUrls: string[] = [];
      for (const file of files) {
        const url = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve(e.target?.result as string);
          reader.readAsDataURL(file);
        });
        newUrls.push(url);
      }
      setEditorState(prev => ({ 
        ...prev, 
        referenceImages: [...prev.referenceImages, ...newUrls].slice(0, 5)
      }));
      
      // 上传到后端
      await uploadReferenceImages(files);
    } catch (err) {
      const message = err instanceof Error ? err.message : "上传参考图失败";
      showError(message);
    }
  }, [selectedId, uploadReferenceImages]);

  // 移除参考图（已落盘的须调后端删除文件）
  const removeRefImage = useCallback(
    async (idx: number) => {
      const url = editorStateRef.current.referenceImages[idx];
      if (url === undefined) return;

      const isLocalPreview = url.startsWith("data:") || url.startsWith("blob:");
      if (!isLocalPreview) {
        const m = url.match(/\/images\/reference\/([^/?#]+)/);
        const filename = m ? decodeURIComponent(m[1]) : null;
        if (filename) {
          try {
            await deleteReferenceImage(filename);
          } catch (err) {
            const message = err instanceof Error ? err.message : "删除参考图失败";
            showError(message);
            return;
          }
        }
      }

      setEditorState((prev) => {
        const next = [...prev.referenceImages];
        next.splice(idx, 1);
        return { ...prev, referenceImages: next };
      });
    },
    [deleteReferenceImage, showError]
  );

  /* ── Continue repair: create new task with result image ─── */
  const handleContinueRepair = useCallback(
    async (imageUrl: string) => {
      try {
        const taskNum = tasks.length + 1;
        const newTask = await createTask(`继续修补 #${taskNum}`);
        setSelectedId(newTask.id);
        // 注意：这里需要将结果图片下载后再上传为新任务的主图
        // 由于跨域限制，这个功能需要后端支持或更复杂的实现
        showError("继续修补功能需要后端支持");
      } catch (err) {
        const message = err instanceof Error ? err.message : "创建任务失败";
        showError(message);
      }
    },
    [createTask, tasks.length]
  );

  /* ── Submit ─── */
  const doSubmit = useCallback(async () => {
    if (!selectedId || !currentTask) return;
    if (!editorState.mainImage || !editorState.prompt.trim()) return;

    if (promptSyncTimerRef.current) {
      clearTimeout(promptSyncTimerRef.current);
      promptSyncTimerRef.current = null;
    }

    try {
      await updateTask({
        prompt: editorState.prompt,
        outputCount: editorState.outputCount,
      });
      const useReferenceImages = editorState.referenceImages.length > 0;
      await startRepair(useReferenceImages);
    } catch (err) {
      const message = err instanceof Error ? err.message : "启动修补任务失败";
      showError(message);
    }
  }, [selectedId, currentTask, editorState, updateTask, startRepair, showError]);

  const handleSubmit = useCallback(() => {
    if (!selectedId || !currentTask) return;
    if (!editorState.mainImage || !editorState.prompt.trim()) return;

    if (currentTask.status === "completed" || currentTask.status === "failed") {
      setRestartConfirmOpen(true);
      return;
    }
    void doSubmit();
  }, [selectedId, currentTask, editorState, doSubmit]);

  const handleRestartCancel = useCallback(() => setRestartConfirmOpen(false), []);

  const handleRestartConfirm = useCallback(() => {
    setRestartConfirmOpen(false);
    void doSubmit();
  }, [doSubmit]);

  /* ── Derived state ─── */
  const isProcessing = currentTask?.status === "processing";
  const isLoading = tasksLoading || taskLoading || isUploading;
  const currentResults = currentTask?.results ?? [];

  return (
    <div
      className="relative h-screen w-full overflow-hidden flex flex-col"
      style={{
        background:
          "linear-gradient(145deg, #fff5f7 0%, #fffaf5 45%, #fef2f8 80%, #fff8f0 100%)",
      }}
    >
      {/* ── Background image ─── */}
      <div
        className="absolute inset-0 z-0 pointer-events-none"
        style={{
          backgroundImage:
            "url(\"https://readdy.ai/api/search-image?query=soft%20dreamy%20anime%20aesthetic%20background%20art%20with%20delicate%20cherry%20blossom%20sakura%20petals%20floating%20in%20gentle%20breeze%2C%20warm%20pastel%20pink%20and%20creamy%20white%20watercolor%20illustration%20style%2C%20kawaii%20japanese%20aesthetic%2C%20soft%20bokeh%20circular%20lights%2C%20no%20people%20no%20characters%2C%20light%20and%20airy%20misty%20atmosphere%2C%20subtle%20floral%20pattern%20elements%2C%20beautiful%20pastel%20digital%20painting%20art%20with%20pink%20rose%20tones&width=1920&height=1080&seq=2001&orientation=landscape\")",
          backgroundSize: "cover",
          backgroundPosition: "center",
          opacity: 0.1,
        }}
      />

      {/* ── Gradient bubbles ─── */}
      {decorations.map((d, i) => (
        <div
          key={i}
          className="absolute rounded-full pointer-events-none"
          style={{
            width: d.size,
            height: d.size,
            top: d.top,
            left: (d as { left?: string }).left,
            right: (d as { right?: string }).right,
            opacity: d.opacity,
            background:
              i % 2 === 0
                ? "radial-gradient(circle, #fda4af 0%, #fecdd3 60%, transparent 100%)"
                : "radial-gradient(circle, #fbcfe8 0%, #fce7f3 60%, transparent 100%)",
            animation: "floatUp 8s ease-in-out infinite",
            animationDelay: d.delay,
          }}
        />
      ))}

      {/* ── Sparkles ─── */}
      {sparkles.map((s, i) => (
        <div
          key={i}
          className="absolute pointer-events-none text-rose-300/40 select-none"
          style={{
            top: s.top,
            left: (s as { left?: string }).left,
            right: (s as { right?: string }).right,
            fontSize: s.size,
            animation: "twinkle 3s ease-in-out infinite",
            animationDelay: s.delay,
          }}
        >
          <i className="ri-star-fill"></i>
        </div>
      ))}

      {/* ── Error toast ─── */}
      {(tasksError || taskError || localError) && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-3 rounded-xl bg-red-50 border border-red-200 shadow-lg">
          <div className="flex items-center gap-2">
            <i className="ri-error-warning-line text-red-500"></i>
            <span className="text-sm text-red-600">{tasksError || taskError || localError}</span>
            <button 
              onClick={() => setLocalError(null)}
              className="ml-2 text-red-400 hover:text-red-600"
            >
              <i className="ri-close-line"></i>
            </button>
          </div>
        </div>
      )}

      {/* ── Loading indicator ─── */}
      {isLoading && !isProcessing && (
        <div className="absolute top-4 right-4 z-50 px-3 py-2 rounded-xl bg-white/90 border border-rose-100 shadow-lg">
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 flex items-center justify-center animate-spin">
              <i className="ri-loader-4-line text-rose-400"></i>
            </span>
            <span className="text-sm text-rose-600">加载中…</span>
          </div>
        </div>
      )}

      {/* ── Page content ─── */}
      <div className="relative z-10 flex flex-col h-full">

        {/* ── Top bar ─── */}
        <div className="flex items-center justify-between px-7 pt-5 pb-4 shrink-0">
          {/* Back + title */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/")}
              className="flex items-center justify-center w-8 h-8 rounded-full cursor-pointer transition-all hover:bg-rose-100/60 text-rose-400/70 hover:text-rose-500 whitespace-nowrap"
            >
              <i className="ri-arrow-left-s-line text-lg"></i>
            </button>
            <div className="flex items-center gap-2">
              <span
                className="flex items-center justify-center w-7 h-7 rounded-xl text-white text-sm"
                style={{ background: "linear-gradient(135deg, #f472b6, #ec4899)" }}
              >
                <i className="ri-eraser-line text-xs"></i>
              </span>
              <h1
                className="text-lg font-semibold text-transparent bg-clip-text whitespace-nowrap"
                style={{
                  backgroundImage: "linear-gradient(135deg, #f472b6 0%, #ec4899 60%, #db2777 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                图片修补
              </h1>
            </div>
          </div>

          {/* Subtitle */}
          <span
            className="text-xs tracking-wide hidden md:block"
            style={{ color: "rgba(244,114,182,0.4)", fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            智能修复，让每一张图都完美无瑕
          </span>

          {/* Right spacer placeholder */}
          <div className="w-8" />
        </div>

        {/* ── Main workspace card ─── */}
        <div className="flex-1 flex flex-col px-6 pb-6 min-h-0">
          <div
            className="flex-1 flex flex-row min-h-0 overflow-hidden rounded-3xl border border-rose-100/80"
            style={{
              background: "rgba(255,255,255,0.55)",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
            }}
          >
            {/* Top accent line */}
            <div className="absolute left-6 right-6 h-[3px] rounded-b-full bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300 opacity-70 pointer-events-none" />

            {/* ── Left: Task list ─── */}
            <div
              className="w-56 shrink-0 border-r border-rose-100/60 flex flex-col min-h-0 pt-1"
              style={{ background: "rgba(255,250,252,0.6)" }}
            >
              <TaskList
                tasks={tasks}
                selectedId={selectedId}
                onSelect={handleSelect}
                onDeleteConfirm={openDeleteConfirm}
                onNew={handleNew}
              />
            </div>

            {/* ── Center: Editor ─── */}
            <div
              className="flex-1 flex flex-col min-h-0 border-r border-rose-100/60 pt-1"
              style={{ minWidth: 0 }}
            >
              {/* Section title */}
              <div className="px-5 pt-4 pb-2 shrink-0 flex items-center gap-2 min-w-0">
                <span className="w-4 h-4 flex items-center justify-center text-rose-400/70 text-sm shrink-0">
                  <i className="ri-edit-2-line"></i>
                </span>
                <h2
                  className="flex-1 min-w-0 text-sm font-semibold text-rose-600/70 tracking-wide truncate"
                  style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  {currentTask ? currentTask.name : "选择任务开始编辑"}
                </h2>
                {currentTask && selectedId ? (
                  <button
                    type="button"
                    title={isProcessing ? "处理中，暂不可删除" : "删除当前任务"}
                    disabled={isProcessing}
                    onClick={() => openDeleteConfirm(selectedId)}
                    className="shrink-0 px-2 py-1 rounded-lg text-xs text-rose-400 hover:text-rose-600 hover:bg-rose-50 disabled:opacity-40 disabled:pointer-events-none cursor-pointer transition-colors"
                  >
                    <i className="ri-delete-bin-6-line" />
                    <span className="sr-only">删除当前任务</span>
                  </button>
                ) : null}
              </div>
              <div className="mx-5 h-px bg-rose-100/60 shrink-0 mb-1" />

              {selectedId ? (
                <TaskEditor
                  taskId={selectedId}
                  taskStatus={currentTask?.status}
                  state={editorState}
                  onChange={handleEditorChange}
                  onSubmit={handleSubmit}
                  onMainImageUpload={handleMainImageUpload}
                  onRefImagesUpload={handleRefImagesUpload}
                  onRemoveRefImage={removeRefImage}
                  isProcessing={isProcessing}
                  isUploading={isUploading}
                  onTemplateError={showError}
                />
              ) : (
                <div className="flex-1 flex items-center justify-center text-rose-300/50 text-sm select-none">
                  ← 请先选择或新建一个任务
                </div>
              )}
            </div>

            {/* ── Right: Results ─── */}
            <div className="w-80 shrink-0 flex flex-col min-h-0 pt-1">
              {/* Section title */}
              <div className="px-4 pt-4 pb-2 shrink-0 flex items-center gap-2">
                <span className="w-4 h-4 flex items-center justify-center text-rose-400/70 text-sm">
                  <i className="ri-image-2-line"></i>
                </span>
                <h2
                  className="text-sm font-semibold text-rose-600/70 tracking-wide"
                  style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  修补结果
                </h2>
              </div>
              <div className="mx-4 h-px bg-rose-100/60 shrink-0 mb-1" />

              <div className="flex-1 min-h-0 overflow-hidden">
                <ResultDisplay
                  results={currentResults}
                  outputCount={editorState.outputCount}
                  isProcessing={isProcessing}
                  onContinueRepair={handleContinueRepair}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <CuteConfirmModal
        isOpen={deleteConfirmTask !== null}
        title="确认删除任务？"
        message={
          deleteConfirmTask
            ? `将删除「${deleteConfirmTask.name}」及其数据库记录与本地图片文件，且不可恢复。`
            : ""
        }
        icon="delete"
        confirmText="确认删除"
        cancelText="取消"
        titleId="repair-delete-confirm-title"
        onConfirm={() => void handleDeleteConfirm()}
        onCancel={handleDeleteCancel}
      />

      <CuteConfirmModal
        isOpen={restartConfirmOpen}
        title="重新修补"
        message="该操作会删除当前结果并重新提交修补任务，是否继续？"
        icon="warning"
        confirmText="确认重新修补"
        cancelText="取消"
        titleId="repair-restart-confirm-title"
        onConfirm={handleRestartConfirm}
        onCancel={handleRestartCancel}
      />

      {/* ── Keyframes ─── */}
      <style>{`
        @keyframes floatUp {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-16px) scale(1.03); }
        }
        @keyframes twinkle {
          0%, 100% { opacity: 0.25; transform: scale(1) rotate(0deg); }
          50% { opacity: 0.6; transform: scale(1.3) rotate(20deg); }
        }
      `}</style>
    </div>
  );
}
