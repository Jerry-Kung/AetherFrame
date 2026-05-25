import { useEffect, useState } from "react";
import type { CreativeDirectionApi } from "@/services/materialApi";

export default function DirectionDeleteConfirmModal({
  open,
  direction,
  boundSeedCount,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  direction: CreativeDirectionApi | null;
  boundSeedCount: number;
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

  if (!open || !direction) return null;

  const message =
    boundSeedCount > 0
      ? `「${direction.title}」下绑定了 ${boundSeedCount} 条种子提示词，删除后会一并清除`
      : `确认删除创意方向「${direction.title}」？此操作无法恢复。`;

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
        className="relative w-full max-w-sm rounded-2xl p-6 shadow-xl"
        style={{ background: "rgba(255,255,255,0.95)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <p
          className="text-sm text-rose-700 leading-relaxed mb-6"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          {message}
        </p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-xl text-sm text-rose-500 cursor-pointer"
          >
            再想想
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
            }}
          >
            确认删除
          </button>
        </div>
      </div>
    </div>
  );
}
