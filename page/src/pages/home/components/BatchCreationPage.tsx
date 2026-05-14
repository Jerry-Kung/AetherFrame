import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import type { CharaProfile } from "@/types/material";
import * as creationApi from "@/services/creationApi";
import { listFixedSeedTemplates } from "@/services/materialApi";
import { ApiError } from "@/services/api";
import type { BatchTask, BatchTaskConfig } from "@/types/batchAutomation";
import { DEFAULT_BATCH_CONFIG } from "@/types/batchAutomation";
import type { SeedPromptSection } from "@/mocks/materialChara";
import {
  buildSkeletonBatchTask,
  hydrateBatchTask,
  type BatchAutomationListItemApi,
} from "@/utils/batchAutomationDisplay";
import BatchConfigModal from "./BatchConfigModal";
import BatchTaskCard from "./BatchTaskCard";

interface BatchCreationPageProps {
  charas: CharaProfile[];
  listLoading?: boolean;
  listError?: string | null;
  onMarkSeedUsed: (charaId: string, section: SeedPromptSection, seedId: string) => Promise<void>;
}

type GenState = "idle" | "generating";

/** 当前角色 bio 内未用种子条数（不含全局固定模板）。 */
function getAvailableSeedsCount(chara: CharaProfile): number {
  const p = chara.bio.officialSeedPrompts;
  if (!p) return 0;
  let n = 0;
  p.characterSpecific.filter((s) => !s.used).forEach(() => {
    n += 1;
  });
  p.general.filter((s) => !s.used).forEach(() => {
    n += 1;
  });
  return n;
}

function hasAnyAvailableSeed(charas: CharaProfile[], fixedUnusedCount: number): boolean {
  if (fixedUnusedCount > 0) return true;
  return charas.some((c) => getAvailableSeedsCount(c) > 0);
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function listRowToApiRow(row: creationApi.BatchAutomationListItemRow): BatchAutomationListItemApi {
  return {
    id: row.id,
    run_id: row.run_id,
    run_status: row.run_status,
    step_index: row.step_index,
    character_id: row.character_id,
    chara_name: row.chara_name,
    chara_avatar: row.chara_avatar,
    seed_prompt_id: row.seed_prompt_id,
    seed_section: row.seed_section,
    seed_prompt_text: row.seed_prompt_text,
    prompt_precreation_task_id: row.prompt_precreation_task_id,
    quick_create_task_id: row.quick_create_task_id,
    status: row.status,
    error_message: row.error_message,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function CharaSelectChip({
  chara,
  selected,
  onToggle,
}: {
  chara: CharaProfile;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="flex items-center gap-2 px-3 py-2 rounded-xl cursor-pointer transition-all duration-200 whitespace-nowrap"
      style={{
        background: selected
          ? "linear-gradient(135deg, rgba(253,164,175,0.2) 0%, rgba(244,114,182,0.15) 100%)"
          : "rgba(255,255,255,0.6)",
        border: selected ? "1.5px solid rgba(244,114,182,0.4)" : "1.5px solid rgba(253,164,175,0.2)",
        boxShadow: selected ? "0 2px 8px rgba(244,114,182,0.15)" : "none",
      }}
    >
      <div className="w-6 h-6 rounded-lg overflow-hidden shrink-0 border border-rose-100">
        <img src={chara.avatarUrl} alt="" className="w-full h-full object-cover object-top" />
      </div>
      <span className="text-xs font-bold text-rose-700/80" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
        {chara.name}
      </span>
      {selected && (
        <div
          className="w-4 h-4 flex items-center justify-center rounded-full shrink-0"
          style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
        >
          <i className="ri-check-line text-white text-xs"></i>
        </div>
      )}
    </button>
  );
}

const GEN_HINTS = [
  "正在清点角色与种子提示词，为产线备料…",
  "灵感产线已启动，云端正顺序跑完每一批产出…",
  "Prompt 预生成与美图创作正在接力进行…",
  "每一批完成后会自动刷新产线记录，请稍候～",
];

export default function BatchCreationPage({
  charas,
  listLoading = false,
  listError = null,
  onMarkSeedUsed,
}: BatchCreationPageProps) {
  const eligibleCharas = charas.filter((c) => c.status === "done");
  const [selectedCharaIds, setSelectedCharaIds] = useState<Set<string>>(new Set());
  const [genState, setGenState] = useState<GenState>("idle");
  const [config, setConfig] = useState<BatchTaskConfig>(DEFAULT_BATCH_CONFIG);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [tasks, setTasks] = useState<BatchTask[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [tasksError, setTasksError] = useState<string | null>(null);
  const [genProgress, setGenProgress] = useState(0);
  const [genHint, setGenHint] = useState("准备启动灵感产线…");
  const pollCancelRef = useRef(false);
  const [fixedSeedUsedFlags, setFixedSeedUsedFlags] = useState<boolean[]>([]);

  const loadFixedSeedMeta = useCallback(async () => {
    try {
      const rows = await listFixedSeedTemplates();
      setFixedSeedUsedFlags(rows.map((r) => r.used));
    } catch {
      setFixedSeedUsedFlags([]);
    }
  }, []);

  const fixedUnusedCount = useMemo(
    () => fixedSeedUsedFlags.filter((used) => !used).length,
    [fixedSeedUsedFlags]
  );

  useEffect(() => {
    void loadFixedSeedMeta();
  }, [loadFixedSeedMeta]);

  const loadTasksFromApi = useCallback(async () => {
    setTasksLoading(true);
    setTasksError(null);
    try {
      const { items } = await creationApi.listBatchAutomationItems({ limit: 80, offset: 0 });
      const skeletons = items.map((row) =>
        buildSkeletonBatchTask(listRowToApiRow(row), charas, config)
      );
      const hydrated = await Promise.all(
        skeletons.map(async (t) =>
          t.itemStatus === "completed" && t.promptRecordId && t.quickCreateRecordId ? hydrateBatchTask(t) : t
        )
      );
      setTasks(hydrated);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "加载产线记录失败";
      setTasksError(msg);
    } finally {
      setTasksLoading(false);
    }
  }, [charas, config]);

  useEffect(() => {
    void loadTasksFromApi();
  }, [loadTasksFromApi]);

  const toggleChara = useCallback((id: string) => {
    setSelectedCharaIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    if (selectedCharaIds.size === eligibleCharas.length && eligibleCharas.length > 0) {
      setSelectedCharaIds(new Set());
    } else {
      setSelectedCharaIds(new Set(eligibleCharas.map((c) => c.id)));
    }
  }, [eligibleCharas, selectedCharaIds.size]);

  const handleDeleteTask = useCallback(
    async (taskId: string) => {
      try {
        await creationApi.deleteBatchAutomationItem(taskId);
        await loadTasksFromApi();
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "删除失败";
        setTasksError(msg);
      }
    },
    [loadTasksFromApi]
  );

  const handleMarkUsed = useCallback(
    async (taskId: string) => {
      const task = tasks.find((t) => t.id === taskId);
      if (!task) return;
      await onMarkSeedUsed(task.charaId, task.seedPromptSection, task.seedPromptId);
      await loadFixedSeedMeta();
      await loadTasksFromApi();
    },
    [tasks, onMarkSeedUsed, loadTasksFromApi, loadFixedSeedMeta]
  );

  const startBatch = useCallback(async () => {
    const pickCharas =
      selectedCharaIds.size === 0 ? eligibleCharas : eligibleCharas.filter((c) => selectedCharaIds.has(c.id));

    if (pickCharas.length === 0) return;

    const anySeed = hasAnyAvailableSeed(pickCharas, fixedUnusedCount);
    if (!anySeed) {
      setGenHint("没有可用的未使用种子提示词，请先在素材加工里备好正式种子，产线才能开工～");
      return;
    }

    const pc = Math.min(4, Math.max(1, Math.round(config.promptCount))) as 1 | 2 | 3 | 4;
    const ip = Math.min(4, Math.max(1, Math.round(config.imagesPerPrompt))) as 1 | 2 | 3 | 4;
    const araw = (config.aspectRatio || "1:1").trim();
    const ar = (["16:9", "4:3", "1:1", "3:4", "9:16"].includes(araw) ? araw : "1:1") as
      | "16:9"
      | "4:3"
      | "1:1"
      | "3:4"
      | "9:16";
    const maxPrompts = pc;
    const iterations = Math.min(10, Math.max(2, Math.round(config.batchCount)));

    pollCancelRef.current = false;
    setGenState("generating");
    setGenProgress(2);
    setGenHint(GEN_HINTS[0] ?? "");

    try {
      const res = await creationApi.startBatchAutomation({
        iterations,
        prompt_count: pc,
        images_per_prompt: ip,
        aspect_ratio: ar,
        max_prompts: maxPrompts,
        character_ids: selectedCharaIds.size === 0 ? null : Array.from(selectedCharaIds),
      });

      await loadTasksFromApi();

      let hintIdx = 0;
      let hintTimer: number | null = null;
      try {
        hintTimer = window.setInterval(() => {
          hintIdx = (hintIdx + 1) % GEN_HINTS.length;
          setGenHint(GEN_HINTS[hintIdx] ?? "");
        }, 4000);

        const runId = res.run_id;
        while (!pollCancelRef.current) {
          const run = await creationApi.getBatchAutomationRun(runId);
          const total = run.iterations_total || 1;
          const done = run.iterations_done ?? 0;
          setGenProgress(Math.min(95, Math.round((done / total) * 92) + 3));

          await loadTasksFromApi();

          if (run.status === "completed" || run.status === "failed") {
            setGenProgress(100);
            setGenHint(
              run.status === "failed"
                ? run.error_message || "灵感产线已结束（存在失败）"
                : "本轮灵感产线已跑完～"
            );
            break;
          }
          await sleep(2500);
        }
      } finally {
        if (hintTimer !== null) window.clearInterval(hintTimer);
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "提交灵感产线失败";
      setGenHint(msg);
      setTasksError(msg);
    } finally {
      setGenState("idle");
      await loadTasksFromApi();
    }
  }, [config, eligibleCharas, fixedUnusedCount, loadTasksFromApi, selectedCharaIds]);

  useEffect(() => {
    return () => {
      pollCancelRef.current = true;
    };
  }, []);

  const canStart = eligibleCharas.length > 0;
  const allSelected = selectedCharaIds.size === eligibleCharas.length && eligibleCharas.length > 0;
  const bc = Math.min(10, Math.max(2, Math.round(config.batchCount)));
  const expectedImages = bc * config.promptCount * config.imagesPerPrompt;

  if (listLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[240px] gap-3">
        <div
          className="w-12 h-12 rounded-full border-2 border-rose-200 border-t-rose-400 animate-spin"
          aria-hidden
        />
        <p className="text-sm text-rose-400/70">正在加载角色资料…</p>
      </div>
    );
  }

  if (listError) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[240px] px-6 text-center">
        <i className="ri-error-warning-line text-3xl text-rose-400 mb-2"></i>
        <p className="text-sm text-rose-600">{listError}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 px-6 py-5 border-b border-rose-100/40" style={{ background: "rgba(255,255,255,0.3)" }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 min-w-0">
            <div
              className="w-8 h-8 flex items-center justify-center rounded-xl shrink-0"
              style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
            >
              <i className="ri-magic-line text-white text-sm"></i>
            </div>
            <h2
              className="text-base font-bold text-rose-700 truncate"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              灵感工坊
            </h2>
            <span className="text-xs text-rose-300/60 shrink-0 hidden sm:inline">
              {canStart ? `${eligibleCharas.length} 位角色可参与` : "暂无可参与角色"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowConfigModal(true)}
            disabled={genState === "generating"}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap shrink-0"
            style={{
              background: "rgba(253,164,175,0.1)",
              border: "1px solid rgba(253,164,175,0.2)",
              color: "#f472b6",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              opacity: genState === "generating" ? 0.5 : 1,
            }}
          >
            <i className="ri-settings-3-line text-xs"></i>
            产线参数
          </button>
        </div>

        <div className="mb-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              <i className="ri-user-heart-line mr-1"></i>选择参与角色
            </span>
            {eligibleCharas.length > 0 && (
              <button
                type="button"
                onClick={selectAll}
                className="text-xs cursor-pointer transition-colors duration-200 whitespace-nowrap"
                style={{ color: "#f472b6" }}
              >
                {allSelected ? "取消全选" : "全选"}
              </button>
            )}
          </div>
          {eligibleCharas.length === 0 ? (
            <div
              className="rounded-2xl p-8 flex flex-col items-center text-center gap-3"
              style={{
                background: "linear-gradient(145deg, rgba(255,250,252,0.95) 0%, rgba(254,242,248,0.9) 100%)",
                border: "1.5px dashed rgba(253,164,175,0.35)",
              }}
            >
              <div
                className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl"
                style={{ background: "rgba(253,164,175,0.12)" }}
              >
                🌸
              </div>
              <p className="text-sm font-medium text-rose-600/80" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                还没有「资料已完善」的角色呢
              </p>
              <p className="text-xs text-rose-400/60 max-w-sm leading-relaxed">
                请先到素材加工模块完善角色资料，完成后就能在灵感工坊里启动产线啦～
              </p>
            </div>
          ) : (
            <div className="flex items-center gap-2 flex-wrap">
              {eligibleCharas.map((chara) => (
                <CharaSelectChip
                  key={chara.id}
                  chara={chara}
                  selected={selectedCharaIds.size === 0 ? true : selectedCharaIds.has(chara.id)}
                  onToggle={() => toggleChara(chara.id)}
                />
              ))}
              {selectedCharaIds.size === 0 && eligibleCharas.length > 0 && (
                <span className="text-xs text-rose-300/50 ml-1">（未点选时默认全部参与）</span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className="text-xs text-rose-300/50 leading-relaxed">
            当前产线参数：产出 {bc} 批 / Prompt {config.promptCount} 个 / 每 Prompt {config.imagesPerPrompt} 张 /{" "}
            {config.aspectRatio} · 预计共 {expectedImages} 张图
          </span>
        </div>

        <button
          type="button"
          onClick={() => void startBatch()}
          disabled={!canStart || genState === "generating"}
          className="flex items-center gap-2 px-6 py-2.5 rounded-2xl text-sm font-semibold text-white transition-all duration-200 whitespace-nowrap"
          style={{
            fontFamily: "'ZCOOL KuaiLe', cursive",
            background:
              !canStart || genState === "generating"
                ? "rgba(253,164,175,0.35)"
                : "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            boxShadow:
              !canStart || genState === "generating" ? "none" : "0 4px 16px rgba(244,114,182,0.35)",
            cursor: !canStart || genState === "generating" ? "not-allowed" : "pointer",
          }}
        >
          <i className="ri-magic-line text-sm"></i>
          {genState === "generating" ? "灵感产线运行中…" : "启动灵感产线"}
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 flex flex-col gap-4">
        {tasksError && (
          <p className="text-xs text-rose-500 shrink-0" role="alert">
            {tasksError}
          </p>
        )}
        {tasksLoading && tasks.length === 0 && (
          <p className="text-xs text-rose-300/60 text-center shrink-0">正在加载产线记录…</p>
        )}

        {genState === "generating" && (
          <div className="flex flex-col items-center py-8 shrink-0">
            <div className="relative w-16 h-16 mb-5">
              <div
                className="absolute inset-0 rounded-full"
                style={{
                  border: "3px solid rgba(253,164,175,0.2)",
                  borderTopColor: "#f472b6",
                  animation: "batchSpin 0.9s linear infinite",
                }}
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <i className="ri-image-ai-line text-rose-400 text-xl"></i>
              </div>
            </div>
            <p className="text-sm text-rose-500/80 mb-4 text-center px-4" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              {genHint}
            </p>
            <div className="w-64 max-w-full h-2 rounded-full overflow-hidden" style={{ background: "rgba(253,164,175,0.15)" }}>
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${genProgress}%`,
                  background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                }}
              />
            </div>
            <p className="text-xs text-rose-300/60 mt-2">{genProgress}%</p>
          </div>
        )}

        {tasks.length > 0 && (
          <div className="space-y-3 shrink-0">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <i className="ri-gallery-line text-rose-400 text-sm"></i>
                <span className="text-sm font-bold text-rose-700/80" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                  产线产出
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
                >
                  {tasks.length} 条产线记录
                </span>
              </div>
            </div>
            {tasks.map((task, idx) => (
              <BatchTaskCard
                key={task.id}
                task={task}
                index={idx}
                onDelete={handleDeleteTask}
                onMarkUsed={handleMarkUsed}
              />
            ))}
          </div>
        )}

        {tasks.length === 0 && genState !== "generating" && eligibleCharas.length > 0 && !tasksLoading && (
          <div className="flex flex-col items-center justify-center flex-1 text-center py-10">
            <div
              className="w-24 h-24 flex items-center justify-center rounded-3xl mb-5 text-5xl"
              style={{
                background: "linear-gradient(135deg, rgba(253,164,175,0.12) 0%, rgba(244,114,182,0.08) 100%)",
                border: "1.5px dashed rgba(244,114,182,0.22)",
              }}
            >
              ✨
            </div>
            <h3 className="text-base font-bold text-rose-400/70 mb-2" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              灵感工坊正在待机中
            </h3>
            <p className="text-sm text-rose-300/55 max-w-xs leading-relaxed">
              选好参与角色，在「产线参数」里设定批次与出图规格，点击「启动灵感产线」，系统会按批随机匹配角色与未用种子，并自动完成 Prompt 预生成与美图创作～
            </p>
          </div>
        )}
      </div>

      <BatchConfigModal
        visible={showConfigModal}
        initialConfig={config}
        onConfirm={(c) => {
          setConfig(c);
          setShowConfigModal(false);
        }}
        onCancel={() => setShowConfigModal(false)}
      />

      <style>{`
        @keyframes batchSpin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
