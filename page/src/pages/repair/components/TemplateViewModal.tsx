import { useEffect, useRef } from "react";
import type { PromptTemplate } from "@/repair/repairTemplateUtils";

interface TemplateViewModalProps {
  template: PromptTemplate;
  onClose: () => void;
  /** 选用后填入 Prompt 并关闭 */
  onApply: (text: string) => void;
}

const TemplateViewModal = ({ template, onClose, onApply }: TemplateViewModalProps) => {
  const backdropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === backdropRef.current) onClose();
  };

  const handleApply = () => {
    onApply(template.text);
    onClose();
  };

  return (
    <div
      ref={backdropRef}
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(255,220,230,0.35)", backdropFilter: "blur(6px)" }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tpl-view-modal-title"
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-2xl rounded-3xl overflow-hidden flex flex-col"
        style={{
          background: "rgba(255,255,255,0.92)",
          border: "1.5px solid rgba(255,182,193,0.45)",
          boxShadow: "0 8px 40px rgba(255,100,130,0.12)",
          maxHeight: "90vh",
        }}
      >
        <div className="h-1.5 w-full bg-gradient-to-r from-pink-300 via-rose-300 to-pink-200 shrink-0" />

        <div className="flex items-center justify-between px-7 pt-5 pb-3 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <span
              className="w-8 h-8 flex items-center justify-center rounded-xl text-white text-sm shrink-0"
              style={{ background: "linear-gradient(135deg, #f9a8d4, #fb7185)" }}
            >
              <i className="ri-eye-line"></i>
            </span>
            <h2
              id="tpl-view-modal-title"
              className="text-lg text-rose-700/90 truncate"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              查看模板
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full text-rose-300 hover:text-rose-500 hover:bg-rose-50 transition-all cursor-pointer shrink-0"
          >
            <i className="ri-close-line text-lg"></i>
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-7 pb-2 space-y-4">
          <div>
            <p className="text-xs font-semibold text-rose-600/70 mb-1 tracking-wide">标题</p>
            <p className="text-sm text-rose-900/85 font-medium">{template.label}</p>
          </div>

          {template.description ? (
            <div>
              <p className="text-xs font-semibold text-rose-600/70 mb-1 tracking-wide">描述</p>
              <p className="text-sm text-rose-700/75 leading-relaxed">{template.description}</p>
            </div>
          ) : null}

          <div>
            <p className="text-xs font-semibold text-rose-600/70 mb-1.5 tracking-wide">标签</p>
            {template.tags.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {template.tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs text-rose-700/85 border border-pink-200/70 bg-pink-50/50"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-rose-300/70">暂无标签</p>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold text-rose-600/70 mb-1.5 tracking-wide">Prompt 内容</p>
            <textarea
              readOnly
              value={template.text}
              rows={12}
              className="w-full rounded-xl border border-rose-100/80 bg-rose-50/30 px-3.5 py-3 text-sm text-rose-900/80 leading-relaxed resize-none focus:outline-none cursor-default"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-7 py-5 shrink-0 border-t border-rose-50/80">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl text-sm text-rose-400/80 hover:text-rose-500 hover:bg-rose-50/60 transition-all cursor-pointer whitespace-nowrap"
          >
            关闭
          </button>
          <button
            type="button"
            onClick={handleApply}
            className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white cursor-pointer transition-all duration-200 active:scale-[0.97] whitespace-nowrap"
            style={{ background: "linear-gradient(135deg, #f9a8d4, #fb7185)" }}
          >
            <span className="flex items-center gap-1.5">
              <i className="ri-magic-line"></i>
              选用此模板
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default TemplateViewModal;
