import { useEffect, useMemo, useState } from "react";
import type { Divergence } from "@/types/material";
import DirectionChip from "@/pages/material/components/direction/DirectionChip";

export default function SeedMergePreview({
  drafts,
  directionMeta,
  remainingPerDirection,
  remainingTotal,
  onCancel,
  onConfirm,
}: {
  drafts: string[];
  directionMeta: { title: string; divergence: Divergence } | null;
  remainingPerDirection: number;
  remainingTotal: number;
  onCancel: () => void;
  onConfirm: (selected: string[]) => Promise<void>;
}) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set(drafts));
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setSelected(new Set(drafts));
  }, [drafts]);

  const selectedCount = selected.size;
  const maxKeep = Math.max(0, Math.min(remainingPerDirection, remainingTotal));
  const overLimit = selectedCount > maxKeep;
  const canConfirm = selectedCount > 0 && !overLimit && !submitting;

  const toggle = (text: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(text)) next.delete(text);
      else next.add(text);
      return next;
    });
  };

  const selectedList = useMemo(
    () => drafts.filter((d) => selected.has(d)),
    [drafts, selected]
  );

  return (
    <div className="px-5 py-4">
      <h2
        className="text-base font-bold text-rose-600 mb-2"
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        合入新生成的种子
      </h2>
      <p className="text-xs text-rose-500/80 mb-3 leading-relaxed">
        以下是新生成的种子，勾选保留并合入正式列表
      </p>
      {directionMeta && (
        <p className="text-xs text-rose-500/80 mb-3 flex items-center gap-2 flex-wrap">
          <span>绑定方向：</span>
          <DirectionChip meta={directionMeta} compact />
        </p>
      )}
      <p className="text-xs text-rose-400/70 mb-3">
        已勾选 {selectedCount} 条 / 还可保留 {maxKeep} 条
        {overLimit && (
          <span className="text-red-500 ml-1">（超出上限，请减少勾选）</span>
        )}
      </p>

      <div
        className="rounded-2xl overflow-hidden mb-4 max-h-[min(50vh,20rem)] overflow-y-auto"
        style={{
          border: "1px solid rgba(253,164,175,0.22)",
          background: "rgba(255,255,255,0.75)",
        }}
      >
        {drafts.map((text, idx) => (
          <div key={text}>
            {idx > 0 && <div className="h-px mx-3" style={{ background: "rgba(253,164,175,0.12)" }} />}
            <label className="flex items-start gap-3 px-4 py-3 cursor-pointer">
              <input
                type="checkbox"
                checked={selected.has(text)}
                onChange={() => toggle(text)}
                className="mt-1 w-4 h-4 rounded border-rose-200 text-pink-500 focus:ring-pink-300"
              />
              <span className="text-sm text-rose-800/85 leading-relaxed flex-1 min-w-0 break-words">
                {text}
              </span>
            </label>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          className="px-4 py-2 rounded-xl text-sm text-rose-500 cursor-pointer disabled:opacity-50"
        >
          放弃合入
        </button>
        <button
          type="button"
          disabled={!canConfirm}
          onClick={() => void (async () => {
            setSubmitting(true);
            try {
              await onConfirm(selectedList);
            } finally {
              setSubmitting(false);
            }
          })()}
          className="px-4 py-2 rounded-xl text-sm text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            fontFamily: "'ZCOOL KuaiLe', cursive",
          }}
        >
          {submitting ? "合入中…" : overLimit ? "超出上限" : "合入正式列表"}
        </button>
      </div>
    </div>
  );
}
