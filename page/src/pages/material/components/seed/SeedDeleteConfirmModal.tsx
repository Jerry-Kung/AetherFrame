import { useEffect, useState } from "react";
import type { SeedPrompt } from "@/types/material";

export default function SeedDeleteConfirmModal({
  open,
  seed,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  seed: SeedPrompt | null;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}) {
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open || !seed) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={onCancel}
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
          className="text-lg font-bold text-rose-600 mb-3"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          确认删除这条种子？
        </h3>
        <div
          className="max-h-36 overflow-y-auto rounded-xl border border-rose-100/90 px-3 py-2.5 mb-5 text-sm text-rose-800/90 leading-relaxed whitespace-pre-wrap break-words"
          style={{ background: "rgba(253,164,175,0.06)" }}
        >
          {seed.text}
        </div>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 rounded-xl text-sm text-rose-500 cursor-pointer disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={async () => {
              setLoading(true);
              try {
                await onConfirm();
              } finally {
                setLoading(false);
              }
            }}
            className="px-4 py-2 rounded-xl text-sm text-white cursor-pointer disabled:opacity-50"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            {loading ? "删除中…" : "确认删除"}
          </button>
        </div>
      </div>
    </div>
  );
}
