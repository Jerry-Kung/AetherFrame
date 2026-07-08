import { useState, useCallback } from "react";
import type { QuickCreateImage } from "@/types/quickCreate";

interface ImageFeedbackModalProps {
  image: QuickCreateImage;
  promptTitle: string;
  onSave: (feedbackText: string, legFootBad: boolean) => Promise<void>;
  onClose: () => void;
}

/** 单张产线出图的人工 feedback 填写弹窗（文本 + 腿脚崩坏勾选；清空保存 = 清除） */
export default function ImageFeedbackModal({
  image,
  promptTitle,
  onSave,
  onClose,
}: ImageFeedbackModalProps) {
  const [text, setText] = useState(image.userFeedback?.feedbackText ?? "");
  const [legFootBad, setLegFootBad] = useState(image.userFeedback?.legFootBad ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(text, legFootBad);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }, [onSave, onClose, text, legFootBad]);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
        onClick={saving ? undefined : onClose}
      />
      <div
        className="relative w-96 max-w-[calc(100vw-2rem)] rounded-3xl overflow-hidden mx-4"
        style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pt-6 pb-4 px-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-14 h-14 rounded-xl overflow-hidden shrink-0 border border-rose-100">
              <img src={image.url} alt="" className="w-full h-full object-cover object-top" />
            </div>
            <div className="min-w-0">
              <h3
                className="text-base font-bold text-rose-600"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                填写人工 Feedback
              </h3>
              <p className="text-xs text-rose-400/60 truncate">{promptTitle}</p>
            </div>
          </div>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            placeholder="记录这张图的问题或亮点（腿/脚/袜、画风、构图…）；留空且不勾选，保存即清除 feedback"
            className="w-full rounded-xl p-3 text-sm text-rose-700/80 resize-none focus:outline-none"
            style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.25)" }}
          />

          <label className="flex items-center gap-2 mt-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={legFootBad}
              onChange={(e) => setLegFootBad(e.target.checked)}
              className="w-4 h-4 accent-rose-400"
            />
            <span
              className="text-sm font-medium text-rose-600"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              腿脚崩坏
            </span>
            <span className="text-xs text-rose-300/60">（计入 Case 的 bad 计数）</span>
          </label>

          {error && (
            <p className="mt-2 text-xs text-rose-600" role="alert">
              {error}
            </p>
          )}
        </div>

        <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />
        <div className="flex gap-3 p-4">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="flex-1 py-2.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "rgba(253,164,175,0.08)",
              color: "#f472b6",
              border: "1px solid rgba(244,114,182,0.2)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              opacity: saving ? 0.5 : 1,
            }}
          >
            取消
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
