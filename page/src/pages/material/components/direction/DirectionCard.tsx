import { useState } from "react";
import type { CreativeDirectionApi } from "@/services/materialApi";
import DivergenceBadge from "@/pages/material/components/direction/DivergenceBadge";

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function DirectionCard({
  direction,
  onEdit,
  onDelete,
}: {
  direction: CreativeDirectionApi;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-2xl px-4 py-3 flex flex-col gap-3"
      style={{
        border: "1px solid rgba(253,164,175,0.2)",
        background: "rgba(255,255,255,0.7)",
      }}
    >
      <div className="flex items-start gap-2 flex-wrap">
        <span
          className="font-bold text-rose-700 text-sm flex-1 min-w-0"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          {direction.title}
        </span>
        <DivergenceBadge divergence={direction.divergence} />
        <div className="flex items-center gap-2 ml-auto shrink-0">
          <button
            type="button"
            onClick={onEdit}
            className="text-xs text-rose-500 hover:text-rose-600 cursor-pointer"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            编辑
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="text-xs text-rose-400 hover:text-rose-600 cursor-pointer"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            删除
          </button>
        </div>
      </div>
      <div>
        <p
          className={`text-sm text-rose-800/80 whitespace-pre-wrap ${expanded ? "" : "line-clamp-4"}`}
        >
          {direction.description}
        </p>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-rose-400 mt-1 cursor-pointer hover:text-rose-500"
        >
          {expanded ? "收起" : "展开"}
        </button>
      </div>
      <p className="text-xs text-rose-400/60">
        方向更新于 {formatTime(direction.updated_at)}
      </p>
    </div>
  );
}
