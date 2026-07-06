import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { CreativeDirectionApi } from "@/services/materialApi";
import DivergenceBadge from "@/pages/material/components/direction/DivergenceBadge";

export default function DirectionEditDrawer({
  open,
  direction,
  onClose,
  onSave,
}: {
  open: boolean;
  direction: CreativeDirectionApi | null;
  onClose: () => void;
  onSave: (patch: { title?: string; description?: string }) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!direction) return;
    setTitle(direction.title);
    setDescription(direction.description);
  }, [direction]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !direction) return null;

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      await onSave({ title: title.trim(), description: description.trim() });
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <>
      <div className="fixed inset-0 z-40 bg-black/20" onClick={onClose} />
      <div
        className="fixed inset-y-0 right-0 z-50 w-full sm:w-[480px] flex flex-col bg-white shadow-2xl"
        style={{ animation: "slideInRight 0.25s ease-out" }}
        role="dialog"
        aria-modal="true"
      >
        <div className="px-5 py-4 border-b border-rose-100 flex items-center justify-between">
          <h3
            className="text-lg font-bold text-rose-600"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            编辑创意方向
          </h3>
          <button type="button" onClick={onClose} className="text-rose-400 cursor-pointer">
            <i className="ri-close-line text-xl" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          <div>
            <label className="text-sm text-rose-600 block mb-1">标题</label>
            <input
              value={title}
              maxLength={200}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-xl border border-rose-100 px-3 py-2 text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-rose-600">发散度</span>
            <DivergenceBadge divergence={direction.divergence} />
          </div>
          <div>
            <label className="text-sm text-rose-600 block mb-1">描述（Markdown）</label>
            <p className="text-xs text-rose-400/70 mb-2">
              7 个小节标题为 LLM 输出约定，建议保留
            </p>
            <textarea
              rows={20}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-xl border border-rose-100 px-3 py-2 text-sm font-mono resize-none"
            />
          </div>
        </div>
        <div className="px-5 py-4 border-t border-rose-100 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm text-rose-500 cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            disabled={saving || !title.trim() || !description.trim()}
            onClick={() => void handleSave()}
            className="px-4 py-2 rounded-xl text-sm text-white cursor-pointer disabled:opacity-50"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to   { transform: translateX(0); }
        }
      `}</style>
    </>,
    document.body
  );
}
