import { useState } from "react";
import type { Divergence, SeedPrompt } from "@/types/material";
import DirectionChip from "@/pages/material/components/direction/DirectionChip";

export type SeedGroup = {
  key: string;
  label: string;
  directionMeta?: { title: string; divergence: Divergence };
  items: SeedPrompt[];
  /** null = 无方向绑定；undefined = 不显示生成按钮（遗留 general） */
  generateBinding?: string | null;
};

export default function SeedGroupSection({
  group,
  defaultExpanded,
  onAddBound,
  onDeleteSeed,
  perDirectionLimit,
  totalAtLimit,
}: {
  group: SeedGroup;
  defaultExpanded: boolean;
  onAddBound: (directionId: string | null) => void;
  onDeleteSeed: (seed: SeedPrompt) => void;
  perDirectionLimit: number;
  totalAtLimit: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const showGenerate = group.generateBinding !== undefined;
  const count = group.items.length;
  const showCount = group.generateBinding !== undefined;
  const atPerLimit = showCount && count >= perDirectionLimit;
  const generateDisabled = totalAtLimit || atPerLimit;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        border: "1px solid rgba(253,164,175,0.22)",
        background: "rgba(255,255,255,0.75)",
      }}
    >
      <div
        className="flex items-center gap-2 px-4 py-3 border-b border-rose-100/40 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
      >
        <i
          className={`ri-arrow-${expanded ? "down" : "right"}-s-line text-rose-400 shrink-0`}
        />
        <span
          className="text-sm font-bold text-rose-600 flex-1 min-w-0 truncate"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          {group.label}
        </span>
        {group.directionMeta && <DirectionChip meta={group.directionMeta} compact />}
        {showCount && (
          <span className="text-xs text-rose-400/80 shrink-0">
            {count} / {perDirectionLimit}
          </span>
        )}
        {showGenerate && (
          <button
            type="button"
            disabled={generateDisabled}
            onClick={(e) => {
              e.stopPropagation();
              onAddBound(group.generateBinding ?? null);
            }}
            className="shrink-0 text-xs px-2.5 py-1 rounded-lg cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              background: "rgba(253,164,175,0.12)",
              color: "#db2777",
              border: "1px solid rgba(244,114,182,0.25)",
            }}
            title="+ 生成 (绑定该方向)"
          >
            <i className="ri-add-line mr-0.5" />
            生成
          </button>
        )}
      </div>

      {expanded && (
        <div className="p-3 flex flex-col gap-2">
          {group.key === "legacy-general" && (
            <p className="text-[11px] text-rose-400/60 leading-snug px-1 mb-1">
              此区块为旧版生成的历史数据，新任务不再产出。可手工编辑/删除
            </p>
          )}
          {group.items.length === 0 ? (
            <p
              className="text-xs text-center text-rose-300/60 py-4"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              暂无种子
            </p>
          ) : (
            group.items.map((seed) => (
              <div
                key={seed.id}
                className="flex items-start gap-2 px-3 py-2.5 rounded-xl"
                style={{
                  background: "rgba(253,164,175,0.04)",
                  border: "1px solid rgba(253,164,175,0.12)",
                }}
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {seed.creativeDirectionId != null &&
                    (seed.creativeDirectionMeta ? (
                      <DirectionChip meta={seed.creativeDirectionMeta} compact />
                    ) : (
                      <DirectionChip
                        meta={{ title: "", divergence: "low" }}
                        compact
                        fallback="方向已删除"
                      />
                    ))}
                  <p className="text-xs leading-relaxed text-rose-700/80 break-words flex-1 min-w-0">
                    {seed.text}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onDeleteSeed(seed)}
                  className="w-7 h-7 shrink-0 flex items-center justify-center rounded-lg cursor-pointer"
                  style={{
                    background: "rgba(253,164,175,0.06)",
                    color: "#fda4af",
                    border: "1px solid rgba(253,164,175,0.15)",
                  }}
                  title="删除"
                >
                  <i className="ri-delete-bin-line text-xs" />
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
