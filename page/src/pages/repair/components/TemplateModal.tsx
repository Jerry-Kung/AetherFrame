import { useEffect, useRef, useState } from "react";
import type { PromptTemplate } from "@/mocks/repairTasks";

interface TemplateModalProps {
  /** 传入时为编辑模式 */
  template?: PromptTemplate;
  onSave: (data: { label: string; description: string; text: string }) => void;
  onClose: () => void;
}

const MAX_TITLE = 40;
const MAX_DESC = 100;
const MAX_TEXT_LEN = 5000;

const TemplateModal = ({ template, onSave, onClose }: TemplateModalProps) => {
  const isEdit = !!template;

  const [label, setLabel] = useState(template?.label ?? "");
  const [description, setDescription] = useState(template?.description ?? "");
  const [text, setText] = useState(template?.text ?? "");
  const [errors, setErrors] = useState<{ label?: string; text?: string }>({});

  const backdropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLabel(template?.label ?? "");
    setDescription(template?.description ?? "");
    setText(template?.text ?? "");
    setErrors({});
  }, [template]);

  useEffect(() => {
    const timer = setTimeout(() => {
      (document.getElementById("tpl-label-input") as HTMLInputElement)?.focus();
    }, 80);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const validate = () => {
    const errs: { label?: string; text?: string } = {};
    const tLabel = label.trim();
    if (!tLabel) errs.label = "模板标题不能为空";
    else if (tLabel.length > MAX_TITLE) errs.label = `模板标题不能超过 ${MAX_TITLE} 字`;
    if (!text.trim()) errs.text = "模板内容不能为空";
    if (text.length > MAX_TEXT_LEN) errs.text = `模板内容不能超过 ${MAX_TEXT_LEN} 字`;
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = () => {
    if (!validate()) return;
    onSave({
      label: label.trim(),
      description: description.trim().slice(0, MAX_DESC),
      text: text.trim(),
    });
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === backdropRef.current) onClose();
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
        aria-labelledby="tpl-modal-title"
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

        <div className="flex items-center justify-between px-7 pt-5 pb-4 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <span
              className="w-8 h-8 flex items-center justify-center rounded-xl text-white text-sm shrink-0"
              style={{ background: "linear-gradient(135deg, #f9a8d4, #fb7185)" }}
            >
              <i className={isEdit ? "ri-edit-2-line" : "ri-add-line"}></i>
            </span>
            <h2
              id="tpl-modal-title"
              className="text-lg text-rose-700/90 truncate"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              {isEdit ? "修改模板" : "新建模板"}
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

        <div className="flex-1 min-h-0 overflow-y-auto px-7 pb-2 space-y-5">
          <div>
            <label className="flex items-center gap-1.5 text-xs font-semibold text-rose-600/70 mb-1.5 tracking-wide">
              <span className="w-3.5 h-3.5 flex items-center justify-center">
                <i className="ri-price-tag-3-line"></i>
              </span>
              模板标题
              <span className="text-rose-400/50 font-normal">· 必填，最多 {MAX_TITLE} 字</span>
            </label>
            <input
              id="tpl-label-input"
              type="text"
              value={label}
              onChange={(e) => {
                setLabel(e.target.value);
                setErrors((p) => ({ ...p, label: undefined }));
              }}
              placeholder="例如：皮肤瑕疵修补"
              maxLength={MAX_TITLE}
              className={[
                "w-full rounded-xl border px-3.5 py-2.5 text-sm text-rose-900/80 placeholder:text-rose-300/50 focus:outline-none transition-all bg-white/70",
                errors.label
                  ? "border-rose-400/70 focus:border-rose-400"
                  : "border-rose-100/80 focus:border-pink-300/80 focus:bg-white/90",
              ].join(" ")}
            />
            <div className="flex justify-end mt-0.5">
              <span className="text-xs tabular-nums text-rose-300/60">{label.length} / {MAX_TITLE}</span>
            </div>
            {errors.label && (
              <p className="mt-1 text-xs text-rose-400 flex items-center gap-1">
                <i className="ri-error-warning-line"></i>
                {errors.label}
              </p>
            )}
          </div>

          <div>
            <label className="flex items-center gap-1.5 text-xs font-semibold text-rose-600/70 mb-1.5 tracking-wide">
              <span className="w-3.5 h-3.5 flex items-center justify-center">
                <i className="ri-file-text-line"></i>
              </span>
              模板描述
              <span className="text-rose-400/50 font-normal">· 选填，最多 {MAX_DESC} 字</span>
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value.slice(0, MAX_DESC))}
              placeholder="例如：适用于修复人物皮肤上的痘印、划痕等瑕疵"
              maxLength={MAX_DESC}
              className="w-full rounded-xl border border-rose-100/80 bg-white/70 px-3.5 py-2.5 text-sm text-rose-900/80 placeholder:text-rose-300/50 focus:outline-none focus:border-pink-300/80 focus:bg-white/90 transition-all"
            />
            <div className="flex justify-end mt-0.5">
              <span className="text-xs tabular-nums text-rose-300/60">{description.length} / {MAX_DESC}</span>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5 gap-2">
              <label className="flex items-center gap-1.5 text-xs font-semibold text-rose-600/70 tracking-wide">
                <span className="w-3.5 h-3.5 flex items-center justify-center shrink-0">
                  <i className="ri-quill-pen-line"></i>
                </span>
                模板内容
                <span className="text-rose-400/50 font-normal hidden sm:inline">· 必填，将作为 Prompt 填入</span>
              </label>
              <span
                className={[
                  "text-xs tabular-nums shrink-0",
                  text.length > MAX_TEXT_LEN ? "text-rose-500 font-semibold" : "text-rose-300/60",
                ].join(" ")}
              >
                {text.length} / {MAX_TEXT_LEN}
              </span>
            </div>
            <textarea
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setErrors((p) => ({ ...p, text: undefined }));
              }}
              placeholder="请输入完整的 Prompt 内容，描述修补效果、风格要求、细节处理方式等..."
              rows={14}
              maxLength={MAX_TEXT_LEN}
              className={[
                "w-full rounded-xl border px-3.5 py-3 text-sm text-rose-900/80 placeholder:text-rose-300/50 focus:outline-none transition-all resize-none bg-white/70 leading-relaxed",
                errors.text
                  ? "border-rose-400/70 focus:border-rose-400"
                  : "border-rose-100/80 focus:border-pink-300/80 focus:bg-white/90",
              ].join(" ")}
            />
            {errors.text && (
              <p className="mt-1 text-xs text-rose-400 flex items-center gap-1">
                <i className="ri-error-warning-line"></i>
                {errors.text}
              </p>
            )}
          </div>

          <div
            className="rounded-xl px-4 py-3 text-xs text-rose-500/70 leading-relaxed"
            style={{ background: "rgba(255,228,230,0.4)" }}
          >
            <span className="font-semibold text-rose-500/80">
              <i className="ri-lightbulb-line mr-1"></i>小提示：
            </span>
            模板内容会直接填入修补 Prompt 输入框，建议写清修补目标、风格与细节，越具体越利于模型理解。
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-7 py-5 shrink-0 border-t border-rose-50/80">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl text-sm text-rose-400/80 hover:text-rose-500 hover:bg-rose-50/60 transition-all cursor-pointer whitespace-nowrap"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white cursor-pointer transition-all duration-200 active:scale-[0.97] whitespace-nowrap"
            style={{ background: "linear-gradient(135deg, #f9a8d4, #fb7185)" }}
          >
            <span className="flex items-center gap-1.5">
              <i className={isEdit ? "ri-save-line" : "ri-add-circle-line"}></i>
              {isEdit ? "保存修改" : "创建模板"}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default TemplateModal;
