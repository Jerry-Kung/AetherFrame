import { useRef, useState, useEffect } from "react";

export interface EditorState {
  mainImage: string;
  prompt: string;
  referenceImages: string[];
  outputCount: 1 | 2 | 4;
}

interface TaskEditorProps {
  state: EditorState;
  onChange: (next: Partial<EditorState>) => void;
  onSubmit: () => void;
  onMainImageUpload?: (file: File) => void;
  onRefImagesUpload?: (files: File[]) => void;
  onRemoveRefImage?: (idx: number) => void;
  isProcessing: boolean;
  isUploading?: boolean;
}

const OUTPUT_OPTIONS: (1 | 2 | 4)[] = [1, 2, 4];

// 内置Prompt模板
const PROMPT_TEMPLATES = [
  { id: "t1", label: "皮肤瑕疵修补", text: "修补人物皮肤上的瑕疵，保持原有的动漫风格和色调，使皮肤光滑自然，细节真实。" },
  { id: "t2", label: "水印去除", text: "完整去除图片中的水印、文字标记及logo，自然填充背景，不留痕迹。" },
  { id: "t3", label: "背景噪点修复", text: "修复背景区域的噪点、模糊和色差问题，使背景干净清晰，与前景融合自然。" },
  { id: "t4", label: "角色轮廓补全", text: "补全残缺或被遮挡的动漫角色轮廓，风格保持一致，线条流畅自然。" },
  { id: "t5", label: "服装细节修复", text: "修复衣物皱褶、配饰残损等细节问题，保持角色整体风格统一，细节精致。" },
  { id: "t6", label: "眼睛高光补绘", text: "为角色眼睛添加或修复高光点，增强眼神灵动感，符合二次元美图风格。" },
];

const TaskEditor = ({ 
  state, 
  onChange, 
  onSubmit, 
  onMainImageUpload,
  onRefImagesUpload,
  onRemoveRefImage,
  isProcessing,
  isUploading = false
}: TaskEditorProps) => {
  const mainInputRef = useRef<HTMLInputElement>(null);
  const refInputRef = useRef<HTMLInputElement>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [mainDragOver, setMainDragOver] = useState(false);

  /* ── File to base64 ─── */
  const fileToUrl = (file: File): Promise<string> =>
    new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.readAsDataURL(file);
    });

  /* ── Main image handlers ─── */
  const handleMainFile = async (file: File) => {
    if (!file.type.startsWith("image/")) return;
    
    if (onMainImageUpload) {
      // 使用父组件提供的上传函数
      onMainImageUpload(file);
    } else {
      // 降级：本地预览
      const url = await fileToUrl(file);
      onChange({ mainImage: url });
    }
  };

  const handleMainDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setMainDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleMainFile(file);
  };

  /* ── Reference image handlers ─── */
  const handleRefFiles = async (files: FileList) => {
    const remaining = 5 - state.referenceImages.length;
    if (remaining <= 0) return;
    const selected = Array.from(files).slice(0, remaining);
    
    if (onRefImagesUpload) {
      // 使用父组件提供的上传函数
      onRefImagesUpload(selected);
    } else {
      // 降级：本地预览
      const urls = await Promise.all(selected.filter((f) => f.type.startsWith("image/")).map(fileToUrl));
      onChange({ referenceImages: [...state.referenceImages, ...urls] });
    }
  };

  const removeRefImageHandler = (idx: number) => {
    if (onRemoveRefImage) {
      onRemoveRefImage(idx);
    } else {
      const next = [...state.referenceImages];
      next.splice(idx, 1);
      onChange({ referenceImages: next });
    }
  };

  const canAddRef = state.referenceImages.length < 5;

  /* ── Prompt template ─── */
  const applyTemplate = (text: string) => {
    onChange({ prompt: text });
    setShowTemplates(false);
  };

  const canSubmit = !!state.mainImage && !!state.prompt.trim() && !isProcessing && !isUploading;

  return (
    <div className="flex flex-col h-full overflow-y-auto px-5 py-4 space-y-4">

      {/* ── 1. Main image upload ─── */}
      <section>
        <label className="flex items-center gap-1.5 text-xs font-semibold text-rose-600/70 mb-2 tracking-wide">
          <span className="w-3.5 h-3.5 flex items-center justify-center">
            <i className="ri-image-line"></i>
          </span>
          待修补主图
          <span className="text-rose-300/50 font-normal ml-1">· 仅支持 1 张</span>
        </label>

        {state.mainImage ? (
          <div className="relative group rounded-2xl overflow-hidden border border-rose-100/80 w-full aspect-video max-h-48">
            <img
              src={state.mainImage}
              alt="主图预览"
              className="w-full h-full object-contain bg-rose-50/30"
            />
            <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <button
                onClick={() => onChange({ mainImage: "" })}
                className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/90 text-rose-500 text-xs font-medium cursor-pointer hover:bg-white transition-all whitespace-nowrap"
              >
                <i className="ri-refresh-line"></i>
                更换图片
              </button>
            </div>
          </div>
        ) : (
          <div
            onClick={() => mainInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setMainDragOver(true); }}
            onDragLeave={() => setMainDragOver(false)}
            onDrop={handleMainDrop}
            className={[
              "w-full rounded-2xl border-2 border-dashed flex flex-col items-center justify-center py-8 cursor-pointer transition-all duration-200",
              mainDragOver
                ? "border-pink-400 bg-pink-50/60"
                : "border-rose-200/60 bg-rose-50/20 hover:border-pink-300 hover:bg-pink-50/30",
            ].join(" ")}
          >
            <span className="text-2xl text-rose-300/70 mb-2">
              <i className="ri-upload-cloud-2-line"></i>
            </span>
            <p className="text-xs text-rose-400/60">点击或拖拽上传图片</p>
            <p className="text-xs text-rose-300/40 mt-0.5">JPG / PNG / WEBP</p>
          </div>
        )}
        <input
          ref={mainInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleMainFile(e.target.files[0])}
        />
      </section>

      {/* ── 2. Prompt input ─── */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <label className="flex items-center gap-1.5 text-xs font-semibold text-rose-600/70 tracking-wide">
            <span className="w-3.5 h-3.5 flex items-center justify-center">
              <i className="ri-quill-pen-line"></i>
            </span>
            修补 Prompt
          </label>
          <button
            onClick={() => setShowTemplates((v) => !v)}
            className="flex items-center gap-1 text-xs text-pink-400 hover:text-pink-600 cursor-pointer transition-colors whitespace-nowrap"
          >
            <i className="ri-magic-line text-xs"></i>
            选用模板
          </button>
        </div>

        {/* Template panel */}
        {showTemplates && (
          <div
            className="mb-2 rounded-xl border border-pink-100 overflow-hidden"
            style={{ background: "rgba(255,255,255,0.85)" }}
          >
            {PROMPT_TEMPLATES.map((tpl) => (
              <button
                key={tpl.id}
                onClick={() => applyTemplate(tpl.text)}
                className="w-full text-left px-3 py-2 text-xs hover:bg-pink-50/80 transition-colors cursor-pointer border-b border-pink-50/60 last:border-0"
              >
                <span className="font-medium text-rose-600/80 mr-2">{tpl.label}</span>
                <span className="text-rose-400/50 line-clamp-1">{tpl.text}</span>
              </button>
            ))}
          </div>
        )}

        <textarea
          value={state.prompt}
          onChange={(e) => onChange({ prompt: e.target.value })}
          placeholder="请描述你想要的修补效果，比如：修补人物皮肤瑕疵，保持动漫风格..."
          rows={4}
          className="w-full rounded-xl border border-rose-100/80 bg-white/60 px-3 py-2.5 text-sm text-rose-900/70 placeholder:text-rose-300/50 focus:outline-none focus:border-pink-300/80 focus:bg-white/80 transition-all resize-none"
        />
      </section>

      {/* ── 3. Reference images ─── */}
      <section>
        <label className="flex items-center gap-1.5 text-xs font-semibold text-rose-600/70 mb-2 tracking-wide">
          <span className="w-3.5 h-3.5 flex items-center justify-center">
            <i className="ri-image-add-line"></i>
          </span>
          参考图
          <span className="text-rose-300/50 font-normal ml-1">· 最多 5 张</span>
        </label>

        <div className="flex items-center gap-2 flex-wrap">
          {state.referenceImages.map((url, idx) => (
            <div key={idx} className="relative group w-16 h-16 rounded-xl overflow-hidden border border-rose-100/80 shrink-0">
              <img src={url} alt={`参考图${idx + 1}`} className="w-full h-full object-cover" />
              <button
                onClick={() => removeRefImageHandler(idx)}
                className="absolute top-0.5 right-0.5 w-4 h-4 flex items-center justify-center rounded-full bg-rose-500/80 text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
              >
                <i className="ri-close-line text-xs leading-none"></i>
              </button>
            </div>
          ))}

          {canAddRef && (
            <button
              onClick={() => refInputRef.current?.click()}
              className="w-16 h-16 rounded-xl border-2 border-dashed border-rose-200/60 flex flex-col items-center justify-center cursor-pointer hover:border-pink-300 hover:bg-pink-50/30 transition-all shrink-0"
            >
              <i className="ri-add-line text-rose-300/60 text-base"></i>
            </button>
          )}
        </div>

        <input
          ref={refInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && handleRefFiles(e.target.files)}
        />
      </section>

      {/* ── 4. Output count ─── */}
      <section>
        <label className="flex items-center gap-1.5 text-xs font-semibold text-rose-600/70 mb-2 tracking-wide">
          <span className="w-3.5 h-3.5 flex items-center justify-center">
            <i className="ri-layout-grid-line"></i>
          </span>
          输出数量
        </label>
        <div className="flex items-center gap-2">
          {OUTPUT_OPTIONS.map((n) => (
            <button
              key={n}
              onClick={() => onChange({ outputCount: n })}
              className={[
                "flex-1 py-2 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap",
                state.outputCount === n
                  ? "bg-gradient-to-r from-pink-400 to-rose-400 text-white"
                  : "bg-rose-50/60 text-rose-400/60 hover:bg-rose-100/50 hover:text-rose-500",
              ].join(" ")}
              style={
                state.outputCount === n
                  ? { fontFamily: "'ZCOOL KuaiLe', cursive" }
                  : {}
              }
            >
              {n} 张
            </button>
          ))}
        </div>
      </section>

      {/* ── 5. Submit ─── */}
      <div className="pt-1 pb-2">
        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          className={[
            "w-full py-3 rounded-2xl font-semibold text-base tracking-wide whitespace-nowrap cursor-pointer transition-all duration-300",
            canSubmit
              ? "bg-gradient-to-r from-pink-400 to-rose-500 text-white hover:from-pink-500 hover:to-rose-600 active:scale-[0.98]"
              : "bg-rose-100/60 text-rose-300/50 cursor-not-allowed",
          ].join(" ")}
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          {isProcessing || isUploading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 flex items-center justify-center animate-spin">
                <i className="ri-loader-4-line"></i>
              </span>
              {isUploading ? "上传中…" : "修补中…"}
            </span>
          ) : (
            <span className="flex items-center justify-center gap-1.5">
              <span className="w-4 h-4 flex items-center justify-center">
                <i className="ri-eraser-line"></i>
              </span>
              开始修补
            </span>
          )}
        </button>
      </div>
    </div>
  );
};

export default TaskEditor;
