import { useState, useRef, useEffect, useCallback } from "react";
import type { CharaProfile } from "@/types/material";
import type { PromptCard, CreationPromptSession, PromptHistoryRecord } from "@/types/creation";
import * as creationApi from "@/services/creationApi";
import { ApiError } from "@/services/api";
import { type AutoSubmitConfig } from "./AutoSubmitConfigModal";
import type { ChainedQuickCreateResumePayload } from "../page";

interface PromptGenPageProps {
  charas: CharaProfile[];
  listLoading?: boolean;
  listError?: string | null;
  /** 同步到美图创作页：生成完成、卡片编辑后推送；清空预生成时传 null */
  onPromptSessionChange?: (session: CreationPromptSession | null) => void;
  autoSubmitEnabled?: boolean;
  onAutoSubmitToggle?: (enabled: boolean) => void;
  autoSubmitConfig?: AutoSubmitConfig;
  onAutoSubmit?: (record: PromptHistoryRecord, config: AutoSubmitConfig) => void;
  /** 服务端链式一键创作已启动时，切换到美图页并轮询该任务 */
  onChainedQuickCreateResume?: (payload: ChainedQuickCreateResumePayload) => void;
  onOpenConfig?: () => void;
}

type GenState = "idle" | "generating" | "done";

const COUNT_OPTIONS = [2, 3, 4] as const;

const POLL_INTERVAL_MS = 10000;

const CHAIN_ASPECT_OPTIONS = ["16:9", "4:3", "1:1", "3:4", "9:16"] as const;

function clampPromptCountFromConfig(n: number): 1 | 2 | 3 | 4 {
  const v = Math.round(Number(n));
  if (v >= 1 && v <= 4) return v as 1 | 2 | 3 | 4;
  return 2;
}

function clampPromptImagesPer(n: number): 1 | 2 | 3 | 4 {
  const v = Math.round(Number(n));
  if (v >= 1 && v <= 4) return v as 1 | 2 | 3 | 4;
  return 2;
}

function clampPromptAspect(ratio: string): ChainedQuickCreateResumePayload["aspectRatio"] {
  return (CHAIN_ASPECT_OPTIONS.includes(ratio as (typeof CHAIN_ASPECT_OPTIONS)[number])
    ? ratio
    : "1:1") as ChainedQuickCreateResumePayload["aspectRatio"];
}

function isPromptCharaSelectable(c: CharaProfile): boolean {
  return c.status === "done";
}

/** 原生 <option> 仅支持纯文本，用符号区分「资料已完善 / 待完善」 */
function charaSelectOptionLabel(c: CharaProfile): string {
  return isPromptCharaSelectable(c) ? `✓ ${c.name}` : `✗ ${c.name}`;
}

function stepHintLabel(step: string | null | undefined): string | null {
  if (!step) return null;
  if (step === "collecting") return "正在生成备选 Prompt…";
  if (step === "reviewing") return "正在筛选最优 Prompt…";
  return null;
}

const LOADING_TIPS = [
  "正在阅读角色设定，感受她的灵魂～",
  "构思画面中，请稍等一下下～",
  "Prompt 正在从脑海中涌现出来～",
  "快好了！正在做最后的润色～",
];

function toPromptHistoryRecord(
  raw: creationApi.PromptPrecreationHistoryItem | creationApi.PromptPrecreationHistoryDetailResponse,
  charas: CharaProfile[]
): PromptHistoryRecord {
  const chara = charas.find((c) => c.id === raw.character_id) ?? null;
  return {
    id: raw.id,
    taskId: raw.task_id,
    charaId: raw.character_id,
    charaName: raw.chara_name,
    charaAvatar: chara?.avatarUrl || raw.chara_avatar || "",
    seedPrompt: raw.seed_prompt,
    promptCount: raw.prompt_count,
    status: raw.status,
    errorMessage: raw.error_message ?? null,
    cards: "cards" in raw ? raw.cards ?? [] : [],
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

interface ConfirmModalProps {
  visible: boolean;
  title: string;
  desc: string;
  confirmText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmModal = ({
  visible,
  title,
  desc,
  confirmText = "确认",
  onConfirm,
  onCancel,
}: ConfirmModalProps) => {
  if (!visible) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(253,164,175,0.15)", backdropFilter: "blur(6px)" }}
        onClick={onCancel}
      />
      <div
        className="relative rounded-3xl px-8 py-7 w-80 flex flex-col items-center gap-4"
        style={{
          background: "linear-gradient(160deg, #fff8fa 0%, #fffaf5 100%)",
          border: "1.5px solid rgba(253,164,175,0.3)",
          boxShadow: "0 8px 32px rgba(244,114,182,0.12)",
        }}
      >
        <div
          className="w-12 h-12 flex items-center justify-center rounded-2xl"
          style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
        >
          <i className="ri-delete-bin-2-line text-white text-xl"></i>
        </div>
        <div className="text-center">
          <h3
            className="text-base font-bold text-rose-700 mb-1"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            {title}
          </h3>
          <p className="text-sm text-rose-400/70 leading-relaxed">{desc}</p>
        </div>
        <div className="flex items-center gap-3 w-full">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 py-2 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "rgba(253,164,175,0.1)",
              border: "1px solid rgba(253,164,175,0.25)",
              color: "#f472b6",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            再想想
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 py-2 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              color: "white",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

interface HistorySidebarProps {
  records: PromptHistoryRecord[];
  activeId: string | null;
  onSelect: (record: PromptHistoryRecord) => void;
  onDelete: (id: string) => void;
}

const HistorySidebar = ({ records, activeId, onSelect, onDelete }: HistorySidebarProps) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  return (
    <>
      <div
        className="w-64 shrink-0 flex flex-col h-full"
        style={{
          background: "rgba(255,255,255,0.5)",
          borderLeft: "1px solid rgba(253,164,175,0.2)",
        }}
      >
        <div
          className="px-4 py-3.5 shrink-0 border-b border-rose-100/40"
          style={{ background: "rgba(255,248,250,0.8)" }}
        >
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 flex items-center justify-center rounded-lg"
              style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
            >
              <i className="ri-history-line text-white text-xs"></i>
            </div>
            <span
              className="text-sm font-bold text-rose-600"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              历史创作
            </span>
            <span
              className="ml-auto text-xs px-1.5 py-0.5 rounded-full"
              style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
            >
              {records.length}
            </span>
          </div>
          <p className="text-xs text-rose-300/60 mt-1.5 leading-relaxed">
            双击记录可以带出当次创作内容
          </p>
        </div>

        <div className="flex-1 overflow-y-auto py-2 px-2">
          {records.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center px-3">
              <i className="ri-inbox-line text-rose-200 text-3xl mb-2"></i>
              <p
                className="text-xs text-rose-300/60 leading-relaxed"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                还没有历史记录哦，快去创作吧～
              </p>
            </div>
          ) : (
            records.map((record) => (
              <div
                key={record.id}
                className="relative rounded-2xl p-3 mb-1.5 cursor-pointer transition-all duration-200"
                style={{
                  background:
                    activeId === record.id
                      ? "linear-gradient(135deg, rgba(253,164,175,0.18) 0%, rgba(244,114,182,0.1) 100%)"
                      : hoveredId === record.id
                        ? "rgba(253,164,175,0.1)"
                        : "transparent",
                  border:
                    activeId === record.id
                      ? "1.5px solid rgba(244,114,182,0.35)"
                      : "1.5px solid transparent",
                }}
                onDoubleClick={() => onSelect(record)}
                onMouseEnter={() => setHoveredId(record.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                {hoveredId === record.id && (
                  <button
                    type="button"
                    className="absolute top-2 right-2 w-5 h-5 flex items-center justify-center rounded-lg cursor-pointer transition-all duration-200 z-10"
                    style={{
                      background: "rgba(253,164,175,0.2)",
                      color: "#f472b6",
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTargetId(record.id);
                    }}
                  >
                    <i className="ri-close-line text-xs"></i>
                  </button>
                )}
                <div className="flex items-center gap-2 mb-2 pr-5">
                  <div className="w-7 h-7 rounded-xl overflow-hidden shrink-0 border border-rose-100">
                    {record.charaAvatar ? (
                      <img
                        src={record.charaAvatar}
                        alt={record.charaName}
                        className="w-full h-full object-cover object-top"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-rose-50">
                        <i className="ri-user-heart-line text-rose-300 text-xs"></i>
                      </div>
                    )}
                  </div>
                  <div className="min-w-0">
                    <p
                      className="text-xs font-bold text-rose-600 truncate"
                      style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                    >
                      {record.charaName}
                    </p>
                    <p className="text-xs text-rose-300/60">{record.createdAt}</p>
                  </div>
                </div>
                <p className="text-xs text-rose-500/60 leading-relaxed line-clamp-2 mb-2">
                  {record.seedPrompt}
                </p>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className="text-xs px-1.5 py-0.5 rounded-full"
                    style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
                  >
                    {record.promptCount} 个 Prompt
                  </span>
                  {activeId === record.id && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded-full"
                      style={{ background: "rgba(110,231,183,0.2)", color: "#059669" }}
                    >
                      当前
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <ConfirmModal
        visible={deleteTargetId !== null}
        title="删除这条记录？"
        desc="删除后无法恢复哦，确定要删掉这次的创作记录吗？"
        confirmText="确认删除"
        onConfirm={() => {
          if (deleteTargetId) onDelete(deleteTargetId);
          setDeleteTargetId(null);
        }}
        onCancel={() => setDeleteTargetId(null)}
      />
    </>
  );
};

interface DetailPanelProps {
  card: PromptCard | null;
  onClose: () => void;
  onSave: (id: string, newPrompt: string) => void;
}

const DetailPanel = ({ card, onClose, onSave }: DetailPanelProps) => {
  const [editText, setEditText] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (card) {
      setEditText(card.fullPrompt);
      setSaved(false);
    }
  }, [card]);

  const handleSave = () => {
    if (!card) return;
    onSave(card.id, editText);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  };

  const handleCopy = () => {
    void navigator.clipboard.writeText(editText);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ pointerEvents: card ? "auto" : "none" }}
    >
      <div
        className="absolute inset-0 transition-opacity duration-300"
        style={{
          background: "rgba(253,164,175,0.12)",
          backdropFilter: card ? "blur(4px)" : "none",
          opacity: card ? 1 : 0,
        }}
        onClick={onClose}
        aria-hidden={!card}
      />

      <div
        className="relative w-full max-w-lg h-full flex flex-col transition-transform duration-300"
        style={{
          background: "linear-gradient(160deg, #fff8fa 0%, #fffaf5 100%)",
          borderLeft: "1px solid rgba(253,164,175,0.25)",
          transform: card ? "translateX(0)" : "translateX(100%)",
        }}
      >
        <div className="h-[3px] w-full shrink-0 bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300 opacity-70" />

        <div className="flex items-center justify-between px-6 py-4 shrink-0 border-b border-rose-100/50">
          <div className="flex items-center gap-2.5 min-w-0">
            <div
              className="w-8 h-8 shrink-0 flex items-center justify-center rounded-xl"
              style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
            >
              <i className="ri-quill-pen-line text-white text-sm"></i>
            </div>
            <div className="min-w-0">
              <h3
                className="text-sm font-bold text-rose-700 truncate"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                {card?.title ?? ""}
              </h3>
              <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                {card?.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-1.5 py-0.5 rounded-full"
                    style={{
                      background: "rgba(253,164,175,0.15)",
                      color: "#f472b6",
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 shrink-0 flex items-center justify-center rounded-xl cursor-pointer transition-all duration-200 hover:bg-rose-100/60"
            style={{ color: "#f472b6" }}
          >
            <i className="ri-close-line text-base"></i>
          </button>
        </div>

        <div className="flex-1 flex flex-col px-6 py-4 min-h-0">
          <div className="flex items-center justify-between mb-2">
            <span
              className="text-xs font-medium text-rose-500"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              完整 Prompt（可直接编辑修改）
            </span>
            <span className="text-xs text-rose-300/60">{editText.length} 字符</span>
          </div>
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="flex-1 w-full min-h-[200px] resize-none rounded-2xl p-4 text-sm leading-relaxed outline-none transition-all duration-200"
            style={{
              background: "rgba(255,255,255,0.8)",
              border: "1.5px solid rgba(253,164,175,0.25)",
              color: "#7c3f5e",
              fontFamily: "monospace",
              fontSize: "13px",
            }}
            onFocus={(e) => {
              e.target.style.borderColor = "rgba(244,114,182,0.5)";
            }}
            onBlur={(e) => {
              e.target.style.borderColor = "rgba(253,164,175,0.25)";
            }}
          />
        </div>

        <div className="px-6 pb-6 shrink-0 flex items-center gap-3">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "rgba(253,164,175,0.12)",
              border: "1px solid rgba(253,164,175,0.25)",
              color: "#f472b6",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            <i className="ri-file-copy-line text-sm"></i>
            复制 Prompt
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: saved
                ? "linear-gradient(135deg, #6ee7b7 0%, #34d399 100%)"
                : "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              color: "white",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              boxShadow: "0 2px 8px rgba(244,114,182,0.3)",
            }}
          >
            <i className={saved ? "ri-check-line text-sm" : "ri-save-line text-sm"}></i>
            {saved ? "已保存！" : "保存修改"}
          </button>
        </div>
      </div>
    </div>
  );
};

interface PromptCardItemProps {
  card: PromptCard;
  index: number;
  onClick: () => void;
}

const PromptCardItem = ({ card, index, onClick }: PromptCardItemProps) => {
  const [hovered, setHovered] = useState(false);

  const gradients = [
    "from-rose-100/60 to-pink-50/60",
    "from-pink-100/60 to-fuchsia-50/60",
    "from-fuchsia-100/60 to-rose-50/60",
    "from-amber-50/60 to-rose-50/60",
  ];

  const accentColors = ["#f472b6", "#e879f9", "#fb7185", "#f59e0b"];

  return (
    <div
      className={`relative rounded-2xl p-4 cursor-pointer transition-all duration-200 bg-gradient-to-br ${gradients[index % gradients.length]}`}
      style={{
        border: hovered
          ? `1.5px solid ${accentColors[index % accentColors.length]}50`
          : "1.5px solid rgba(253,164,175,0.2)",
        transform: hovered ? "translateY(-2px)" : "translateY(0)",
      }}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className="absolute top-3 right-3 w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold text-white"
        style={{ background: accentColors[index % accentColors.length] }}
      >
        {index + 1}
      </div>

      <h4
        className="text-sm font-bold text-rose-700 mb-2 pr-8"
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        {card.title}
      </h4>

      <div className="flex items-center gap-1 mb-2.5 flex-wrap">
        {card.tags.map((tag) => (
          <span
            key={tag}
            className="text-xs px-2 py-0.5 rounded-full"
            style={{
              background: "rgba(253,164,175,0.18)",
              color: "#f472b6",
            }}
          >
            #{tag}
          </span>
        ))}
      </div>

      <p className="text-xs text-rose-500/70 leading-relaxed line-clamp-2 font-mono">{card.preview}</p>

      <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-rose-100/50">
        <span className="text-xs text-rose-300/60">{card.createdAt}</span>
        <span
          className="text-xs flex items-center gap-1 transition-all duration-200"
          style={{ color: accentColors[index % accentColors.length] }}
        >
          点击查看完整 Prompt
          <i className="ri-arrow-right-line text-xs"></i>
        </span>
      </div>
    </div>
  );
};

const PromptGenPage = ({
  charas,
  listLoading,
  listError,
  onPromptSessionChange,
  autoSubmitEnabled = false,
  onAutoSubmitToggle,
  autoSubmitConfig,
  onAutoSubmit,
  onChainedQuickCreateResume,
  onOpenConfig,
}: PromptGenPageProps) => {
  const [selectedCharaId, setSelectedCharaId] = useState<string>("");
  const [seedPrompt, setSeedPrompt] = useState("");
  const [promptCount, setPromptCount] = useState<2 | 3 | 4>(3);
  const [genState, setGenState] = useState<GenState>("idle");
  const [cards, setCards] = useState<PromptCard[]>([]);
  const [tipIndex, setTipIndex] = useState(0);
  const [detailCard, setDetailCard] = useState<PromptCard | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [statusStep, setStatusStep] = useState<string | null>(null);
  const [historyRecords, setHistoryRecords] = useState<PromptHistoryRecord[]>([]);
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [showAutoSubmitToast, setShowAutoSubmitToast] = useState(false);
  const tipTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);
  const lastAutoSubmitKeyRef = useRef("");
  /** 本轮 start 是否已请求服务端链式一键创作（用于跳过客户端 onAutoSubmit 重复提交） */
  const lastStartUsedServerChainRef = useRef(false);
  const toastTimerRef = useRef<number | null>(null);
  /** 本轮生成结果对应的角色（避免用户在 done 态切换下拉框后错绑角色） */
  const sessionCharaIdRef = useRef<string>("");

  const clearPollTimer = useCallback(() => {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const clearTipTimer = useCallback(() => {
    if (tipTimerRef.current !== null) {
      window.clearInterval(tipTimerRef.current);
      tipTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (charas.length === 0) {
      setSelectedCharaId("");
      return;
    }
    const firstDone = charas.find(isPromptCharaSelectable);
    setSelectedCharaId((prev) => {
      if (prev && charas.some((c) => c.id === prev)) {
        return prev;
      }
      return firstDone?.id ?? "";
    });
  }, [charas]);

  const selectedChara = charas.find((c) => c.id === selectedCharaId) ?? null;
  const hasCharas = charas.length > 0;
  const hasSelectableChara = charas.some(isPromptCharaSelectable);

  const upsertHistoryRecord = useCallback((record: PromptHistoryRecord) => {
    setHistoryRecords((prev) => {
      const existed = prev.some((item) => item.id === record.id);
      if (!existed) return [record, ...prev];
      const next = prev.map((item) => (item.id === record.id ? record : item));
      next.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
      return next;
    });
  }, []);

  const applyHistoryRecordToMain = useCallback(
    (record: PromptHistoryRecord) => {
      if (charas.some((item) => item.id === record.charaId)) {
        setSelectedCharaId(record.charaId);
      }
      setSeedPrompt(record.seedPrompt);
      setPromptCount((record.promptCount === 2 || record.promptCount === 4 ? record.promptCount : 3) as 2 | 3 | 4);
      setActiveHistoryId(record.id);
      sessionCharaIdRef.current = record.charaId;
      setGenError(record.status === "failed" ? record.errorMessage || "Prompt 预生成失败" : null);
      setStatusStep(null);
      if (record.status === "completed" && record.cards.length > 0) {
        setCards(record.cards);
        setGenState("done");
        onPromptSessionChange?.({
          charaId: record.charaId,
          cards: record.cards,
          updatedAt: Date.now(),
        });
      } else if (record.status === "failed") {
        setCards([]);
        setGenState("idle");
        onPromptSessionChange?.(null);
      } else {
        setCards([]);
        setGenState("generating");
        onPromptSessionChange?.(null);
      }
    },
    [charas, onPromptSessionChange]
  );

  useEffect(() => {
    const load = async () => {
      try {
        const [latest, list] = await Promise.all([
          creationApi.getLatestPromptPrecreationHistory(),
          creationApi.listPromptPrecreationHistory({ limit: 50, offset: 0 }),
        ]);
        const mapped = list.items.map((item) => toPromptHistoryRecord(item, charas));
        setHistoryRecords(mapped);
        if (latest) {
          const latestRecord = toPromptHistoryRecord(latest, charas);
          upsertHistoryRecord(latestRecord);
          applyHistoryRecordToMain(latestRecord);
        }
      } catch (e) {
        void e;
      }
    };
    void load();
  }, [charas, applyHistoryRecordToMain, upsertHistoryRecord]);

  const startGenerate = async () => {
    const charaForGen = charas.find((c) => c.id === selectedCharaId);
    if (!selectedCharaId || !seedPrompt.trim() || !charaForGen || !isPromptCharaSelectable(charaForGen)) {
      return;
    }
    setGenError(null);
    setStatusStep(null);
    setGenState("generating");
    setCards([]);
    setActiveHistoryId(null);
    setTipIndex(0);
    cancelledRef.current = false;
    lastAutoSubmitKeyRef.current = "";
    lastStartUsedServerChainRef.current = false;
    clearPollTimer();
    clearTipTimer();

    tipTimerRef.current = window.setInterval(() => {
      setTipIndex((prev) => (prev + 1) % LOADING_TIPS.length);
    }, 900);

    const charaId = selectedCharaId;
    const seed = seedPrompt.trim();
    const useAutoDefaults = Boolean(autoSubmitEnabled && autoSubmitConfig);
    const count = useAutoDefaults
      ? clampPromptCountFromConfig(autoSubmitConfig!.promptCount)
      : promptCount;

    const chain_quick_create = useAutoDefaults
      ? {
          n: clampPromptImagesPer(autoSubmitConfig!.imagesPerPrompt),
          aspect_ratio: clampPromptAspect(autoSubmitConfig!.aspectRatio),
          max_prompts: count,
        }
      : undefined;
    lastStartUsedServerChainRef.current = Boolean(chain_quick_create);

    const finishWithError = (message: string) => {
      clearTipTimer();
      clearPollTimer();
      setGenError(message);
      setGenState("idle");
      setStatusStep(null);
    };

    try {
      const { task_id } = await creationApi.startPromptPrecreation(charaId, {
        seed_prompt: seed,
        count,
        chain_quick_create: chain_quick_create ?? undefined,
      });
      const pendingRecord: PromptHistoryRecord = {
        id: task_id,
        taskId: task_id,
        charaId: charaId,
        charaName: selectedChara?.name ?? "未知角色",
        charaAvatar: selectedChara?.avatarUrl ?? "",
        seedPrompt: seed,
        promptCount: 0,
        status: "pending",
        errorMessage: null,
        cards: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      upsertHistoryRecord(pendingRecord);
      setActiveHistoryId(task_id);

      try {
        const detail = await creationApi.getPromptPrecreationHistory(task_id);
        upsertHistoryRecord(toPromptHistoryRecord(detail, charas));
      } catch {
        // keep pending placeholder
      }

      const schedulePoll = (delayMs: number) => {
        clearPollTimer();
        pollTimerRef.current = window.setTimeout(() => {
          void runPoll();
        }, delayMs);
      };

      const runPoll = async () => {
        if (cancelledRef.current) return;
        try {
          const st = await creationApi.getPromptPrecreationTaskStatus(task_id);
          if (cancelledRef.current) return;
          setStatusStep(st.current_step ?? null);

          if (st.status === "completed") {
            clearTipTimer();
            clearPollTimer();
            const nextCards = st.cards ?? [];
            if (nextCards.length === 0) {
              finishWithError("任务完成但未返回 Prompt 卡片");
              return;
            }
            sessionCharaIdRef.current = charaId;
            setCards(nextCards);
            setGenState("done");
            setStatusStep(null);

            try {
              const detail = await creationApi.getPromptPrecreationHistory(task_id);
              const record = toPromptHistoryRecord(detail, charas);
              upsertHistoryRecord(record);
              setActiveHistoryId(record.id);
            } catch {
              // ignore; status card already present
            }

            onPromptSessionChange?.({
              charaId: charaId,
              cards: nextCards,
              updatedAt: Date.now(),
            });

            const chainedId = (st.chained_quick_create_task_id ?? "").trim();
            if (
              chainedId &&
              lastStartUsedServerChainRef.current &&
              onChainedQuickCreateResume &&
              autoSubmitConfig
            ) {
              const charaForResume = charas.find((c) => c.id === charaId) ?? null;
              const limit = Math.min(
                nextCards.length,
                clampPromptCountFromConfig(autoSubmitConfig.promptCount)
              );
              const sliced = nextCards.slice(0, limit);
              onChainedQuickCreateResume({
                taskId: chainedId,
                charaId,
                charaName: charaForResume?.name ?? selectedChara?.name ?? "未知角色",
                charaAvatar: charaForResume?.avatarUrl ?? selectedChara?.avatarUrl ?? "",
                n: clampPromptImagesPer(autoSubmitConfig.imagesPerPrompt),
                aspectRatio: clampPromptAspect(autoSubmitConfig.aspectRatio),
                prompts: sliced.map((p) => ({
                  id: p.id,
                  title: p.title,
                  preview: p.preview,
                })),
              });
            }
            return;
          }

          if (st.status === "failed") {
            try {
              const detail = await creationApi.getPromptPrecreationHistory(task_id);
              const record = toPromptHistoryRecord(detail, charas);
              upsertHistoryRecord(record);
              setActiveHistoryId(record.id);
            } catch {
              // ignore
            }
            finishWithError(st.error_message?.trim() || "Prompt 预生成失败");
            return;
          }

          schedulePoll(POLL_INTERVAL_MS);
        } catch (e) {
          if (cancelledRef.current) return;
          finishWithError(e instanceof ApiError ? e.message : "获取任务状态失败");
        }
      };

      void runPoll();
    } catch (e) {
      finishWithError(e instanceof ApiError ? e.message : "启动 Prompt 预生成失败");
    }
  };

  const handleRegenerate = () => {
    sessionCharaIdRef.current = "";
    lastAutoSubmitKeyRef.current = "";
    lastStartUsedServerChainRef.current = false;
    setGenError(null);
    setStatusStep(null);
    setGenState("idle");
    setCards([]);
    setActiveHistoryId(null);
    onPromptSessionChange?.(null);
  };

  const handleSelectHistory = async (record: PromptHistoryRecord) => {
    try {
      const detail = await creationApi.getPromptPrecreationHistory(record.id);
      const next = toPromptHistoryRecord(detail, charas);
      upsertHistoryRecord(next);
      applyHistoryRecordToMain(next);
    } catch (e) {
      if (e instanceof ApiError) {
        setGenError(e.message);
      }
    }
  };

  const handleDeleteHistory = async (id: string) => {
    try {
      const result = await creationApi.deletePromptPrecreationHistory(id);
      setHistoryRecords((prev) => prev.filter((item) => item.id !== id));
      if (result.latest) {
        const latestRecord = toPromptHistoryRecord(result.latest, charas);
        upsertHistoryRecord(latestRecord);
        applyHistoryRecordToMain(latestRecord);
      } else {
        setActiveHistoryId(null);
        setGenState("idle");
        setCards([]);
        setGenError(null);
        setStatusStep(null);
        onPromptSessionChange?.(null);
      }
    } catch (e) {
      if (e instanceof ApiError) {
        setGenError(e.message);
      }
    }
  };

  const handleClearAll = () => {
    setShowClearConfirm(true);
  };

  const confirmClearAll = () => {
    clearTipTimer();
    clearPollTimer();
    cancelledRef.current = true;
    sessionCharaIdRef.current = "";
    lastAutoSubmitKeyRef.current = "";
    lastStartUsedServerChainRef.current = false;
    setSeedPrompt("");
    setPromptCount(3);
    setCards([]);
    setDetailCard(null);
    setGenError(null);
    setStatusStep(null);
    setGenState("idle");
    setActiveHistoryId(null);
    setShowClearConfirm(false);
    onPromptSessionChange?.(null);
  };

  const handleSaveCard = (id: string, newPrompt: string) => {
    setCards((prev) => {
      const next = prev.map((c) => (c.id === id ? { ...c, fullPrompt: newPrompt } : c));
      if (activeHistoryId) {
        setHistoryRecords((records) =>
          records.map((record) =>
            record.id === activeHistoryId ? { ...record, cards: next, promptCount: next.length } : record
          )
        );
      }
      if (genState === "done" && sessionCharaIdRef.current && next.length > 0) {
        onPromptSessionChange?.({
          charaId: sessionCharaIdRef.current,
          cards: next,
          updatedAt: Date.now(),
        });
      }
      return next;
    });
    if (detailCard?.id === id) {
      setDetailCard((prev) => (prev ? { ...prev, fullPrompt: newPrompt } : prev));
    }
  };

  useEffect(() => {
    if (lastStartUsedServerChainRef.current) return;
    if (!autoSubmitEnabled || !onAutoSubmit || !autoSubmitConfig) return;
    if (genState !== "done" || cards.length === 0 || !activeHistoryId) return;
    const baseRecord = historyRecords.find((r) => r.id === activeHistoryId);
    if (!baseRecord) return;
    const key = `${baseRecord.id}|${cards.map((c) => c.id).join(",")}`;
    if (key === lastAutoSubmitKeyRef.current) return;
    lastAutoSubmitKeyRef.current = key;
    onAutoSubmit({ ...baseRecord, cards, promptCount: cards.length }, autoSubmitConfig);
    setShowAutoSubmitToast(true);
    if (toastTimerRef.current !== null) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setShowAutoSubmitToast(false), 2800);
  }, [
    genState,
    autoSubmitEnabled,
    autoSubmitConfig,
    activeHistoryId,
    cards,
    historyRecords,
    onAutoSubmit,
    onChainedQuickCreateResume,
  ]);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      if (tipTimerRef.current !== null) {
        window.clearInterval(tipTimerRef.current);
        tipTimerRef.current = null;
      }
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      if (toastTimerRef.current !== null) {
        window.clearTimeout(toastTimerRef.current);
        toastTimerRef.current = null;
      }
    };
  }, []);

  const canSubmit =
    hasCharas &&
    !!selectedChara &&
    isPromptCharaSelectable(selectedChara) &&
    !!seedPrompt.trim();
  const submitDisabled = !canSubmit || genState === "generating" || !!listLoading;
  const stepHint = stepHintLabel(statusStep);

  const showClearButton = !!seedPrompt.trim() || cards.length > 0;

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div
          className="shrink-0 px-6 py-2.5 border-b border-rose-100/40 flex items-center justify-between"
          style={{ background: "rgba(255,255,255,0.2)" }}
        >
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 flex items-center justify-center">
              <i className="ri-flashlight-line text-rose-400 text-sm"></i>
            </div>
            <span
              className="text-xs text-rose-400/70"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              生成完成后自动提交到美图创作
            </span>
            <button
              type="button"
              onClick={() => onAutoSubmitToggle?.(!autoSubmitEnabled)}
              className="w-8 h-5 flex items-center justify-center cursor-pointer transition-all duration-200"
              style={{ color: autoSubmitEnabled ? "#f472b6" : "#e5a3b3" }}
              aria-label={autoSubmitEnabled ? "关闭自动提交" : "开启自动提交"}
            >
              <i className={autoSubmitEnabled ? "ri-toggle-fill text-lg" : "ri-toggle-line text-lg"}></i>
            </button>
            {autoSubmitEnabled && (
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
              >
                已开启
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => onOpenConfig?.()}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "rgba(253,164,175,0.1)",
              border: "1px solid rgba(253,164,175,0.2)",
              color: "#f472b6",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            <span className="w-3 h-3 flex items-center justify-center">
              <i className="ri-settings-3-line text-xs"></i>
            </span>
            默认配置
          </button>
        </div>

        <div
        className="shrink-0 px-6 py-5 border-b border-rose-100/40"
        style={{ background: "rgba(255,255,255,0.3)" }}
      >
        {listError && (
          <p className="text-xs text-amber-600 mb-3 rounded-xl px-3 py-2 bg-amber-50/80 border border-amber-100">
            {listError}
          </p>
        )}
        {genError && (
          <p className="text-xs text-rose-700 mb-3 rounded-xl px-3 py-2 bg-rose-50/90 border border-rose-100">
            {genError}
          </p>
        )}
        <div className="flex items-start gap-5">
          <div className="flex flex-col gap-3 w-52 shrink-0">
            <div>
              <label
                className="block text-xs font-medium text-rose-500 mb-1.5"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                <i className="ri-user-heart-line mr-1"></i>选择角色
              </label>
              <div className="relative">
                <select
                  value={selectedCharaId}
                  onChange={(e) => setSelectedCharaId(e.target.value)}
                  disabled={listLoading || !hasCharas}
                  className="w-full appearance-none rounded-xl px-3 py-2 text-sm outline-none cursor-pointer transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
                  style={{
                    background: "rgba(255,255,255,0.85)",
                    border: "1.5px solid rgba(253,164,175,0.3)",
                    color: "#7c3f5e",
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                  }}
                >
                  {!hasCharas && !listLoading ? (
                    <option value="">暂无角色，请先在「素材加工」中创建</option>
                  ) : hasCharas && !hasSelectableChara ? (
                    <>
                      <option value="">暂无「资料已完善」的角色</option>
                      {charas.map((c) => (
                        <option key={c.id} value={c.id} disabled>
                          {charaSelectOptionLabel(c)}
                        </option>
                      ))}
                    </>
                  ) : (
                    charas.map((c) => (
                      <option key={c.id} value={c.id} disabled={!isPromptCharaSelectable(c)}>
                        {charaSelectOptionLabel(c)}
                      </option>
                    ))
                  )}
                </select>
                <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none w-4 h-4 flex items-center justify-center">
                  <i className="ri-arrow-down-s-line text-rose-400 text-sm"></i>
                </div>
              </div>
              {hasCharas &&
                !listLoading &&
                charas.some((c) => !isPromptCharaSelectable(c)) && (
                  <p className="text-[11px] text-rose-400/70 mt-1.5 leading-snug">
                    <span className="mr-2.5">✓ 资料已完善</span>
                    <span>✗ 资料未完善</span>
                  </p>
                )}
              {listLoading && (
                <p className="text-xs text-rose-300/70 mt-2">正在加载角色列表…</p>
              )}
              {selectedChara && !listLoading && (
                <div
                  className="flex items-center gap-2 mt-2 px-2.5 py-1.5 rounded-xl"
                  style={{
                    background: "rgba(253,164,175,0.1)",
                    border: "1px solid rgba(253,164,175,0.2)",
                  }}
                >
                  <div className="w-7 h-7 rounded-lg overflow-hidden shrink-0 border border-rose-100">
                    {selectedChara.avatarUrl ? (
                      <img
                        src={selectedChara.avatarUrl}
                        alt={selectedChara.name}
                        className="w-full h-full object-cover object-top"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-rose-50">
                        <i className="ri-user-heart-line text-rose-300 text-xs"></i>
                      </div>
                    )}
                  </div>
                  <div className="min-w-0">
                    <p
                      className="text-xs font-bold text-rose-600 truncate"
                      style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                    >
                      {selectedChara.name}
                    </p>
                    <p className="text-xs text-rose-400/60 truncate">
                      {selectedChara.settingText.trim()
                        ? `${selectedChara.settingText.slice(0, 18)}${selectedChara.settingText.length > 18 ? "…" : ""}`
                        : "暂无设定摘要"}
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div>
              <label
                className="block text-xs font-medium text-rose-500 mb-1.5"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                <i className="ri-stack-line mr-1"></i>生成数量
              </label>
              <div className="flex items-center gap-2">
                {COUNT_OPTIONS.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setPromptCount(n)}
                    className="flex-1 py-1.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap"
                    style={{
                      background:
                        promptCount === n
                          ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                          : "rgba(255,255,255,0.7)",
                      border:
                        promptCount === n
                          ? "1.5px solid transparent"
                          : "1.5px solid rgba(253,164,175,0.25)",
                      color: promptCount === n ? "white" : "#f472b6",
                      fontFamily: "'ZCOOL KuaiLe', cursive",
                      boxShadow:
                        promptCount === n ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
                    }}
                  >
                    {n} 个
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex-1 flex flex-col gap-2 min-w-0">
            <label
              className="block text-xs font-medium text-rose-500"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              <i className="ri-seedling-line mr-1"></i>种子提示词 Seed Prompt
              <span className="ml-2 text-rose-300/60 font-normal">
                描述你想要的画面氛围、场景、动作等
              </span>
            </label>
            <textarea
              value={seedPrompt}
              onChange={(e) => setSeedPrompt(e.target.value)}
              placeholder="例如：少女在樱花树下弹奏钢琴，阳光透过花瓣洒落，温柔而梦幻的氛围..."
              rows={4}
              className="w-full resize-none rounded-2xl px-4 py-3 text-sm leading-relaxed outline-none transition-all duration-200"
              style={{
                background: "rgba(255,255,255,0.85)",
                border: "1.5px solid rgba(253,164,175,0.25)",
                color: "#7c3f5e",
                fontFamily: "'ZCOOL KuaiLe', cursive",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "rgba(244,114,182,0.5)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "rgba(253,164,175,0.25)";
              }}
            />
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <p className="text-xs text-rose-300/60">
                角色设定会自动融入，你只需要描述这次的画面想象～
              </p>
              <div className="flex items-center gap-2 shrink-0">
                {showClearButton && (
                  <button
                    type="button"
                    onClick={handleClearAll}
                    className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                    style={{
                      background: "rgba(253,164,175,0.08)",
                      border: "1.5px solid rgba(253,164,175,0.2)",
                      color: "#f472b6",
                      fontFamily: "'ZCOOL KuaiLe', cursive",
                    }}
                  >
                    <i className="ri-eraser-line text-sm"></i>
                    一键清空
                  </button>
                )}
                <button
                  type="button"
                  onClick={startGenerate}
                  disabled={submitDisabled}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-medium transition-all duration-200 whitespace-nowrap"
                  style={{
                    background: submitDisabled
                      ? "rgba(253,164,175,0.3)"
                      : "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                    color: submitDisabled ? "rgba(244,114,182,0.5)" : "white",
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    boxShadow: submitDisabled ? "none" : "0 2px 10px rgba(244,114,182,0.35)",
                    cursor: submitDisabled ? "not-allowed" : "pointer",
                  }}
                >
                  <i className="ri-sparkling-line text-sm"></i>
                  {genState === "generating" ? "生成中..." : "开始生成"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5">
        {genState === "idle" && (
          <div className="flex flex-col items-center justify-center h-full text-center py-16">
            <div
              className="w-20 h-20 flex items-center justify-center rounded-3xl mb-5"
              style={{
                background:
                  "linear-gradient(135deg, rgba(253,164,175,0.12) 0%, rgba(244,114,182,0.08) 100%)",
                border: "1.5px dashed rgba(244,114,182,0.2)",
              }}
            >
              <i className="ri-sparkling-2-line text-rose-300 text-3xl"></i>
            </div>
            <h3
              className="text-base font-bold text-rose-400/60 mb-2"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              还没有生成任何 Prompt 哦
            </h3>
            <p className="text-sm text-rose-300/50 max-w-xs leading-relaxed">
              选择一位角色，输入你的画面灵感，点击「开始生成」就可以啦～
            </p>
          </div>
        )}

        {genState === "generating" && (
          <div className="flex flex-col items-center justify-center h-full text-center py-16">
            <div className="relative mb-6">
              <div
                className="w-20 h-20 rounded-full flex items-center justify-center"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
                  border: "2px solid rgba(244,114,182,0.2)",
                }}
              >
                <i className="ri-sparkling-line text-rose-400 text-3xl"></i>
              </div>
              <div
                className="absolute inset-0 rounded-full"
                style={{
                  border: "2px solid transparent",
                  borderTopColor: "#f472b6",
                  borderRightColor: "rgba(244,114,182,0.3)",
                  animation: "pg-spin 1.2s linear infinite",
                }}
              />
            </div>
            <h3
              className="text-base font-bold text-rose-500 mb-2"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              Prompt 生成中～
            </h3>
            <p
              className="text-sm text-rose-400/70 transition-all duration-500"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              {LOADING_TIPS[tipIndex]}
            </p>
            {stepHint && <p className="text-xs text-rose-400/55 mt-2">{stepHint}</p>}
            <div className="flex items-center gap-1.5 mt-4">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-rose-300"
                  style={{
                    animation: "pg-bounce 1.2s ease-in-out infinite",
                    animationDelay: `${i * 0.2}s`,
                  }}
                />
              ))}
            </div>
          </div>
        )}

        {genState === "done" && cards.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-4 gap-2 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                <div
                  className="w-6 h-6 flex items-center justify-center rounded-lg"
                  style={{
                    background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                  }}
                >
                  <i className="ri-sparkling-fill text-white text-xs"></i>
                </div>
                <span
                  className="text-sm font-bold text-rose-600"
                  style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  生成完成！共 {cards.length} 个 Prompt
                </span>
                <span className="text-xs text-rose-300/60">点击卡片查看完整内容</span>
              </div>
              <button
                type="button"
                onClick={handleRegenerate}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                style={{
                  background: "rgba(253,164,175,0.1)",
                  border: "1px solid rgba(253,164,175,0.25)",
                  color: "#f472b6",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                <i className="ri-refresh-line text-sm"></i>
                重新生成
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {cards.map((card, i) => (
                <PromptCardItem
                  key={card.id}
                  card={card}
                  index={i}
                  onClick={() => setDetailCard(card)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      </div>

      <HistorySidebar
        records={historyRecords}
        activeId={activeHistoryId}
        onSelect={handleSelectHistory}
        onDelete={handleDeleteHistory}
      />

      <DetailPanel
        card={detailCard}
        onClose={() => setDetailCard(null)}
        onSave={handleSaveCard}
      />

      <ConfirmModal
        visible={showClearConfirm}
        title="一键清空当前内容？"
        desc="这会清除种子提示词和所有已生成的 Prompt，页面将恢复到初始状态哦～"
        confirmText="确认清空"
        onConfirm={confirmClearAll}
        onCancel={() => setShowClearConfirm(false)}
      />

      {showAutoSubmitToast && (
        <div
          className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[70] flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm text-white whitespace-nowrap transition-all duration-300"
          style={{
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            boxShadow: "0 4px 16px rgba(244,114,182,0.35)",
            fontFamily: "'ZCOOL KuaiLe', cursive",
          }}
          role="status"
        >
          <span className="w-4 h-4 flex items-center justify-center">
            <i className="ri-check-line text-sm"></i>
          </span>
          已自动提交到美图创作，正在切换中～
        </div>
      )}

      <style>{`
        @keyframes pg-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pg-bounce {
          0%, 100% { transform: translateY(0); opacity: 0.5; }
          50% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default PromptGenPage;
