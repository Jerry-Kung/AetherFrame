import { useEffect, useMemo, useState } from "react";
import type { OfficialSeedPrompts } from "@/types/material";
import { MATERIAL_ERROR_CODES } from "@/types/material";
import type { CreativeDirectionApi } from "@/services/materialApi";
import { readApiErrorCode } from "@/services/materialApi";
import { ApiError } from "@/services/api";

const PER_DIRECTION_LIMIT = 20;
const TOTAL_LIMIT = 100;

function countSeedsForDirection(
  bio: { officialSeedPrompts: OfficialSeedPrompts | null },
  directionId: string | null
): number {
  const cs = bio.officialSeedPrompts?.characterSpecific ?? [];
  if (directionId === null) {
    return cs.filter((s) => s.creativeDirectionId == null).length;
  }
  return cs.filter((s) => s.creativeDirectionId === directionId).length;
}

function countTotalSeeds(bio: { officialSeedPrompts: OfficialSeedPrompts | null }): number {
  const p = bio.officialSeedPrompts;
  if (!p) return 0;
  return p.characterSpecific.length + p.general.length;
}

export default function SeedGenerateModal({
  open,
  directions,
  bio,
  preselectDirectionId,
  onClose,
  onSubmit,
}: {
  open: boolean;
  directions: CreativeDirectionApi[];
  bio: { officialSeedPrompts: OfficialSeedPrompts | null };
  preselectDirectionId?: string | null;
  onClose: () => void;
  onSubmit: (creativeDirectionId: string | null) => Promise<void>;
}) {
  const [directionId, setDirectionId] = useState<string | "none">("none");
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (preselectDirectionId === undefined) {
      setDirectionId("none");
    } else if (preselectDirectionId === null) {
      setDirectionId("none");
    } else {
      setDirectionId(preselectDirectionId);
    }
    setErrorText(null);
  }, [open, preselectDirectionId]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const resolvedId: string | null = directionId === "none" ? null : directionId;

  const perDirCount = useMemo(
    () => countSeedsForDirection(bio, resolvedId),
    [bio, resolvedId]
  );
  const totalCount = useMemo(() => countTotalSeeds(bio), [bio]);

  const perDirAtLimit = perDirCount >= PER_DIRECTION_LIMIT;
  const totalAtLimit = totalCount >= TOTAL_LIMIT;
  const blocked = perDirAtLimit || totalAtLimit;

  if (!open) return null;

  const handleSubmit = async () => {
    if (blocked || submitting) return;
    setSubmitting(true);
    setErrorText(null);
    try {
      await onSubmit(resolvedId);
    } catch (e) {
      const code = readApiErrorCode(e);
      if (code === MATERIAL_ERROR_CODES.SEED_PER_DIRECTION_EXCEEDED) {
        setErrorText("该方向种子已达 20 条上限");
      } else if (code === MATERIAL_ERROR_CODES.SEED_TOTAL_EXCEEDED) {
        setErrorText("角色种子总数已达 100 条上限");
      } else if (code === MATERIAL_ERROR_CODES.TASK_CONCURRENCY_EXCEEDED) {
        setErrorText("该角色已有 2 个任务在跑，请等一个完成再来");
      } else {
        setErrorText(e instanceof ApiError ? e.message : "提交失败");
      }
    } finally {
      setSubmitting(false);
    }
  };

  let limitHint = `该方向 ${perDirCount} / ${PER_DIRECTION_LIMIT}，角色总计 ${totalCount} / ${TOTAL_LIMIT}`;
  if (perDirAtLimit) limitHint = "该方向种子已达 20 条上限";
  else if (totalAtLimit) limitHint = "角色种子总数已达 100 条上限";

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
          生成种子提示词
        </h3>

        <label className="block text-sm text-rose-600 mb-1">绑定创意方向</label>
        <select
          value={directionId}
          onChange={(e) => setDirectionId(e.target.value)}
          className="w-full rounded-xl border border-rose-100 px-3 py-2 text-sm mb-2"
        >
          <option value="none">不绑定（使用默认世界观）</option>
          {directions.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
        <p className="text-xs text-rose-400/70 mb-4">{limitHint}</p>

        {errorText && (
          <p className="text-sm text-red-600 mb-3 rounded-lg bg-red-50 px-3 py-2">{errorText}</p>
        )}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm text-rose-500 cursor-pointer"
          >
            取消
          </button>
          <button
            type="button"
            disabled={blocked || submitting}
            onClick={() => void handleSubmit()}
            className="px-4 py-2 rounded-xl text-sm text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            {blocked ? "已达上限" : submitting ? "提交中…" : "开始生成"}
          </button>
        </div>
      </div>
    </div>
  );
}
