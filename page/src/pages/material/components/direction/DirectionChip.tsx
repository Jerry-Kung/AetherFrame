import type { Divergence } from "@/types/material";
import DivergenceBadge from "@/pages/material/components/direction/DivergenceBadge";

export interface DirectionChipProps {
  meta: { title: string; divergence: Divergence };
  compact?: boolean;
  /** 当 meta 失效（如方向已删除）时显示的文案 */
  fallback?: string;
}

function truncateTitle(title: string, max = 14): string {
  const t = title.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

export default function DirectionChip({
  meta,
  compact = false,
  fallback = "方向已删除",
}: DirectionChipProps) {
  const title = meta.title?.trim() ?? "";
  if (!title) {
    return (
      <span
        className={`inline-flex items-center gap-1 shrink-0 rounded-full border border-rose-100/90 bg-rose-50/90 text-rose-400/85 ${compact ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-xs"}`}
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        <i className="ri-compass-3-line opacity-60" />
        {fallback}
      </span>
    );
  }

  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 shrink-0 rounded-full border border-rose-100/80 bg-white/90 text-rose-600/90 max-w-[10rem] ${compact ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-xs"}`}
      style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
    >
      <i className="ri-compass-3-line text-rose-400 shrink-0" />
      <DivergenceBadge divergence={meta.divergence} compact={compact} />
      <span className="truncate">{truncateTitle(title)}</span>
    </span>
  );
}
