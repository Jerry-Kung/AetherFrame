import { useRef, useState, useEffect, useCallback } from "react";
import type { PromptTemplate } from "@/mocks/repairTasks";
import {
  enrichPromptTemplates,
  setCustomTemplateDescription,
  removeCustomTemplateDescription,
} from "@/mocks/repairTasks";
import {
  getTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
} from "@/services/repairApi";
import TemplateModal from "./TemplateModal";

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
  /** 当前任务 id：切换任务时收起模板面板与弹窗 */
  taskId?: string | null;
  /** 模板 CRUD / 加载失败时提示 */
  onTemplateError?: (message: string) => void;
}

const OUTPUT_OPTIONS: (1 | 2 | 4)[] = [1, 2, 4];

type ModalMode = { type: "create" } | { type: "edit"; template: PromptTemplate };

const TaskEditor = ({
  state,
  onChange,
  onSubmit,
  onMainImageUpload,
  onRefImagesUpload,
  onRemoveRefImage,
  isProcessing,
  isUploading = false,
  taskId,
  onTemplateError,
}: TaskEditorProps) => {
  const mainInputRef = useRef<HTMLInputElement>(null);
  const refInputRef = useRef<HTMLInputElement>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [mainDragOver, setMainDragOver] = useState(false);

  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);

  const [modalMode, setModalMode] = useState<ModalMode | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const refreshTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const list = await getTemplates();
      setTemplates(enrichPromptTemplates(list));
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载模板失败";
      onTemplateError?.(message);
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
  }, [onTemplateError]);

  /** 仅在展开「选用模板」面板时拉取列表，避免随父组件轮询重渲染反复请求 */
  const toggleTemplatePanel = useCallback(() => {
    setShowTemplates((open) => {
      if (open) return false;
      void refreshTemplates();
      return true;
    });
  }, [refreshTemplates]);

  useEffect(() => {
    setShowTemplates(false);
    setDeleteConfirmId(null);
    setModalMode(null);
  }, [taskId]);

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
      onMainImageUpload(file);
    } else {
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
      onRefImagesUpload(selected);
    } else {
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

  const handleSaveTemplate = async (data: { label: string; description: string; text: string }) => {
    if (!modalMode) return;
    try {
      if (modalMode.type === "create") {
        const created = await createTemplate({
          label: data.label,
          text: data.text,
          description: data.description,
        });
        setCustomTemplateDescription(created.id, "");
      } else {
        const t = modalMode.template;
        await updateTemplate(t.id, {
          label: data.label,
          text: data.text,
          description: data.description,
        });
        setCustomTemplateDescription(t.id, "");
      }
      await refreshTemplates();
      setModalMode(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "保存模板失败";
      onTemplateError?.(message);
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    try {
      await deleteTemplate(id);
      removeCustomTemplateDescription(id);
      setDeleteConfirmId(null);
      await refreshTemplates();
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除模板失败";
      onTemplateError?.(message);
      setDeleteConfirmId(null);
    }
  };

  const canSubmit = !!state.mainImage && !!state.prompt.trim() && !isProcessing && !isUploading;

  return (
    <>
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
                  type="button"
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
              onDragOver={(e) => {
                e.preventDefault();
                setMainDragOver(true);
              }}
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
          <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
            <label className="flex items-center gap-1.5 text-xs font-semibold text-rose-600/70 tracking-wide shrink-0">
              <span className="w-3.5 h-3.5 flex items-center justify-center">
                <i className="ri-quill-pen-line"></i>
              </span>
              修补 Prompt
            </label>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setModalMode({ type: "create" })}
                className="flex items-center gap-1 text-xs text-rose-400/70 hover:text-rose-600 cursor-pointer transition-colors whitespace-nowrap"
              >
                <i className="ri-add-circle-line text-xs"></i>
                新建模板
              </button>
              <span className="text-rose-200/60 text-xs" aria-hidden>
                |
              </span>
              <button
                type="button"
                onClick={toggleTemplatePanel}
                className="flex items-center gap-1 text-xs text-pink-400 hover:text-pink-600 cursor-pointer transition-colors whitespace-nowrap"
              >
                <i className="ri-magic-line text-xs"></i>
                选用模板
              </button>
            </div>
          </div>

          {showTemplates && (
            <div
              className="mb-2 rounded-xl border border-pink-100 overflow-hidden"
              style={{ background: "rgba(255,255,255,0.88)" }}
            >
              {templatesLoading ? (
                <div className="px-4 py-5 text-center text-xs text-rose-300/60">
                  <span className="inline-flex items-center gap-2">
                    <i className="ri-loader-4-line animate-spin"></i>
                    加载模板中…
                  </span>
                </div>
              ) : templates.length === 0 ? (
                <div className="px-4 py-6 text-center text-xs text-rose-400/70 space-y-2">
                  <i className="ri-inbox-2-line text-2xl text-rose-300/50 block"></i>
                  <p className="text-rose-500/80 font-medium">还没有任何 Prompt 模板</p>
                  <p className="text-rose-300/70 leading-relaxed max-w-xs mx-auto">
                    可点击右上角「新建模板」添加常用修补说明；有模板后会在此列出，一键填入 Prompt。
                  </p>
                </div>
              ) : (
                templates.map((tpl) => (
                  <div
                    key={tpl.id}
                    className="group flex items-start gap-2 px-3 py-2.5 border-b border-pink-50/60 last:border-0 hover:bg-pink-50/50 transition-colors"
                  >
                    <button
                      type="button"
                      onClick={() => applyTemplate(tpl.text)}
                      className="flex-1 text-left min-w-0 cursor-pointer"
                    >
                      <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                        <span className="font-semibold text-xs text-rose-600/80">{tpl.label}</span>
                        {tpl.description ? (
                          <span className="text-rose-400/55 text-xs line-clamp-1 min-w-0">{tpl.description}</span>
                        ) : null}
                      </div>
                      <p className="text-xs text-rose-400/50 line-clamp-2 leading-relaxed">{tpl.text}</p>
                    </button>

                    {!tpl.is_builtin && (
                      <div className="flex items-center gap-1 shrink-0 pt-0.5">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setModalMode({ type: "edit", template: tpl });
                          }}
                          title="修改模板"
                          className="w-6 h-6 flex items-center justify-center rounded-lg text-rose-300/70 hover:text-pink-500 hover:bg-pink-50 transition-all cursor-pointer"
                        >
                          <i className="ri-edit-2-line text-xs"></i>
                        </button>
                        {deleteConfirmId === tpl.id ? (
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleDeleteTemplate(tpl.id);
                              }}
                              className="px-1.5 py-0.5 rounded-md text-xs text-white bg-rose-400 hover:bg-rose-500 cursor-pointer whitespace-nowrap transition-colors"
                            >
                              确认
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeleteConfirmId(null);
                              }}
                              className="px-1.5 py-0.5 rounded-md text-xs text-rose-400/70 hover:text-rose-500 cursor-pointer whitespace-nowrap transition-colors"
                            >
                              取消
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeleteConfirmId(tpl.id);
                            }}
                            title="删除模板"
                            className="w-6 h-6 flex items-center justify-center rounded-lg text-rose-300/70 hover:text-rose-500 hover:bg-rose-50 transition-all cursor-pointer"
                          >
                            <i className="ri-delete-bin-6-line text-xs"></i>
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
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
                  type="button"
                  onClick={() => removeRefImageHandler(idx)}
                  className="absolute top-0.5 right-0.5 w-4 h-4 flex items-center justify-center rounded-full bg-rose-500/80 text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                >
                  <i className="ri-close-line text-xs leading-none"></i>
                </button>
              </div>
            ))}

            {canAddRef && (
              <button
                type="button"
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
                type="button"
                onClick={() => onChange({ outputCount: n })}
                className={[
                  "flex-1 py-2 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap",
                  state.outputCount === n
                    ? "bg-gradient-to-r from-pink-400 to-rose-400 text-white"
                    : "bg-rose-50/60 text-rose-400/60 hover:bg-rose-100/50 hover:text-rose-500",
                ].join(" ")}
                style={state.outputCount === n ? { fontFamily: "'ZCOOL KuaiLe', cursive" } : {}}
              >
                {n} 张
              </button>
            ))}
          </div>
        </section>

        {/* ── 5. Submit ─── */}
        <div className="pt-1 pb-2">
          <button
            type="button"
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

      {modalMode && (
        <TemplateModal
          key={modalMode.type === "edit" ? modalMode.template.id : "create"}
          template={modalMode.type === "edit" ? modalMode.template : undefined}
          onSave={(data) => void handleSaveTemplate(data)}
          onClose={() => setModalMode(null)}
        />
      )}
    </>
  );
};

export default TaskEditor;
