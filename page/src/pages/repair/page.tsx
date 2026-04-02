import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { mockRepairTasks, type RepairTask, type TaskStatus } from "@/mocks/repairTasks";
import TaskList from "./components/TaskList";
import TaskEditor, { type EditorState } from "./components/TaskEditor";
import ResultDisplay from "./components/ResultDisplay";

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

let nextTaskId = 100;

const defaultEditorState = (): EditorState => ({
  mainImage: "",
  prompt: "",
  referenceImages: [],
  outputCount: 1,
});

export default function RepairPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<RepairTask[]>(mockRepairTasks);
  const [selectedId, setSelectedId] = useState<string | null>(mockRepairTasks[0]?.id ?? null);
  const [editorMap, setEditorMap] = useState<Record<string, EditorState>>(() => {
    const m: Record<string, EditorState> = {};
    mockRepairTasks.forEach((t) => {
      m[t.id] = {
        mainImage: t.mainImage,
        prompt: t.prompt,
        referenceImages: t.referenceImages,
        outputCount: t.outputCount,
      };
    });
    return m;
  });
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());

  /* ── Derived current task ─── */
  const currentTask = tasks.find((t) => t.id === selectedId) ?? null;
  const currentEditor: EditorState = selectedId
    ? (editorMap[selectedId] ?? defaultEditorState())
    : defaultEditorState();
  const isProcessing = selectedId ? processingIds.has(selectedId) : false;
  const currentResults = currentTask?.results ?? [];

  /* ── Task actions ─── */
  const handleSelect = useCallback((id: string) => setSelectedId(id), []);

  const handleDelete = useCallback((id: string) => {
    setTasks((prev) => {
      const next = prev.filter((t) => t.id !== id);
      if (selectedId === id) {
        setSelectedId(next[0]?.id ?? null);
      }
      return next;
    });
    setEditorMap((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, [selectedId]);

  const handleNew = useCallback(() => {
    const id = `task-${++nextTaskId}`;
    const newTask: RepairTask = {
      id,
      name: `新任务 #${nextTaskId}`,
      status: "pending" as TaskStatus,
      createdAt: new Date().toISOString().split("T")[0],
      mainImage: "",
      prompt: "",
      referenceImages: [],
      outputCount: 1,
      results: [],
    };
    setTasks((prev) => [newTask, ...prev]);
    setEditorMap((prev) => ({ ...prev, [id]: defaultEditorState() }));
    setSelectedId(id);
  }, []);

  /* ── Editor change ─── */
  const handleEditorChange = useCallback(
    (next: Partial<EditorState>) => {
      if (!selectedId) return;
      setEditorMap((prev) => ({
        ...prev,
        [selectedId]: { ...(prev[selectedId] ?? defaultEditorState()), ...next },
      }));
    },
    [selectedId]
  );

  /* ── Continue repair: set result image as new main image ─── */
  const handleContinueRepair = useCallback(
    (imageUrl: string) => {
      if (!selectedId) return;
      // Update editor state: set result as main image, clear results
      setEditorMap((prev) => ({
        ...prev,
        [selectedId]: {
          ...(prev[selectedId] ?? defaultEditorState()),
          mainImage: imageUrl,
        },
      }));
      // Reset task results and status
      setTasks((prev) =>
        prev.map((t) =>
          t.id === selectedId
            ? { ...t, status: "pending" as TaskStatus, results: [] }
            : t
        )
      );
    },
    [selectedId]
  );

  /* ── Submit ─── */
  const handleSubmit = useCallback(() => {
    if (!selectedId) return;
    const editor = editorMap[selectedId];
    if (!editor?.mainImage || !editor.prompt.trim()) return;

    // Update task status to processing
    setTasks((prev) =>
      prev.map((t) => (t.id === selectedId ? { ...t, status: "processing" as TaskStatus } : t))
    );
    setProcessingIds((prev) => new Set(prev).add(selectedId));

    // Simulate processing — complete after 3s
    const sid = selectedId;
    setTimeout(() => {
      const mockResults = Array.from({ length: editor.outputCount }).map(
        (_, i) =>
          `https://readdy.ai/api/search-image?query=cute%20anime%20character%20image%20repair%20result%2C%20soft%20pastel%20kawaii%20illustration%20style%2C%20beautiful%20digital%20art%2C%20refined%20smooth%20details%2C%20pink%20rose%20watercolor%20aesthetic%2C%20clean%20background&width=512&height=512&seq=res${sid}${i}&orientation=squarish`
      );
      setTasks((prev) =>
        prev.map((t) =>
          t.id === sid
            ? { ...t, status: "completed" as TaskStatus, results: mockResults }
            : t
        )
      );
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(sid);
        return next;
      });
    }, 3000);
  }, [selectedId, editorMap]);

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
                onDelete={handleDelete}
                onNew={handleNew}
              />
            </div>

            {/* ── Center: Editor ─── */}
            <div
              className="flex-1 flex flex-col min-h-0 border-r border-rose-100/60 pt-1"
              style={{ minWidth: 0 }}
            >
              {/* Section title */}
              <div className="px-5 pt-4 pb-2 shrink-0 flex items-center gap-2">
                <span className="w-4 h-4 flex items-center justify-center text-rose-400/70 text-sm">
                  <i className="ri-edit-2-line"></i>
                </span>
                <h2
                  className="text-sm font-semibold text-rose-600/70 tracking-wide"
                  style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  {currentTask ? currentTask.name : "选择任务开始编辑"}
                </h2>
              </div>
              <div className="mx-5 h-px bg-rose-100/60 shrink-0 mb-1" />

              {selectedId ? (
                <TaskEditor
                  key={selectedId}
                  state={currentEditor}
                  onChange={handleEditorChange}
                  onSubmit={handleSubmit}
                  isProcessing={isProcessing}
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
                  outputCount={currentEditor.outputCount}
                  isProcessing={isProcessing}
                  onContinueRepair={handleContinueRepair}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

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
