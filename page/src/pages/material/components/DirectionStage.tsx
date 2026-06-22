import { useCallback, useEffect, useState } from "react";
import type { CharaBio, CharaProfile, Divergence } from "@/types/material";
import {
  type CreativeDirectionApi,
  type CreativeDirectionTaskStatus,
  deleteCreativeDirection,
  getCreativeDirectionTaskStatus,
  listCreativeDirections,
  patchCreativeDirection,
  startCreativeDirectionTask,
} from "@/services/materialApi";
import { ApiError } from "@/services/api";
import TaskGeneratingView from "@/pages/material/components/shared/TaskGeneratingView";
import { useTaskPolling } from "@/pages/material/components/shared/useTaskPolling";
import DirectionCard from "@/pages/material/components/direction/DirectionCard";
import DirectionGenerateModal from "@/pages/material/components/direction/DirectionGenerateModal";
import DirectionEditDrawer from "@/pages/material/components/direction/DirectionEditDrawer";
import DirectionDeleteConfirmModal from "@/pages/material/components/direction/DirectionDeleteConfirmModal";

const DIRECTION_LIMIT = 20;
const INFLIGHT_KEY = (id: string) => `material_creative_direction_inflight_${id}`;

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

type DirectionStagePhase = "hydrating" | "idle" | "generating";

function countSeedsBoundToDirection(bio: CharaBio, dirId?: string | null): number {
  if (!dirId) return 0;
  const cs = bio.officialSeedPrompts?.characterSpecific ?? [];
  return cs.filter((s) => s.creativeDirectionId === dirId).length;
}

export default function DirectionStage({
  characterId,
  chara,
  showToast,
  onCountChange,
  onRefreshChara,
  onRefreshDirections,
}: {
  characterId: string;
  chara: CharaProfile;
  showToast: (msg: string) => void;
  onCountChange?: (count: number) => void;
  onRefreshChara?: (id: string) => Promise<void>;
  onRefreshDirections?: () => Promise<void>;
}) {
  const [phase, setPhase] = useState<DirectionStagePhase>("hydrating");
  const [directions, setDirections] = useState<CreativeDirectionApi[]>([]);
  const [inflightTaskId, setInflightTaskId] = useState<string | null>(null);
  const [inflightStatus, setInflightStatus] = useState<CreativeDirectionTaskStatus | null>(
    null
  );
  const [recentError, setRecentError] = useState<string | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [editingDirection, setEditingDirection] = useState<CreativeDirectionApi | null>(null);
  const [deletingDirection, setDeletingDirection] = useState<CreativeDirectionApi | null>(null);
  const [lastFormDraft, setLastFormDraft] = useState<{
    divergence: Divergence;
    initialInput: string;
  } | null>(null);

  useEffect(() => {
    onCountChange?.(directions.length);
  }, [directions.length, onCountChange]);

  const handleTerminal = useCallback(
    async (status: CreativeDirectionTaskStatus) => {
      clearInflight(characterId);
      setInflightTaskId(null);
      if (status.status === "completed" && status.result_direction) {
        setDirections((prev) => [
          status.result_direction!,
          ...prev.filter((d) => d.id !== status.result_direction!.id),
        ]);
        setPhase("idle");
        setRecentError(null);
        showToast("创意方向已生成");
        // P2-3: 终态后强制刷新 chara 详情与 directions 列表，绕过 MaterialPage 的 30s 缓存
        if (onRefreshChara) void onRefreshChara(characterId);
        if (onRefreshDirections) void onRefreshDirections();
      } else if (status.status === "failed") {
        setRecentError(status.error_message || "生成失败");
        setPhase("idle");
      }
    },
    [characterId, showToast, onRefreshChara, onRefreshDirections]
  );

  const handleGiveUp = useCallback((lastError: unknown) => {
    setRecentError(lastError instanceof ApiError ? lastError.message : "轮询多次失败");
    setPhase("idle");
  }, []);

  useTaskPolling({
    taskId: inflightTaskId,
    enabled: phase === "generating",
    fetchStatus: (id) => getCreativeDirectionTaskStatus(characterId, id),
    isTerminal: (s) => s.status === "completed" || s.status === "failed",
    onProgress: (s) => setInflightStatus(s),
    onTerminal: (s) => void handleTerminal(s),
    onGiveUp: handleGiveUp,
  });

  useEffect(() => {
    let cancelled = false;
    setPhase("hydrating");
    void (async () => {
      try {
        const list = await listCreativeDirections(characterId);
        if (cancelled) return;
        setDirections(list);

        const taskId = readInflight(characterId);
        if (taskId) {
          try {
            const status = await getCreativeDirectionTaskStatus(characterId, taskId);
            if (cancelled) return;
            if (status.status === "completed" || status.status === "failed") {
              clearInflight(characterId);
              if (status.status === "failed") {
                setRecentError(status.error_message || "上次任务失败");
              }
              setPhase("idle");
            } else {
              setInflightTaskId(taskId);
              setInflightStatus(status);
              setPhase("generating");
            }
          } catch {
            clearInflight(characterId);
            setPhase("idle");
          }
        } else {
          setPhase("idle");
        }
      } catch (e) {
        if (cancelled) return;
        setRecentError(e instanceof ApiError ? e.message : "加载失败");
        setPhase("idle");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [characterId]);

  const handleGenerate = async (divergence: Divergence, initialInput: string | null) => {
    setLastFormDraft({ divergence, initialInput: initialInput ?? "" });
    const { task_id } = await startCreativeDirectionTask(characterId, {
      divergence,
      initial_input: initialInput,
    });
    writeInflight(characterId, task_id);
    setInflightTaskId(task_id);
    setInflightStatus(null);
    setPhase("generating");
    setShowGenerateModal(false);
    setRecentError(null);
  };

  const handleSaveEdit = async (
    directionId: string,
    patch: { title?: string; description?: string }
  ) => {
    const updated = await patchCreativeDirection(characterId, directionId, patch);
    setDirections((prev) => prev.map((d) => (d.id === directionId ? updated : d)));
    setEditingDirection(null);
    showToast("已保存");
  };

  const handleConfirmDelete = async (directionId: string) => {
    await deleteCreativeDirection(characterId, directionId);
    setDirections((prev) => prev.filter((d) => d.id !== directionId));
    setDeletingDirection(null);
    showToast("已删除");
  };

  const atLimit = directions.length >= DIRECTION_LIMIT;
  const stepLabel =
    inflightStatus?.current_step === "generating"
      ? "正在调用模型生成…"
      : inflightStatus?.status === "processing"
        ? "处理中…"
        : "排队中…";

  return (
    <div className="px-5 py-4">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h2
            className="text-base font-bold text-rose-600"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            创意方向
          </h2>
          <p className="text-xs text-rose-400/70 mt-0.5">
            {directions.length} / {DIRECTION_LIMIT}
          </p>
        </div>
        <button
          type="button"
          disabled={atLimit || phase === "generating"}
          onClick={() => setShowGenerateModal(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            fontFamily: "'ZCOOL KuaiLe', cursive",
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            boxShadow: "0 4px 14px rgba(244,114,182,0.25)",
          }}
        >
          <i className="ri-add-line" />
          生成新方向
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
          icon="ri-compass-3-line"
          title="正在生成创意方向…"
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
            setShowGenerateModal(true);
          }}
        />
      )}

      {phase === "idle" && directions.length === 0 && (
        <p
          className="text-sm text-rose-400/60 text-center py-16"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          还没有创意方向。点击「生成新方向」为后续绘图准备主题。
        </p>
      )}

      {phase === "idle" && directions.length > 0 && (
        <div className="flex flex-col gap-3">
          {directions.map((d) => (
            <DirectionCard
              key={d.id}
              direction={d}
              onEdit={() => setEditingDirection(d)}
              onDelete={() => setDeletingDirection(d)}
            />
          ))}
        </div>
      )}

      <DirectionGenerateModal
        open={showGenerateModal}
        currentCount={directions.length}
        limit={DIRECTION_LIMIT}
        initialDraft={lastFormDraft}
        onClose={() => setShowGenerateModal(false)}
        onSubmit={handleGenerate}
      />
      <DirectionEditDrawer
        open={!!editingDirection}
        direction={editingDirection}
        onClose={() => setEditingDirection(null)}
        onSave={(patch) =>
          editingDirection
            ? handleSaveEdit(editingDirection.id, patch)
            : Promise.resolve()
        }
      />
      <DirectionDeleteConfirmModal
        open={!!deletingDirection}
        direction={deletingDirection}
        boundSeedCount={countSeedsBoundToDirection(chara.bio, deletingDirection?.id)}
        onCancel={() => setDeletingDirection(null)}
        onConfirm={() =>
          deletingDirection
            ? handleConfirmDelete(deletingDirection.id)
            : Promise.resolve()
        }
      />
    </div>
  );
}
