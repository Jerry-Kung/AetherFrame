import { useEffect, useState } from "react";
import type { Divergence } from "@/types/material";
import { MATERIAL_ERROR_CODES } from "@/types/material";
import { readApiErrorCode } from "@/services/materialApi";
import { ApiError } from "@/services/api";

export default function DirectionGenerateModal({
  open,
  currentCount,
  limit,
  initialDraft,
  onClose,
  onSubmit,
}: {
  open: boolean;
  currentCount: number;
  limit: number;
  initialDraft?: { divergence: Divergence; initialInput: string } | null;
  onClose: () => void;
  onSubmit: (divergence: Divergence, initialInput: string | null) => Promise<void>;
}) {
  const [divergence, setDivergence] = useState<Divergence>("low");
  const [initialInput, setInitialInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDivergence(initialDraft?.divergence ?? "low");
    setInitialInput(initialDraft?.initialInput ?? "");
    setErrorText(null);
  }, [open, initialDraft]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const atLimit = currentCount >= limit;
  const remaining = Math.max(0, limit - currentCount);

  const handleSubmit = async () => {
    if (atLimit || submitting) return;
    setSubmitting(true);
    setErrorText(null);
    try {
      await onSubmit(divergence, initialInput.trim() || null);
    } catch (e) {
      const code = readApiErrorCode(e);
      if (code === MATERIAL_ERROR_CODES.DIRECTION_LIMIT_EXCEEDED) {
        setErrorText("方向已达上限 20 条，请先删除部分再生成新方向");
      } else if (code === MATERIAL_ERROR_CODES.TASK_CONCURRENCY_EXCEEDED) {
        setErrorText("该角色已有 2 个任务在跑，请等一个完成再来");
      } else {
        setErrorText(e instanceof ApiError ? e.message : "提交失败");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="absolute inset-0"
        style={{ backdropFilter: "blur(6px)", background: "rgba(15,23,42,0.25)" }}
      />
      <div
        className="relative w-full max-w-md rounded-2xl p-6 shadow-xl"
        style={{ background: "rgba(255,255,255,0.95)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3
          className="text-lg font-bold text-rose-600 mb-4"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          生成新创意方向
        </h3>
        <p className="text-sm text-rose-500/80 mb-4">
          当前 {currentCount} / {limit} — 还可再生成 {remaining} 条
        </p>
        <fieldset className="mb-4 space-y-2">
          <legend className="text-sm text-rose-600 mb-2">发散度</legend>
          {(["low", "mid", "high"] as Divergence[]).map((d) => (
            <label key={d} className="flex items-center gap-2 text-sm text-rose-700 cursor-pointer">
              <input
                type="radio"
                name="divergence"
                checked={divergence === d}
                onChange={() => setDivergence(d)}
              />
              {d === "low" ? "低" : d === "mid" ? "中" : "高"}
            </label>
          ))}
        </fieldset>
        <label className="block text-sm text-rose-600 mb-1">创作要求（可选）</label>
        <textarea
          rows={3}
          maxLength={500}
          value={initialInput}
          onChange={(e) => setInitialInput(e.target.value)}
          className="w-full rounded-xl border border-rose-100 px-3 py-2 text-sm resize-none"
          placeholder="例如：治愈氛围、窗边午后…"
        />
        <p className={`text-xs mt-1 ${initialInput.length >= 500 ? "text-red-500" : "text-rose-400/60"}`}>
          {initialInput.length} / 500
        </p>
        {errorText && (
          <p className="text-sm text-red-600 mt-3 rounded-lg bg-red-50 px-3 py-2">{errorText}</p>
        )}
        <div className="flex justify-end gap-3 mt-6">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm text-rose-500 cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            disabled={atLimit || submitting}
            onClick={() => void handleSubmit()}
            className="px-4 py-2 rounded-xl text-sm text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            {atLimit ? "已达上限，请先删除部分历史" : submitting ? "提交中…" : "生成"}
          </button>
        </div>
      </div>
    </div>
  );
}
