import { useCallback, useEffect, useMemo, useState } from "react";
import type { CharaProfile, Divergence, OfficialSeedPrompts } from "@/types/material";
import {
  cloneOfficialSeedPrompts,
  emptyOfficialSeedPrompts,
} from "@/types/material";
import {
  type CreativeDirectionApi,
  type SeedPromptTaskStatus,
  getSeedPromptTaskStatus,
  startSeedPromptTask,
} from "@/services/materialApi";
import { ApiError } from "@/services/api";
import TaskGeneratingView from "@/pages/material/components/shared/TaskGeneratingView";
import { useTaskPolling } from "@/pages/material/components/shared/useTaskPolling";
import SeedListPanel from "@/pages/material/components/seed/SeedListPanel";
import SeedGenerateModal from "@/pages/material/components/seed/SeedGenerateModal";
import SeedMergePreview from "@/pages/material/components/seed/SeedMergePreview";
import SeedDeleteConfirmModal from "@/pages/material/components/seed/SeedDeleteConfirmModal";
import { newSeedId } from "@/pages/material/components/seed/utils";
import type { SeedPrompt } from "@/types/material";

const PER_DIRECTION_LIMIT = 20;
const TOTAL_LIMIT = 100;

const INFLIGHT_KEY = (id: string) => `material_seed_prompt_inflight_${id}`;

function readInflight(characterId: string): string | null {
  try {
    const raw = window.sessionStorage.getItem(INFLIGHT_KEY(characterId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { taskId?: string };
    return typeof parsed?.taskId === "string" ? parsed.taskId : null;
  } catch {
    return null;
  }
}

function writeInflight(characterId: string, taskId: string) {
  try {
    window.sessionStorage.setItem(
      INFLIGHT_KEY(characterId),
      JSON.stringify({ taskId, submittedAt: new Date().toISOString() })
    );
  } catch {
    /* private mode */
  }
}

function clearInflight(characterId: string) {
  try {
    window.sessionStorage.removeItem(INFLIGHT_KEY(characterId));
  } catch {
    /* */
  }
}

function countTotalSeeds(seeds: OfficialSeedPrompts): number {
  return seeds.characterSpecific.length + seeds.general.length;
}

function countSeedsForDirection(seeds: OfficialSeedPrompts, directionId: string | null): number {
  return seeds.characterSpecific.filter((s) =>
    directionId === null ? s.creativeDirectionId == null : s.creativeDirectionId === directionId
  ).length;
}

type SeedStagePhase = "hydrating" | "idle" | "generating" | "merging";

export default function SeedPromptStage({
  characterId,
  chara,
  directions,
  onCountChange,
  onSaveBio,
  onRefreshChara,
  showToast,
}: {
  characterId: string;
  chara: CharaProfile;
  directions: CreativeDirectionApi[];
  onCountChange?: (count: number) => void;
  onSaveBio: (payload: OfficialSeedPrompts) => Promise<void>;
  onRefreshChara?: (id: string) => Promise<void>;
  showToast: (msg: string) => void;
}) {
  const [phase, setPhase] = useState<SeedStagePhase>("hydrating");
  const [inflightTaskId, setInflightTaskId] = useState<string | null>(null);
  const [inflightStatus, setInflightStatus] = useState<SeedPromptTaskStatus | null>(null);
  const [pendingMerge, setPendingMerge] = useState<{
    directionId: string | null;
    drafts: string[];
  } | null>(null);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [preselectDirectionId, setPreselectDirectionId] = useState<string | null | undefined>(
    undefined
  );
  const [deletingSeed, setDeletingSeed] = useState<SeedPrompt | null>(null);

  const officialSeeds = chara.bio.officialSeedPrompts ?? emptyOfficialSeedPrompts();

  useEffect(() => {
    onCountChange?.(countTotalSeeds(officialSeeds));
  }, [officialSeeds, onCountChange]);

  const directionMetaForMerge = useMemo(() => {
    if (!pendingMerge?.directionId) return null;
    const d = directions.find((x) => x.id === pendingMerge.directionId);
    if (!d) return null;
    return { title: d.title, divergence: d.divergence as Divergence };
  }, [pendingMerge?.directionId, directions]);

  const remainingPerDirection = useMemo(() => {
    if (!pendingMerge) return PER_DIRECTION_LIMIT;
    return Math.max(
      0,
      PER_DIRECTION_LIMIT - countSeedsForDirection(officialSeeds, pendingMerge.directionId)
    );
  }, [pendingMerge, officialSeeds]);

  const remainingTotal = useMemo(
    () => Math.max(0, TOTAL_LIMIT - countTotalSeeds(officialSeeds)),
    [officialSeeds]
  );

  const handleTerminal = useCallback(
    (status: SeedPromptTaskStatus) => {
      clearInflight(characterId);
      setInflightTaskId(null);
      if (status.status === "completed" && status.seed_draft) {
        setPendingMerge({
          directionId: status.creative_direction_id,
          drafts: status.seed_draft.character_specific ?? [],
        });
        setPhase("merging");
        setRecentError(null);
      } else if (status.status === "failed") {
        setRecentError(status.error_message || "生成失败");
        setPhase("idle");
      }
    },
    [characterId]
  );

  const handleGiveUp = useCallback((lastError: unknown) => {
    setRecentError(lastError instanceof ApiError ? lastError.message : "轮询多次失败");
    setPhase("idle");
  }, []);

  useTaskPolling({
    taskId: inflightTaskId,
    enabled: phase === "generating",
    fetchStatus: (id) => getSeedPromptTaskStatus(characterId, id),
    isTerminal: (s) => s.status === "completed" || s.status === "failed",
    onProgress: (s) => setInflightStatus(s),
    onTerminal: (s) => handleTerminal(s),
    onGiveUp: handleGiveUp,
  });

  useEffect(() => {
    let cancelled = false;
    setPhase("hydrating");
    void (async () => {
      const taskId = readInflight(characterId);
      if (!taskId) {
        if (!cancelled) setPhase("idle");
        return;
      }
      try {
        const status = await getSeedPromptTaskStatus(characterId, taskId);
        if (cancelled) return;
        if (status.status === "completed" || status.status === "failed") {
          clearInflight(characterId);
          if (status.status === "completed" && status.seed_draft) {
            setPendingMerge({
              directionId: status.creative_direction_id,
              drafts: status.seed_draft.character_specific ?? [],
            });
            setPhase("merging");
          } else if (status.status === "failed") {
            setRecentError(status.error_message || "上次任务失败");
            setPhase("idle");
          } else {
            setPhase("idle");
          }
        } else {
          setInflightTaskId(taskId);
          setInflightStatus(status);
          setPhase("generating");
        }
      } catch {
        clearInflight(characterId);
        if (!cancelled) setPhase("idle");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [characterId]);

  const handleGenerate = async (creativeDirectionId: string | null) => {
    const { task_id } = await startSeedPromptTask(characterId, {
      creative_direction_id: creativeDirectionId,
    });
    writeInflight(characterId, task_id);
    setInflightTaskId(task_id);
    setInflightStatus(null);
    setPhase("generating");
    setShowGenerateModal(false);
    setRecentError(null);
  };

  const handleConfirmMerge = async (selectedDrafts: string[]) => {
    if (!pendingMerge) return;
    const current = chara.bio.officialSeedPrompts ?? emptyOfficialSeedPrompts();
    const base = cloneOfficialSeedPrompts(current);
    const seen = new Set(base.characterSpecific.map((s) => s.text.trim()));
    for (const text of selectedDrafts) {
      const t = text.trim();
      if (!t || seen.has(t)) continue;
      seen.add(t);
      base.characterSpecific.push({
        id: newSeedId(),
        text,
        used: false,
        creativeDirectionId: pendingMerge.directionId,
      });
    }
    await onSaveBio(base);
    setPendingMerge(null);
    setPhase("idle");
    showToast("已合入");
    // P2-3: 合入后强制刷新 chara，确保 bio 中 creative_direction_meta 与服务端最新一致
    if (onRefreshChara) void onRefreshChara(characterId);
  };

  const handleCancelMerge = () => {
    setPendingMerge(null);
    setPhase("idle");
  };

  const handleConfirmDelete = async () => {
    if (!deletingSeed) return;
    const current = chara.bio.officialSeedPrompts ?? emptyOfficialSeedPrompts();
    const next = cloneOfficialSeedPrompts(current);
    const inCs = next.characterSpecific.some((s) => s.id === deletingSeed.id);
    if (inCs) {
      next.characterSpecific = next.characterSpecific.filter((s) => s.id !== deletingSeed.id);
    } else {
      next.general = next.general.filter((s) => s.id !== deletingSeed.id);
    }
    await onSaveBio(next);
    setDeletingSeed(null);
    showToast("已删除");
  };

  const openGenerate = (binding?: string | null) => {
    setPreselectDirectionId(binding);
    setShowGenerateModal(true);
  };

  const stepLabel =
    inflightStatus?.current_step === "generating"
      ? "正在生成种子提示词…"
      : inflightStatus?.status === "processing"
        ? "处理中…"
        : "排队中…";

  if (phase === "merging" && pendingMerge) {
    return (
      <SeedMergePreview
        drafts={pendingMerge.drafts}
        directionMeta={directionMetaForMerge}
        remainingPerDirection={remainingPerDirection}
        remainingTotal={remainingTotal}
        onCancel={handleCancelMerge}
        onConfirm={handleConfirmMerge}
      />
    );
  }

  return (
    <div className="px-5 py-4">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h2
            className="text-base font-bold text-rose-600"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            种子提示词
          </h2>
          <p className="text-xs text-rose-400/70 mt-0.5">
            {countTotalSeeds(officialSeeds)} / {TOTAL_LIMIT}
          </p>
        </div>
        <button
          type="button"
          disabled={phase === "generating" || phase === "hydrating"}
          onClick={() => openGenerate(undefined)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            fontFamily: "'ZCOOL KuaiLe', cursive",
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            boxShadow: "0 4px 14px rgba(244,114,182,0.25)",
          }}
        >
          <i className="ri-add-line" />
          生成种子
        </button>
      </div>

      {recentError && phase !== "generating" && (
        <div className="mb-4 flex items-start gap-2 rounded-xl bg-rose-50 border border-rose-100 px-3 py-2">
          <p className="text-sm text-rose-600 flex-1">{recentError}</p>
          <button
            type="button"
            onClick={() => setRecentError(null)}
            className="text-rose-400 cursor-pointer shrink-0"
            aria-label="关闭"
          >
            <i className="ri-close-line" />
          </button>
        </div>
      )}

      {phase === "hydrating" && (
        <p className="text-sm text-rose-400/70 text-center py-12">加载中…</p>
      )}

      {phase === "generating" && (
        <TaskGeneratingView
          icon="ri-seedling-line"
          title="正在生成种子提示词…"
          stepLabel={stepLabel}
          hint="首次生成约 30-60s"
          errorMessage={inflightStatus?.status === "failed" ? inflightStatus.error_message : null}
          onBack={() => {
            clearInflight(characterId);
            setInflightTaskId(null);
            setPhase("idle");
          }}
          onRetry={() => {
            setRecentError(null);
            openGenerate(undefined);
          }}
        />
      )}

      {phase === "idle" && (
        <SeedListPanel
          chara={chara}
          directions={directions}
          onAddBound={(id) => openGenerate(id)}
          onDeleteSeed={setDeletingSeed}
        />
      )}

      <SeedGenerateModal
        open={showGenerateModal}
        directions={directions}
        bio={{ officialSeedPrompts: chara.bio.officialSeedPrompts ?? null }}
        preselectDirectionId={preselectDirectionId}
        onClose={() => setShowGenerateModal(false)}
        onSubmit={handleGenerate}
      />

      <SeedDeleteConfirmModal
        open={!!deletingSeed}
        seed={deletingSeed}
        onCancel={() => setDeletingSeed(null)}
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
}
