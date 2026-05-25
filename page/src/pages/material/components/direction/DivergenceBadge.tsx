import type { Divergence } from "@/types/material";

const TOKENS: Record<
  Divergence,
  { label: string; bg: string; fg: string; border: string }
> = {
  low: {
    label: "低",
    bg: "rgba(96,165,250,0.12)",
    fg: "#2563eb",
    border: "rgba(96,165,250,0.35)",
  },
  mid: {
    label: "中",
    bg: "rgba(250,204,21,0.15)",
    fg: "#a16207",
    border: "rgba(250,204,21,0.4)",
  },
  high: {
    label: "高",
    bg: "rgba(251,146,60,0.15)",
    fg: "#c2410c",
    border: "rgba(251,146,60,0.4)",
  },
};

export default function DivergenceBadge({
  divergence,
  compact = false,
}: {
  divergence: Divergence;
  compact?: boolean;
}) {
  const t = TOKENS[divergence];
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full ${compact ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-xs"} font-medium`}
      style={{
        background: t.bg,
        color: t.fg,
        border: `1px solid ${t.border}`,
        fontFamily: "'ZCOOL KuaiLe', cursive",
      }}
      aria-label={`发散度 ${t.label}`}
    >
      {t.label}
    </span>
  );
}
