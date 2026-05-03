import { useState, useCallback, useEffect, useRef } from "react";
import type { CreationPromptSession, PromptCard, PromptHistoryRecord } from "@/types/creation";
import type { CharaProfile } from "@/types/material";
import { DEFAULT_CHARA_AVATAR_PLACEHOLDER } from "@/types/material";
import { ApiError } from "@/services/api";
import * as creationApi from "@/services/creationApi";
import {
  mapQuickCreateResultsToGroups,
  quickCreateImageFromApiEntry,
} from "@/utils/quickCreateReview";
import {
  type QuickCreateRecord,
  type QuickCreateGroup,
  type QuickCreateImage,
  type AiComment,
} from "@/types/quickCreate";
import AiCommentModal from "./AiCommentModal";
import type { AutoSubmitPayload, ChainedQuickCreateResumePayload } from "../page";

type GenStatus = "idle" | "generating" | "done";

interface ImageLightbox {
  images: QuickCreateImage[];
  index: number;
}

const IMAGES_PER_PROMPT_OPTIONS = [1, 2, 3, 4] as const;
const ASPECT_RATIO_OPTIONS = [
  { label: "16:9", value: "16:9" },
  { label: "4:3", value: "4:3" },
  { label: "1:1", value: "1:1" },
  { label: "3:4", value: "3:4" },
  { label: "9:16", value: "9:16" },
] as const;

type AspectRatioValue = (typeof ASPECT_RATIO_OPTIONS)[number]["value"];

function clampN(n: number): (typeof IMAGES_PER_PROMPT_OPTIONS)[number] {
  const v = Math.round(Number(n));
  if (v >= 1 && v <= 4) return v as (typeof IMAGES_PER_PROMPT_OPTIONS)[number];
  return 2;
}

function clampAspect(ratio: string): AspectRatioValue {
  const allowed = ASPECT_RATIO_OPTIONS.map((o) => o.value);
  return (allowed.includes(ratio as AspectRatioValue) ? ratio : "16:9") as AspectRatioValue;
}

const GEN_HINTS = [
  "正在召唤创作灵感，请稍等一下下～",
  "AI 正在认真画画，不要催她哦～",
  "正在为每一份 Prompt 注入魔法✨",
  "快好了！美图正在从像素中诞生～",
  "最后一点点，马上就来啦～",
];
const POLL_INTERVAL_MS = 15000;
const QUICK_CREATE_ACTIVE_TASK_STORAGE_KEY = "aetherframe.creation.quickCreate.activeTask";

interface StoredQuickCreatePromptMeta {
  id: string;
  title: string;
  preview: string;
}

interface StoredQuickCreateTaskPayload {
  taskId: string;
  charaId: string;
  n: number;
  aspectRatio: string;
  prompts: StoredQuickCreatePromptMeta[];
}

interface QuickCreatePageProps {
  charas: CharaProfile[];
  promptSession: CreationPromptSession | null;
  autoStartPayload?: AutoSubmitPayload | null;
  onConsumePayload?: () => AutoSubmitPayload | null;
  /** 服务端已在预生成后创建一键创作任务：写入本地活跃任务并轮询 */
  chainedResume?: ChainedQuickCreateResumePayload | null;
  onConsumeChainedResume?: () => void;
}

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
    charaAvatar: chara?.avatarUrl || raw.chara_avatar || DEFAULT_CHARA_AVATAR_PLACEHOLDER,
    seedPrompt: raw.seed_prompt,
    promptCount: raw.prompt_count,
    status: raw.status,
    errorMessage: raw.error_message ?? null,
    cards: "cards" in raw ? raw.cards ?? [] : [],
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function LinkedTaskSelector({
  charas,
  historyItems,
  listLoading,
  value,
  pickingId,
  onPick,
  onClear,
}: {
  charas: CharaProfile[];
  historyItems: creationApi.PromptPrecreationHistoryItem[];
  listLoading: boolean;
  value: PromptHistoryRecord | null;
  pickingId: string | null;
  onPick: (item: creationApi.PromptPrecreationHistoryItem) => void;
  onClear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative w-full flex items-center gap-3 px-4 py-3 rounded-2xl cursor-pointer transition-all duration-200 text-left"
        style={{
          background: value
            ? "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)"
            : "rgba(255,255,255,0.6)",
          border: value
            ? "1.5px solid rgba(244,114,182,0.4)"
            : "1.5px dashed rgba(253,164,175,0.35)",
        }}
      >
        {value && (
          <div
            className="absolute top-3 right-[3.25rem] w-5 h-5 flex items-center justify-center rounded-full shrink-0 z-[1]"
            style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
            aria-hidden
          >
            <i className="ri-check-line text-white text-xs"></i>
          </div>
        )}

        {value ? (
          <>
            <div
              className="w-8 h-8 rounded-xl overflow-hidden shrink-0"
              style={{ border: "1.5px solid rgba(244,114,182,0.3)" }}
            >
              <img
                src={value.charaAvatar}
                alt=""
                className="w-full h-full object-cover object-top"
                draggable={false}
              />
            </div>
            <div className="flex-1 min-w-0 pr-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className="text-sm font-semibold text-rose-700/80"
                  style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  {value.charaName}
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(253,164,175,0.2)", color: "#f472b6" }}
                >
                  {value.promptCount} 份 Prompt
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(253,164,175,0.12)", color: "#fb7185" }}
                >
                  {fmtTime(value.createdAt)}
                </span>
              </div>
              <p className="text-xs text-rose-400/50 mt-0.5 truncate">{value.seedPrompt}</p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onClear();
                setOpen(false);
              }}
              className="w-6 h-6 flex items-center justify-center rounded-lg shrink-0 cursor-pointer transition-colors duration-200 z-[1]"
              style={{ color: "#f472b6", background: "rgba(253,164,175,0.15)" }}
              aria-label="取消关联"
            >
              <i className="ri-close-line text-xs"></i>
            </button>
          </>
        ) : (
          <>
            <div
              className="w-8 h-8 flex items-center justify-center rounded-xl shrink-0"
              style={{
                background:
                  "linear-gradient(135deg, rgba(253,164,175,0.2) 0%, rgba(244,114,182,0.15) 100%)",
                border: "1px solid rgba(253,164,175,0.25)",
              }}
            >
              <i className="ri-link text-rose-400 text-sm"></i>
            </div>
            <div className="flex-1 min-w-0">
              <p
                className="text-sm text-rose-500/70"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                选一个灵感来源～
              </p>
              <p className="text-xs text-rose-400/40 mt-0.5">
                从历史 Prompt 任务中挑一个，自动带出角色和 Prompt 卡片
              </p>
            </div>
            <div className="w-5 h-5 flex items-center justify-center shrink-0">
              <i
                className="ri-arrow-down-s-line text-rose-400 text-sm transition-transform duration-200"
                style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
              />
            </div>
          </>
        )}
      </button>

      {open && (
        <div
          className="absolute left-0 right-0 top-full mt-2 rounded-2xl overflow-hidden z-30"
          style={{
            background: "rgba(255,255,255,0.97)",
            border: "1px solid rgba(253,164,175,0.25)",
            boxShadow: "0 8px 32px rgba(244,114,182,0.12)",
            backdropFilter: "blur(12px)",
          }}
        >
          {listLoading ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div
                className="w-8 h-8 rounded-full mb-2"
                style={{
                  border: "2px solid rgba(253,164,175,0.25)",
                  borderTopColor: "#f472b6",
                  animation: "qc-spin 0.9s linear infinite",
                }}
              />
              <p className="text-xs text-rose-300/70">加载历史任务中…</p>
            </div>
          ) : historyItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <i className="ri-inbox-line text-rose-200 text-2xl mb-2"></i>
              <p className="text-xs text-rose-300/60">还没有历史 Prompt 任务哦～</p>
            </div>
          ) : (
            <div className="max-h-72 overflow-y-auto p-2 space-y-1">
              {historyItems.map((record) => {
                const chara = charas.find((c) => c.id === record.character_id) ?? null;
                const avatar =
                  chara?.avatarUrl || record.chara_avatar || DEFAULT_CHARA_AVATAR_PLACEHOLDER;
                const busy = pickingId === record.id;
                return (
                  <button
                    key={record.id}
                    type="button"
                    disabled={busy}
                    onClick={() => onPick(record)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 text-left disabled:opacity-60"
                    style={{
                      background:
                        value?.id === record.id
                          ? "linear-gradient(135deg, rgba(253,164,175,0.18) 0%, rgba(244,114,182,0.12) 100%)"
                          : "transparent",
                      border:
                        value?.id === record.id
                          ? "1px solid rgba(244,114,182,0.3)"
                          : "1px solid transparent",
                    }}
                    onMouseEnter={(e) => {
                      if (value?.id !== record.id) {
                        (e.currentTarget as HTMLButtonElement).style.background =
                          "rgba(253,164,175,0.08)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (value?.id !== record.id) {
                        (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                      }
                    }}
                  >
                    <div
                      className="w-9 h-9 rounded-xl overflow-hidden shrink-0"
                      style={{ border: "1.5px solid rgba(244,114,182,0.25)" }}
                    >
                      <img
                        src={avatar}
                        alt=""
                        className="w-full h-full object-cover object-top"
                        draggable={false}
                      />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className="text-sm font-semibold text-rose-700/80"
                          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                        >
                          {record.chara_name}
                        </span>
                        <span
                          className="text-xs px-1.5 py-0.5 rounded-full"
                          style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
                        >
                          {record.prompt_count} 份
                        </span>
                      </div>
                      <p className="text-xs text-rose-400/50 mt-0.5 truncate">{record.seed_prompt}</p>
                      <p className="text-xs text-rose-300/50 mt-0.5">{fmtTime(record.created_at)}</p>
                    </div>

                    {busy ? (
                      <div
                        className="w-5 h-5 shrink-0 rounded-full"
                        style={{
                          border: "2px solid rgba(253,164,175,0.3)",
                          borderTopColor: "#f472b6",
                          animation: "qc-spin 0.8s linear infinite",
                        }}
                      />
                    ) : value?.id === record.id ? (
                      <div
                        className="w-5 h-5 flex items-center justify-center rounded-full shrink-0"
                        style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
                      >
                        <i className="ri-check-line text-white text-xs"></i>
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function fmtTime(value: string): string {
  const t = new Date(value);
  if (Number.isNaN(t.getTime())) return value;
  return t.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function PromptSelectCard({
  card,
  selected,
  onToggle,
}: {
  card: PromptCard;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="relative w-full text-left rounded-2xl p-4 cursor-pointer transition-all duration-200 whitespace-normal"
      style={{
        background: selected
          ? "linear-gradient(135deg, rgba(253,164,175,0.18) 0%, rgba(244,114,182,0.12) 100%)"
          : "rgba(255,255,255,0.6)",
        border: selected
          ? "1.5px solid rgba(244,114,182,0.5)"
          : "1.5px solid rgba(253,164,175,0.2)",
      }}
    >
      <div
        className="absolute top-3 right-3 w-5 h-5 flex items-center justify-center rounded-full transition-all duration-200"
        style={{
          background: selected
            ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
            : "rgba(253,164,175,0.15)",
          border: selected ? "none" : "1.5px solid rgba(253,164,175,0.3)",
        }}
      >
        {selected && <i className="ri-check-line text-white text-xs"></i>}
      </div>

      <div className="flex flex-wrap gap-1 mb-2 pr-7">
        {card.tags.map((tag) => (
          <span
            key={tag}
            className="text-xs px-2 py-0.5 rounded-full"
            style={{
              background: "rgba(253,164,175,0.15)",
              color: "#f472b6",
            }}
          >
            {tag}
          </span>
        ))}
      </div>

      <p
        className="text-sm font-semibold text-rose-700/80 mb-1"
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        {card.title}
      </p>

      <p className="text-xs text-rose-400/60 leading-relaxed line-clamp-2">{card.preview}</p>
    </button>
  );
}

function ResultImage({
  img,
  onClick,
  onViewComment,
}: {
  img: QuickCreateImage;
  onClick: () => void;
  onViewComment: () => void;
}) {
  return (
    <div
      className="relative group rounded-xl overflow-hidden w-full"
      style={{ border: "1px solid rgba(253,164,175,0.2)" }}
    >
      <button
        type="button"
        onClick={onClick}
        className="relative w-full cursor-pointer transition-all duration-200 text-left block"
        aria-label="查看大图"
      >
        <div className="w-full aspect-square">
          <img
            src={img.url}
            alt=""
            className="w-full h-full object-cover object-top"
            draggable={false}
          />
        </div>
        <div
          className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none"
          style={{ background: "rgba(244,114,182,0.25)" }}
        >
          <div className="w-8 h-8 flex items-center justify-center rounded-full bg-white/80">
            <i className="ri-zoom-in-line text-rose-500 text-sm"></i>
          </div>
        </div>
      </button>

      {img.aiComment && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onViewComment();
          }}
          className="absolute bottom-2 right-2 z-10 flex items-center gap-1 px-2.5 py-1 rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap hover:opacity-90 pointer-events-auto"
          style={{
            fontFamily: "'ZCOOL KuaiLe', cursive",
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            color: "white",
            boxShadow: "0 2px 10px rgba(244,114,182,0.4)",
          }}
        >
          <span className="w-3 h-3 flex items-center justify-center" aria-hidden>
            <i className="ri-robot-2-line text-xs"></i>
          </span>
          AI 评论
        </button>
      )}
    </div>
  );
}

function ResultGroup({
  group,
  cols,
  onImageClick,
  onViewComment,
}: {
  group: QuickCreateGroup;
  cols: number;
  onImageClick: (images: QuickCreateImage[], index: number) => void;
  onViewComment: (img: QuickCreateImage, promptTitle: string) => void;
}) {
  return (
    <div
      className="rounded-2xl p-4"
      style={{
        background: "rgba(255,255,255,0.6)",
        border: "1px solid rgba(253,164,175,0.18)",
      }}
    >
      <div className="flex items-start gap-2 mb-3">
        <div
          className="w-5 h-5 flex items-center justify-center rounded-lg shrink-0 mt-0.5"
          style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
        >
          <i className="ri-quill-pen-line text-white text-xs"></i>
        </div>
        <div className="min-w-0">
          <p
            className="text-sm font-semibold text-rose-700/80"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            {group.promptTitle}
          </p>
          <p className="text-xs text-rose-400/50 mt-0.5 line-clamp-1">{group.promptPreview}</p>
        </div>
      </div>

      <div
        className="grid gap-2"
        style={{
          gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
        }}
      >
        {group.images.map((img, idx) => (
          <ResultImage
            key={img.id}
            img={img}
            onClick={() => onImageClick(group.images, idx)}
            onViewComment={() => onViewComment(img, group.promptTitle)}
          />
        ))}
      </div>
    </div>
  );
}

function HistoryItem({
  record,
  active,
  onView,
  onDelete,
}: {
  record: QuickCreateRecord;
  active: boolean;
  onView: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      className="rounded-2xl p-3 cursor-pointer transition-all duration-200 group"
      style={{
        background: active ? "rgba(253,164,175,0.22)" : "rgba(255,255,255,0.55)",
        border: active
          ? "1px solid rgba(244,114,182,0.35)"
          : "1px solid rgba(253,164,175,0.18)",
      }}
      onClick={onView}
    >
      <div className="flex items-start gap-2">
        <div className="w-8 h-8 rounded-xl overflow-hidden shrink-0 border border-rose-100/50">
          <img
            src={record.charaAvatar}
            alt=""
            className="w-full h-full object-cover object-top"
            draggable={false}
          />
        </div>

        <div className="flex-1 min-w-0">
          <p
            className="text-xs font-semibold text-rose-700/80 truncate"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            {record.charaName}
          </p>
          <p className="text-xs text-rose-400/50 mt-0.5">{record.createdAt}</p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
            >
              {record.promptCount} 份 Prompt
            </span>
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
            >
              每份 {record.imagesPerPrompt} 张
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="w-6 h-6 flex items-center justify-center rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 cursor-pointer shrink-0"
          style={{ color: "#f472b6", background: "rgba(253,164,175,0.15)" }}
          aria-label="删除记录"
        >
          <i className="ri-delete-bin-line text-xs"></i>
        </button>
      </div>
    </div>
  );
}

function Lightbox({
  lightbox,
  onClose,
  onPrev,
  onNext,
}: {
  lightbox: ImageLightbox;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}) {
  const img = lightbox.images[lightbox.index];
  const total = lightbox.images.length;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") onPrev();
      if (e.key === "ArrowRight") onNext();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, onPrev, onNext]);

  return (
    <div
      className="fixed inset-0 z-[60] flex flex-col items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative max-w-4xl w-full flex flex-col items-center gap-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative rounded-2xl overflow-hidden bg-black/20 max-h-[85vh] flex items-center justify-center">
          <img
            src={img.url}
            alt=""
            className="max-h-[85vh] w-auto max-w-full object-contain"
            draggable={false}
          />

          <button
            type="button"
            onClick={onClose}
            className="absolute top-3 right-3 w-9 h-9 flex items-center justify-center rounded-full cursor-pointer"
            style={{ background: "rgba(0,0,0,0.45)", color: "white" }}
            aria-label="关闭"
          >
            <i className="ri-close-line text-lg"></i>
          </button>

          {total > 1 && (
            <>
              <button
                type="button"
                onClick={onPrev}
                className="absolute left-3 top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center rounded-full cursor-pointer"
                style={{ background: "rgba(0,0,0,0.45)", color: "white" }}
                aria-label="上一张"
              >
                <i className="ri-arrow-left-s-line text-lg"></i>
              </button>
              <button
                type="button"
                onClick={onNext}
                className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center rounded-full cursor-pointer"
                style={{ background: "rgba(0,0,0,0.45)", color: "white" }}
                aria-label="下一张"
              >
                <i className="ri-arrow-right-s-line text-lg"></i>
              </button>
              <div
                className="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-full text-xs text-white"
                style={{ background: "rgba(0,0,0,0.45)" }}
              >
                {lightbox.index + 1} / {total}
              </div>
            </>
          )}
        </div>

        <p className="text-xs text-white/70 text-center">
          键盘 <kbd className="px-1 py-0.5 rounded bg-white/10">←</kbd>{" "}
          <kbd className="px-1 py-0.5 rounded bg-white/10">→</kbd> 切换 ·{" "}
          <kbd className="px-1 py-0.5 rounded bg-white/10">Esc</kbd> 关闭
        </p>
      </div>
    </div>
  );
}

export default function QuickCreatePage({
  charas,
  promptSession,
  autoStartPayload = null,
  onConsumePayload,
  chainedResume = null,
  onConsumeChainedResume,
}: QuickCreatePageProps) {
  const [linkedTask, setLinkedTask] = useState<PromptHistoryRecord | null>(null);
  const [serverDefaultTask, setServerDefaultTask] = useState<PromptHistoryRecord | null>(null);
  const [promptHistoryItems, setPromptHistoryItems] = useState<creationApi.PromptPrecreationHistoryItem[]>(
    []
  );
  const [promptHistoryListLoading, setPromptHistoryListLoading] = useState(true);
  const [pickingHistoryId, setPickingHistoryId] = useState<string | null>(null);

  /** Prompt 页刚推过来的承接会话（生成中/未完成时通常无卡片） */
  const hasLivePromptSession = (promptSession?.cards?.length ?? 0) > 0;

  const allPrompts = linkedTask
    ? linkedTask.cards
    : hasLivePromptSession
      ? promptSession!.cards
      : serverDefaultTask?.cards ?? [];

  const effectiveCharaId = linkedTask
    ? linkedTask.charaId
    : hasLivePromptSession
      ? promptSession!.charaId
      : serverDefaultTask?.charaId ?? null;

  const sessionChara =
    effectiveCharaId && charas.length > 0
      ? charas.find((c) => c.id === effectiveCharaId) ?? null
      : null;

  const displayName = linkedTask
    ? linkedTask.charaName || sessionChara?.name || "未知角色"
    : sessionChara?.name ??
      serverDefaultTask?.charaName ??
      (effectiveCharaId ? "未知角色" : "—");
  const displayAvatar = linkedTask
    ? linkedTask.charaAvatar || sessionChara?.avatarUrl || DEFAULT_CHARA_AVATAR_PLACEHOLDER
    : sessionChara?.avatarUrl ??
      serverDefaultTask?.charaAvatar ??
      DEFAULT_CHARA_AVATAR_PLACEHOLDER;

  const activeCharaId = effectiveCharaId;

  const [selectedPromptIds, setSelectedPromptIds] = useState<Set<string>>(() => new Set());
  const [imagesPerPrompt, setImagesPerPrompt] = useState<(typeof IMAGES_PER_PROMPT_OPTIONS)[number]>(2);
  const [aspectRatio, setAspectRatio] =
    useState<(typeof ASPECT_RATIO_OPTIONS)[number]["value"]>("16:9");
  const [genStatus, setGenStatus] = useState<GenStatus>("idle");
  const [hintIndex, setHintIndex] = useState(0);
  const [resultGroups, setResultGroups] = useState<QuickCreateGroup[]>([]);
  const [lightbox, setLightbox] = useState<ImageLightbox | null>(null);
  const [viewingComment, setViewingComment] = useState<{
    comment: AiComment;
    imageUrl: string;
    promptTitle: string;
  } | null>(null);
  const [historyRecords, setHistoryRecords] = useState<QuickCreateRecord[]>([]);
  const [viewingRecord, setViewingRecord] = useState<QuickCreateRecord | null>(null);
  const [genError, setGenError] = useState<string | null>(null);

  const genHintTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  /** Browser timer id; avoid NodeJS.Timeout vs number mismatch under mixed DOM/Node typings */
  const pollTimerRef = useRef<number | null>(null);
  const cancelledRef = useRef(false);
  const skipNextSelectionResetRef = useRef(false);
  const lastConsumedPayloadKeyRef = useRef("");
  const lastChainedResumeKeyRef = useRef("");

  const clearQuickCreateActiveTaskStorage = useCallback(() => {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(QUICK_CREATE_ACTIVE_TASK_STORAGE_KEY);
  }, []);

  const writeQuickCreateActiveTaskStorage = useCallback(
    (payload: StoredQuickCreateTaskPayload) => {
      if (typeof window === "undefined") return;
      if (!payload.taskId || !payload.charaId || !Array.isArray(payload.prompts)) return;
      window.localStorage.setItem(QUICK_CREATE_ACTIVE_TASK_STORAGE_KEY, JSON.stringify(payload));
    },
    []
  );

  const readQuickCreateActiveTaskStorage = useCallback((): StoredQuickCreateTaskPayload | null => {
    if (typeof window === "undefined") return null;
    const raw = window.localStorage.getItem(QUICK_CREATE_ACTIVE_TASK_STORAGE_KEY);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as Partial<StoredQuickCreateTaskPayload>;
      if (
        !parsed ||
        typeof parsed.taskId !== "string" ||
        typeof parsed.charaId !== "string" ||
        typeof parsed.n !== "number" ||
        typeof parsed.aspectRatio !== "string" ||
        !Array.isArray(parsed.prompts)
      ) {
        clearQuickCreateActiveTaskStorage();
        return null;
      }
      const prompts = parsed.prompts
        .filter((p): p is StoredQuickCreatePromptMeta => !!p && typeof p.id === "string")
        .map((p) => ({
          id: p.id,
          title: typeof p.title === "string" ? p.title : "",
          preview: typeof p.preview === "string" ? p.preview : "",
        }));
      return {
        taskId: parsed.taskId.trim(),
        charaId: parsed.charaId.trim(),
        n: parsed.n,
        aspectRatio: parsed.aspectRatio,
        prompts,
      };
    } catch {
      clearQuickCreateActiveTaskStorage();
      return null;
    }
  }, [clearQuickCreateActiveTaskStorage]);

  const buildGroupsFromHistoryDetail = useCallback(
    (detail: creationApi.QuickCreateHistoryDetailResponse): QuickCreateGroup[] => {
      const promptMetaMap = new Map((detail.selected_prompts ?? []).map((p) => [p.id, p.fullPrompt] as const));
      return (detail.results ?? []).map((r) => ({
        promptId: r.prompt_id,
        promptTitle: r.prompt_id,
        promptPreview: promptMetaMap.get(r.prompt_id)?.slice(0, 80) || r.full_prompt.slice(0, 80),
        images: (r.generated_images ?? []).map((img, i) =>
          quickCreateImageFromApiEntry(detail.task_id, r.prompt_id, i, img)
        ),
      }));
    },
    []
  );

  const toQuickCreateRecord = useCallback(
    (
      raw: creationApi.QuickCreateHistoryItem | creationApi.QuickCreateHistoryDetailResponse
    ): QuickCreateRecord => {
      const chara = charas.find((c) => c.id === raw.character_id);
      const groups =
        "results" in raw
          ? buildGroupsFromHistoryDetail(raw as creationApi.QuickCreateHistoryDetailResponse)
          : [];
      return {
        id: raw.id,
        taskId: raw.task_id,
        charaId: raw.character_id,
        charaName: raw.chara_name || chara?.name || "未知角色",
        charaAvatar: chara?.avatarUrl || raw.chara_avatar || DEFAULT_CHARA_AVATAR_PLACEHOLDER,
        promptCount: raw.prompt_count,
        imageCount: raw.image_count,
        imagesPerPrompt: raw.n,
        status: raw.status,
        errorMessage: raw.error_message ?? null,
        createdAt: fmtTime(raw.created_at),
        updatedAt: raw.updated_at,
        groups,
      };
    },
    [buildGroupsFromHistoryDetail, charas]
  );

  const upsertRecord = useCallback((record: QuickCreateRecord) => {
    setHistoryRecords((prev) => {
      const existed = prev.some((x) => x.id === record.id);
      if (!existed) return [record, ...prev];
      return prev.map((x) => (x.id === record.id ? record : x));
    });
  }, []);

  const applyRecordToView = useCallback((record: QuickCreateRecord) => {
    setViewingRecord(record);
    setResultGroups(record.groups);
    if (record.status === "failed") {
      setGenError(record.errorMessage || "一键创作失败");
      setGenStatus("idle");
      return;
    }
    if (record.status === "completed") {
      setGenError(null);
      setGenStatus("done");
      return;
    }
    setGenError(null);
    setGenStatus("generating");
  }, []);

  useEffect(() => {
    return () => {
      if (genHintTimerRef.current) clearInterval(genHintTimerRef.current);
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      cancelledRef.current = true;
    };
  }, []);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const [latest, list] = await Promise.all([
          creationApi.getLatestQuickCreateHistory(),
          creationApi.listQuickCreateHistory({ limit: 50, offset: 0 }),
        ]);
        setHistoryRecords(list.items.map((x) => toQuickCreateRecord(x)));
        if (latest) {
          const rec = toQuickCreateRecord(latest);
          upsertRecord(rec);
          applyRecordToView(rec);
        }
      } catch {
        // ignore history preload failure
      }
    };
    void loadHistory();
  }, [applyRecordToView, toQuickCreateRecord, upsertRecord]);

  const reloadPromptPrecreationPickers = useCallback(async () => {
    setPromptHistoryListLoading(true);
    try {
      const [latestDone, list] = await Promise.all([
        creationApi.getLatestCompletedPromptPrecreationHistory(),
        creationApi.listPromptPrecreationHistory({ limit: 80, offset: 0, status: "completed" }),
      ]);
      setServerDefaultTask(latestDone ? toPromptHistoryRecord(latestDone, charas) : null);
      setPromptHistoryItems(list.items ?? []);
    } catch {
      setServerDefaultTask(null);
      setPromptHistoryItems([]);
    } finally {
      setPromptHistoryListLoading(false);
    }
  }, [charas]);

  useEffect(() => {
    void reloadPromptPrecreationPickers();
  }, [reloadPromptPrecreationPickers]);

  const resetGenerationUi = useCallback(() => {
    cancelledRef.current = true;
    if (genHintTimerRef.current) {
      clearInterval(genHintTimerRef.current);
      genHintTimerRef.current = null;
    }
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    clearQuickCreateActiveTaskStorage();
    setGenStatus("idle");
    setResultGroups([]);
    setViewingRecord(null);
    setGenError(null);
    setHintIndex(0);
  }, [clearQuickCreateActiveTaskStorage]);

  const handleLinkedTaskChange = useCallback(
    (record: PromptHistoryRecord | null) => {
      resetGenerationUi();
      setLinkedTask(record);
      if (record === null) {
        void reloadPromptPrecreationPickers();
      }
    },
    [resetGenerationUi, reloadPromptPrecreationPickers]
  );

  const handlePickPromptHistoryItem = useCallback(
    async (item: creationApi.PromptPrecreationHistoryItem) => {
      const id = String(item.id ?? "").trim();
      if (!id) return;
      setPickingHistoryId(id);
      try {
        const detail = await creationApi.getPromptPrecreationHistory(id);
        const rec = toPromptHistoryRecord(detail, charas);
        handleLinkedTaskChange(rec);
      } catch (e) {
        setGenError(e instanceof ApiError ? e.message : "加载 Prompt 任务详情失败");
      } finally {
        setPickingHistoryId(null);
      }
    },
    [charas, handleLinkedTaskChange]
  );

  useEffect(() => {
    if (skipNextSelectionResetRef.current) {
      skipNextSelectionResetRef.current = false;
      return;
    }
    if (linkedTask) {
      const cards = linkedTask.cards ?? [];
      setSelectedPromptIds(cards.length ? new Set(cards.map((p) => p.id)) : new Set());
      return;
    }
    if (hasLivePromptSession) {
      const cards = promptSession?.cards ?? [];
      setSelectedPromptIds(cards.length ? new Set(cards.map((p) => p.id)) : new Set());
      return;
    }
    const cards = serverDefaultTask?.cards ?? [];
    setSelectedPromptIds(cards.length ? new Set(cards.map((p) => p.id)) : new Set());
  }, [
    linkedTask,
    hasLivePromptSession,
    promptSession?.updatedAt,
    serverDefaultTask?.id,
    serverDefaultTask?.updatedAt,
  ]);

  const pollQuickCreateTask = useCallback(
    async (taskId: string, promptMetas: StoredQuickCreatePromptMeta[]) => {
      const tid = String(taskId ?? "").trim();
      if (!tid) return;
      cancelledRef.current = false;
      setGenError(null);
      setViewingRecord(null);
      setGenStatus("generating");
      setHintIndex(0);
      if (genHintTimerRef.current) clearInterval(genHintTimerRef.current);
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      genHintTimerRef.current = setInterval(() => {
        setHintIndex((prev) => (prev + 1) % GEN_HINTS.length);
      }, 1200);
      const finishError = (msg: string) => {
        if (genHintTimerRef.current) {
          clearInterval(genHintTimerRef.current);
          genHintTimerRef.current = null;
        }
        if (pollTimerRef.current) {
          clearTimeout(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        clearQuickCreateActiveTaskStorage();
        setGenError(msg);
        setGenStatus("idle");
      };
      const schedulePoll = (delay: number) => {
        if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
        pollTimerRef.current = window.setTimeout(() => void runPoll(), delay);
      };
      const runPoll = async () => {
        if (cancelledRef.current) return;
        try {
          const st = await creationApi.getQuickCreateTaskStatus(tid);
          if (cancelledRef.current) return;
          if (st.status === "failed") {
            try {
              const detail = await creationApi.getQuickCreateHistory(tid);
              const record = toQuickCreateRecord(detail);
              upsertRecord(record);
              applyRecordToView(record);
            } catch {
              // ignore
            }
            finishError(st.error_message?.trim() || "一键创作失败");
            return;
          }
          if (st.status !== "completed") {
            schedulePoll(POLL_INTERVAL_MS);
            return;
          }
          if (genHintTimerRef.current) {
            clearInterval(genHintTimerRef.current);
            genHintTimerRef.current = null;
          }
          if (pollTimerRef.current) {
            clearTimeout(pollTimerRef.current);
            pollTimerRef.current = null;
          }
          clearQuickCreateActiveTaskStorage();
          try {
            const detail = await creationApi.getQuickCreateHistory(tid);
            const record = toQuickCreateRecord(detail);
            upsertRecord(record);
            applyRecordToView(record);
          } catch {
            const rawResults = st.results ?? [];
            setResultGroups(mapQuickCreateResultsToGroups(tid, rawResults));
            setGenStatus("done");
          }
        } catch (e) {
          if (cancelledRef.current) return;
          finishError(e instanceof ApiError ? e.message : "获取一键创作任务状态失败");
        }
      };
      void runPoll();
    },
    [applyRecordToView, clearQuickCreateActiveTaskStorage, toQuickCreateRecord, upsertRecord]
  );

  useEffect(() => {
    const active = readQuickCreateActiveTaskStorage();
    if (!active) return;
    void pollQuickCreateTask(active.taskId, active.prompts);
  }, [pollQuickCreateTask, readQuickCreateActiveTaskStorage]);

  const selectedPrompts = allPrompts.filter((p) => selectedPromptIds.has(p.id));

  const togglePrompt = useCallback((id: string) => {
    setSelectedPromptIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    if (selectedPromptIds.size === allPrompts.length) {
      setSelectedPromptIds(new Set());
    } else {
      setSelectedPromptIds(new Set(allPrompts.map((p) => p.id)));
    }
  }, [selectedPromptIds.size, allPrompts]);

  const startGenerateWith = useCallback(
    async (params: {
      charaId: string;
      prompts: PromptCard[];
      n: (typeof IMAGES_PER_PROMPT_OPTIONS)[number];
      aspectRatio: AspectRatioValue;
      overrideCharaName?: string;
      overrideCharaAvatar?: string;
    }) => {
      const cid = params.charaId.trim();
      const { prompts, n, aspectRatio: ratio } = params;
      if (prompts.length === 0 || !cid) return;

      const charaFromList = charas.find((c) => c.id === cid) ?? null;
      const charaName =
        params.overrideCharaName ??
        charaFromList?.name ??
        linkedTask?.charaName ??
        serverDefaultTask?.charaName ??
        "未知角色";
      const charaAvatar =
        params.overrideCharaAvatar ??
        charaFromList?.avatarUrl ??
        linkedTask?.charaAvatar ??
        serverDefaultTask?.charaAvatar ??
        DEFAULT_CHARA_AVATAR_PLACEHOLDER;

      try {
        const start = await creationApi.startQuickCreate(cid, {
          selected_prompts: prompts.map((p) => ({ id: p.id, fullPrompt: p.fullPrompt })),
          n,
          aspect_ratio: ratio,
        });
        writeQuickCreateActiveTaskStorage({
          taskId: start.task_id,
          charaId: cid,
          n,
          aspectRatio: ratio,
          prompts: prompts.map((p) => ({
            id: p.id,
            title: p.title,
            preview: p.preview,
          })),
        });
        const pendingRecord: QuickCreateRecord = {
          id: start.task_id,
          taskId: start.task_id,
          charaId: cid,
          charaName,
          charaAvatar,
          promptCount: prompts.length,
          imageCount: 0,
          imagesPerPrompt: n,
          status: "pending",
          errorMessage: null,
          createdAt: fmtTime(new Date().toISOString()),
          updatedAt: new Date().toISOString(),
          groups: [],
        };
        upsertRecord(pendingRecord);
        applyRecordToView(pendingRecord);

        try {
          const detail = await creationApi.getQuickCreateHistory(start.task_id);
          const serverPending = toQuickCreateRecord(detail);
          upsertRecord(serverPending);
          applyRecordToView(serverPending);
        } catch {
          // keep local pending
        }
        void pollQuickCreateTask(
          start.task_id,
          prompts.map((p) => ({
            id: p.id,
            title: p.title,
            preview: p.preview,
          }))
        );
      } catch (e) {
        clearQuickCreateActiveTaskStorage();
        setGenError(e instanceof ApiError ? e.message : "启动一键创作失败");
        setGenStatus("idle");
      }
    },
    [
      charas,
      linkedTask?.charaAvatar,
      linkedTask?.charaName,
      serverDefaultTask?.charaAvatar,
      serverDefaultTask?.charaName,
      pollQuickCreateTask,
      writeQuickCreateActiveTaskStorage,
      clearQuickCreateActiveTaskStorage,
      upsertRecord,
      applyRecordToView,
      toQuickCreateRecord,
    ]
  );

  const startGenerate = useCallback(async () => {
    const prompts = allPrompts.filter((p) => selectedPromptIds.has(p.id));
    const charaId = activeCharaId?.trim();
    if (prompts.length === 0 || !charaId) return;
    await startGenerateWith({
      charaId,
      prompts,
      n: imagesPerPrompt,
      aspectRatio,
    });
  }, [
    activeCharaId,
    allPrompts,
    selectedPromptIds,
    imagesPerPrompt,
    aspectRatio,
    startGenerateWith,
  ]);

  useEffect(() => {
    if (!autoStartPayload) return;
    const { record, config } = autoStartPayload;
    if (!record?.cards?.length || !record.charaId?.trim()) return;

    const previewCards = record.cards.slice(0, config.promptCount);
    const key = `${record.id}|${config.promptCount}|${config.imagesPerPrompt}|${config.aspectRatio}|${previewCards.map((p) => p.id).join(",")}`;
    if (lastConsumedPayloadKeyRef.current === key) return;
    lastConsumedPayloadKeyRef.current = key;

    const payload = onConsumePayload?.() ?? autoStartPayload;
    if (!payload) return;

    const selectedCards = payload.record.cards.slice(0, payload.config.promptCount);
    if (selectedCards.length === 0) return;

    const n = clampN(payload.config.imagesPerPrompt);
    const ratio = clampAspect(payload.config.aspectRatio);

    skipNextSelectionResetRef.current = true;
    setLinkedTask(payload.record);
    setSelectedPromptIds(new Set(selectedCards.map((p) => p.id)));
    setImagesPerPrompt(n);
    setAspectRatio(ratio);

    void startGenerateWith({
      charaId: payload.record.charaId,
      prompts: selectedCards,
      n,
      aspectRatio: ratio,
      overrideCharaName: payload.record.charaName,
      overrideCharaAvatar: payload.record.charaAvatar,
    });
  }, [autoStartPayload, onConsumePayload, startGenerateWith]);

  useEffect(() => {
    const resume = chainedResume;
    if (!resume?.taskId?.trim()) return;
    const key = `chain|${resume.taskId.trim()}`;
    if (lastChainedResumeKeyRef.current === key) return;
    lastChainedResumeKeyRef.current = key;

    writeQuickCreateActiveTaskStorage({
      taskId: resume.taskId.trim(),
      charaId: resume.charaId.trim(),
      n: resume.n,
      aspectRatio: resume.aspectRatio,
      prompts: resume.prompts,
    });
    void pollQuickCreateTask(resume.taskId.trim(), resume.prompts);
    onConsumeChainedResume?.();
  }, [chainedResume, onConsumeChainedResume, pollQuickCreateTask, writeQuickCreateActiveTaskStorage]);

  const handleReset = useCallback(() => {
    setGenStatus("idle");
    setResultGroups([]);
    setViewingRecord(null);
    setGenError(null);
  }, []);

  const handleViewRecord = useCallback(
    async (record: QuickCreateRecord) => {
      try {
        const detail = await creationApi.getQuickCreateHistory(record.id);
        const next = toQuickCreateRecord(detail);
        upsertRecord(next);
        applyRecordToView(next);
      } catch (e) {
        if (e instanceof ApiError) setGenError(e.message);
      }
    },
    [applyRecordToView, toQuickCreateRecord, upsertRecord]
  );

  const handleDeleteRecord = useCallback(
    async (id: string) => {
      try {
        const result = await creationApi.deleteQuickCreateHistory(id);
        setHistoryRecords((prev) => prev.filter((r) => r.id !== id));
        if (result.latest) {
          const latest = toQuickCreateRecord(result.latest);
          upsertRecord(latest);
          applyRecordToView(latest);
        } else {
          setViewingRecord(null);
          setResultGroups([]);
          setGenStatus("idle");
          setGenError(null);
        }
      } catch (e) {
        if (e instanceof ApiError) setGenError(e.message);
      }
    },
    [applyRecordToView, toQuickCreateRecord, upsertRecord]
  );

  const openLightbox = useCallback((images: QuickCreateImage[], index: number) => {
    setLightbox({ images, index });
  }, []);

  const closeLightbox = useCallback(() => setLightbox(null), []);

  const handleViewComment = useCallback((img: QuickCreateImage, promptTitle: string) => {
    if (!img.aiComment) return;
    setViewingComment({
      comment: img.aiComment,
      imageUrl: img.url,
      promptTitle,
    });
  }, []);

  const closeComment = useCallback(() => setViewingComment(null), []);

  const prevImage = useCallback(() => {
    setLightbox((prev) =>
      prev
        ? { ...prev, index: (prev.index - 1 + prev.images.length) % prev.images.length }
        : null
    );
  }, []);

  const nextImage = useCallback(() => {
    setLightbox((prev) =>
      prev ? { ...prev, index: (prev.index + 1) % prev.images.length } : null
    );
  }, []);

  const displayGroups = viewingRecord ? viewingRecord.groups : resultGroups;
  const gridColsForGroup = (n: number) => Math.min(Math.max(n, 1), 4);

  const hasPrompts = allPrompts.length > 0;
  const submitDisabled =
    selectedPromptIds.size === 0 || genStatus === "generating" || !hasPrompts;

  return (
    <div className="flex h-full min-h-0 overflow-hidden">
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {genError && (
            <p className="text-xs text-rose-700 rounded-xl px-3 py-2 bg-rose-50/90 border border-rose-100">
              {genError}
            </p>
          )}

          <div
            className="rounded-2xl p-4"
            style={{
              background: "rgba(255,255,255,0.55)",
              border: "1px solid rgba(253,164,175,0.18)",
            }}
          >
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <div className="w-4 h-4 flex items-center justify-center">
                <i className="ri-magic-line text-rose-400 text-sm"></i>
              </div>
              <span
                className="text-sm font-semibold text-rose-700/80"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                挑一个灵感来源
              </span>
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: "rgba(253,164,175,0.12)", color: "#fb7185" }}
              >
                关联 Prompt 任务
              </span>
            </div>
            <LinkedTaskSelector
              charas={charas}
              historyItems={promptHistoryItems}
              listLoading={promptHistoryListLoading}
              value={linkedTask}
              pickingId={pickingHistoryId}
              onPick={(item) => void handlePickPromptHistoryItem(item)}
              onClear={() => handleLinkedTaskChange(null)}
            />
            {!linkedTask && (
              <p className="text-xs text-rose-400/40 mt-2 text-center">
                不选也没关系，默认使用最新一轮的 Prompt 任务～
              </p>
            )}
          </div>

          <div
            className="rounded-2xl p-4 flex items-center gap-4"
            style={{
              background:
                "linear-gradient(135deg, rgba(253,164,175,0.12) 0%, rgba(244,114,182,0.08) 100%)",
              border: "1px solid rgba(253,164,175,0.25)",
            }}
          >
            <div
              className="w-12 h-12 rounded-2xl overflow-hidden shrink-0"
              style={{ border: "2px solid rgba(244,114,182,0.3)" }}
            >
              <img
                src={displayAvatar}
                alt=""
                className="w-full h-full object-cover object-top"
                draggable={false}
              />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className="text-sm font-bold text-rose-700/80"
                  style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  {displayName}
                </span>
                {hasPrompts && (
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(253,164,175,0.2)", color: "#f472b6" }}
                  >
                    当前角色
                  </span>
                )}
              </div>
              <p className="text-xs text-rose-400/60 mt-0.5">
                {hasPrompts
                  ? linkedTask
                    ? `来自「${linkedTask.charaName}」的 Prompt 任务 · 本轮可用 ${allPrompts.length} 份 Prompt`
                    : hasLivePromptSession
                      ? `来自最新一轮的 Prompt 预生成任务 · 本轮可用 ${allPrompts.length} 份 Prompt`
                      : `来自最新一条已完成的 Prompt 预生成任务 · 本轮可用 ${allPrompts.length} 份 Prompt`
                  : linkedTask
                    ? "该关联任务暂无可用的 Prompt 卡片"
                    : "请先在「Prompt 预生成」中完成生成，再回来一键出图～"}
              </p>
            </div>
            <div
              className="w-8 h-8 flex items-center justify-center rounded-xl shrink-0"
              style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
            >
              <i className="ri-flashlight-line text-white text-sm"></i>
            </div>
          </div>

          <div
            className="rounded-2xl p-4"
            style={{
              background: "rgba(255,255,255,0.55)",
              border: "1px solid rgba(253,164,175,0.18)",
            }}
          >
            <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="w-4 h-4 flex items-center justify-center">
                  <i className="ri-list-check-2 text-rose-400 text-sm"></i>
                </div>
                <span
                  className="text-sm font-semibold text-rose-700/80"
                  style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  选择要生成的 Prompt
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
                >
                  已选 {selectedPromptIds.size} / {allPrompts.length}
                </span>
              </div>
              <button
                type="button"
                onClick={toggleAll}
                disabled={!hasPrompts}
                className="text-xs cursor-pointer transition-colors duration-200 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ color: "#f472b6" }}
              >
                {selectedPromptIds.size === allPrompts.length && hasPrompts ? "取消全选" : "全部选中"}
              </button>
            </div>

            {hasPrompts ? (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {allPrompts.map((card) => (
                  <PromptSelectCard
                    key={card.id}
                    card={card}
                    selected={selectedPromptIds.has(card.id)}
                    onToggle={() => togglePrompt(card.id)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-xs text-rose-300/70 text-center py-6">暂无承接的 Prompt 卡片</p>
            )}
          </div>

          <div
            className="rounded-2xl p-4"
            style={{
              background: "rgba(255,255,255,0.55)",
              border: "1px solid rgba(253,164,175,0.18)",
            }}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="w-4 h-4 flex items-center justify-center">
                <i className="ri-settings-3-line text-rose-400 text-sm"></i>
              </div>
              <span
                className="text-sm font-semibold text-rose-700/80"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                生成设置
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-4 flex-wrap">
                <span className="text-xs text-rose-500/70 whitespace-nowrap w-28 shrink-0">
                  每份 Prompt 生成几张图？
                </span>
                <div
                  className="flex items-center gap-1 p-1 rounded-2xl"
                  style={{
                    background: "rgba(253,164,175,0.1)",
                    border: "1px solid rgba(253,164,175,0.18)",
                  }}
                >
                  {IMAGES_PER_PROMPT_OPTIONS.map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setImagesPerPrompt(n)}
                      className="w-9 h-8 flex items-center justify-center rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                      style={{
                        fontFamily: "'ZCOOL KuaiLe', cursive",
                        background:
                          imagesPerPrompt === n
                            ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                            : "transparent",
                        color: imagesPerPrompt === n ? "white" : "#f472b6",
                        boxShadow:
                          imagesPerPrompt === n ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
                      }}
                    >
                      {n}
                    </button>
                  ))}
                </div>
                <span className="text-xs text-rose-400/50">
                  本次共生成约 {selectedPromptIds.size * imagesPerPrompt} 张图片
                </span>
              </div>

              <div className="flex items-center gap-4 flex-wrap">
                <span className="text-xs text-rose-500/70 whitespace-nowrap w-28 shrink-0">
                  图片长宽比
                </span>
                <div
                  className="flex items-center gap-1 p-1 rounded-2xl"
                  style={{
                    background: "rgba(253,164,175,0.1)",
                    border: "1px solid rgba(253,164,175,0.18)",
                  }}
                >
                  {ASPECT_RATIO_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setAspectRatio(option.value)}
                      className="px-3 h-8 flex items-center justify-center rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
                      style={{
                        fontFamily: "'ZCOOL KuaiLe', cursive",
                        background:
                          aspectRatio === option.value
                            ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                            : "transparent",
                        color: aspectRatio === option.value ? "white" : "#f472b6",
                        boxShadow:
                          aspectRatio === option.value
                            ? "0 2px 8px rgba(244,114,182,0.3)"
                            : "none",
                      }}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <span className="text-xs text-rose-400/50">当前选择：{aspectRatio}</span>
              </div>
            </div>
          </div>

          {genStatus !== "generating" && (
            <div className="flex items-center gap-3 flex-wrap">
              <button
                type="button"
                onClick={startGenerate}
                disabled={submitDisabled}
                className="flex items-center gap-2 px-6 py-2.5 rounded-2xl text-sm font-semibold text-white transition-all duration-200 whitespace-nowrap"
                style={{
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                  background: submitDisabled
                    ? "rgba(253,164,175,0.3)"
                    : "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                  boxShadow: submitDisabled ? "none" : "0 4px 16px rgba(244,114,182,0.35)",
                  cursor: submitDisabled ? "not-allowed" : "pointer",
                }}
              >
                <div className="w-4 h-4 flex items-center justify-center">
                  <i className="ri-flashlight-line text-sm"></i>
                </div>
                一键生成
              </button>

              {genStatus === "done" && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                  style={{
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    background: "rgba(253,164,175,0.12)",
                    color: "#f472b6",
                    border: "1px solid rgba(253,164,175,0.3)",
                  }}
                >
                  <div className="w-4 h-4 flex items-center justify-center">
                    <i className="ri-refresh-line text-sm"></i>
                  </div>
                  重新生成
                </button>
              )}
            </div>
          )}

          {genStatus === "generating" && (
            <div
              className="rounded-2xl p-8 flex flex-col items-center gap-4"
              style={{
                background: "rgba(255,255,255,0.55)",
                border: "1px solid rgba(253,164,175,0.18)",
              }}
            >
              <div className="relative w-16 h-16">
                <div
                  className="absolute inset-0 rounded-full"
                  style={{
                    border: "3px solid rgba(253,164,175,0.2)",
                    borderTopColor: "#f472b6",
                    animation: "qc-spin 1s linear infinite",
                  }}
                />
                <div className="absolute inset-0 flex items-center justify-center">
                  <i className="ri-image-ai-line text-rose-400 text-xl"></i>
                </div>
              </div>

              <p
                className="text-sm text-rose-500/80 text-center"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                {GEN_HINTS[hintIndex]}
              </p>

              <div className="flex items-center gap-1.5">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-rose-300 inline-block"
                    style={{
                      animation: "qc-bounce 1.2s ease-in-out infinite",
                      animationDelay: `${i * 0.2}s`,
                    }}
                  />
                ))}
              </div>
            </div>
          )}

          {genStatus === "done" && displayGroups.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="w-4 h-4 flex items-center justify-center">
                    <i className="ri-gallery-line text-rose-400 text-sm"></i>
                  </div>
                  <span
                    className="text-sm font-semibold text-rose-700/80"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    {viewingRecord ? "历史创作结果" : "生成结果"}
                  </span>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
                  >
                    {displayGroups.length} 组 · 共{" "}
                    {displayGroups.reduce((s, g) => s + g.images.length, 0)} 张
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleReset}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl cursor-pointer transition-all duration-200 whitespace-nowrap"
                  style={{
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    background: "rgba(253,164,175,0.12)",
                    color: "#f472b6",
                    border: "1px solid rgba(253,164,175,0.25)",
                  }}
                >
                  <i className="ri-refresh-line text-xs"></i>
                  重新生成
                </button>
              </div>

              {displayGroups.map((group) => (
                <ResultGroup
                  key={group.promptId}
                  group={group}
                  cols={gridColsForGroup(group.images.length)}
                  onImageClick={openLightbox}
                  onViewComment={handleViewComment}
                />
              ))}
            </div>
          )}

          {genStatus === "idle" && (
            <div
              className="rounded-2xl p-10 flex flex-col items-center text-center"
              style={{
                background: "rgba(255,255,255,0.4)",
                border: "1.5px dashed rgba(253,164,175,0.25)",
              }}
            >
              <div
                className="w-16 h-16 flex items-center justify-center rounded-3xl mb-4"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
                  border: "1.5px solid rgba(253,164,175,0.2)",
                }}
              >
                <i className="ri-image-ai-line text-rose-300 text-3xl"></i>
              </div>
              <p
                className="text-sm font-semibold text-rose-500/60 mb-1"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                {hasPrompts ? "选好 Prompt，点击「一键生成」" : "还没有可生成的 Prompt"}
              </p>
              <p className="text-xs text-rose-400/40 max-w-sm">
                {hasPrompts
                  ? "AI 会为每一份 Prompt 生成对应数量的美图，按组整齐排列～"
                  : "完成 Prompt 预生成后，将自动出现在上方列表中。"}
              </p>
            </div>
          )}
        </div>
      </div>

      <div
        className="shrink-0 flex flex-col border-l min-h-0 w-64"
        style={{
          borderColor: "rgba(253,164,175,0.18)",
          background: "rgba(255,255,255,0.3)",
        }}
      >
        <div
          className="px-4 py-3 shrink-0 border-b"
          style={{ borderColor: "rgba(253,164,175,0.15)" }}
        >
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 flex items-center justify-center">
              <i className="ri-history-line text-rose-400 text-sm"></i>
            </div>
            <span
              className="text-sm font-semibold text-rose-700/70"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              历史创作
            </span>
            {historyRecords.length > 0 && (
              <span
                className="text-xs px-1.5 py-0.5 rounded-full ml-auto"
                style={{ background: "rgba(253,164,175,0.2)", color: "#f472b6" }}
              >
                {historyRecords.length}
              </span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2 min-h-0">
          {historyRecords.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-center">
              <i className="ri-inbox-line text-rose-200 text-2xl mb-2"></i>
              <p className="text-xs text-rose-300/60">还没有历史记录哦～</p>
            </div>
          ) : (
            historyRecords.map((record) => (
              <HistoryItem
                key={record.id}
                record={record}
                active={viewingRecord?.id === record.id}
                onView={() => handleViewRecord(record)}
                onDelete={() => handleDeleteRecord(record.id)}
              />
            ))
          )}
        </div>

        <div
          className="px-4 py-3 shrink-0 border-t"
          style={{ borderColor: "rgba(253,164,175,0.15)" }}
        >
          <p className="text-xs text-rose-300/50 text-center leading-relaxed">
            点击记录可查看历史结果
          </p>
        </div>
      </div>

      {lightbox && (
        <Lightbox
          lightbox={lightbox}
          onClose={closeLightbox}
          onPrev={prevImage}
          onNext={nextImage}
        />
      )}

      {viewingComment && (
        <AiCommentModal
          comment={viewingComment.comment}
          imageUrl={viewingComment.imageUrl}
          promptTitle={viewingComment.promptTitle}
          onClose={closeComment}
        />
      )}

      <style>{`
        @keyframes qc-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes qc-bounce {
          0%, 100% { transform: translateY(0); opacity: 0.5; }
          50% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
