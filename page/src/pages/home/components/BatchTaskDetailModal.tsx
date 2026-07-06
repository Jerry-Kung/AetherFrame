import { useEffect, useRef, useState } from "react";
import DivergenceBadge from "@/pages/material/components/direction/DivergenceBadge";
import * as materialApi from "@/services/materialApi";
import type { CreativeDirectionApi } from "@/services/materialApi";
import type { BatchTask } from "@/types/batchAutomation";

interface BatchTaskDetailModalProps {
  task: BatchTask;
  onClose: () => void;
}

type DirectionState =
  | { kind: "none" }
  | { kind: "loading" }
  | { kind: "loaded"; direction: CreativeDirectionApi }
  | { kind: "deleted" }
  | { kind: "error" };

function CopyButton({ text, label = "复制" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, []);

  const handleCopy = () => {
    void navigator.clipboard.writeText(text);
    setCopied(true);
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="shrink-0 flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs cursor-pointer transition-all duration-200 whitespace-nowrap hover:opacity-80"
      style={{
        background: copied ? "rgba(110,231,183,0.15)" : "rgba(253,164,175,0.12)",
        border: copied ? "1px solid rgba(110,231,183,0.35)" : "1px solid rgba(253,164,175,0.25)",
        color: copied ? "#059669" : "#f472b6",
        fontFamily: "'ZCOOL KuaiLe', cursive",
      }}
      aria-label={label}
    >
      <i className={`${copied ? "ri-check-line" : "ri-file-copy-line"} text-xs`}></i>
      {copied ? "已复制" : label}
    </button>
  );
}

function SectionTitle({
  icon,
  text,
  copyText,
}: {
  icon: string;
  text: string;
  copyText?: string;
}) {
  return (
    <div className="flex items-center gap-1.5 mb-2">
      <i className={`${icon} text-rose-400 text-sm`}></i>
      <span className="text-sm font-bold text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
        {text}
      </span>
      {copyText ? (
        <span className="ml-auto">
          <CopyButton text={copyText} />
        </span>
      ) : null}
    </div>
  );
}

export default function BatchTaskDetailModal({ task, onClose }: BatchTaskDetailModalProps) {
  const [directionState, setDirectionState] = useState<DirectionState>(
    task.creativeDirectionId ? { kind: "loading" } : { kind: "none" }
  );

  useEffect(() => {
    const directionId = task.creativeDirectionId;
    if (!directionId || !task.charaId) {
      setDirectionState({ kind: "none" });
      return;
    }
    let cancelled = false;
    setDirectionState({ kind: "loading" });
    materialApi
      .listCreativeDirections(task.charaId)
      .then((list) => {
        if (cancelled) return;
        const found = list.find((d) => d.id === directionId);
        setDirectionState(found ? { kind: "loaded", direction: found } : { kind: "deleted" });
      })
      .catch(() => {
        if (!cancelled) setDirectionState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [task.creativeDirectionId, task.charaId]);

  const directionCopyText =
    directionState.kind === "loaded"
      ? [
          directionState.direction.title,
          directionState.direction.description,
          directionState.direction.initial_input ? `初始输入：${directionState.direction.initial_input}` : "",
        ]
          .filter(Boolean)
          .join("\n")
      : directionState.kind === "deleted" && task.creativeDirectionMeta
        ? task.creativeDirectionMeta.title
        : "";

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
        onClick={onClose}
      />
      <div
        className="relative w-full max-w-2xl mx-4 rounded-3xl overflow-hidden flex flex-col"
        style={{
          background: "rgba(255,255,255,0.97)",
          border: "1px solid rgba(253,164,175,0.3)",
          maxHeight: "82vh",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between px-5 py-4 shrink-0"
          style={{ borderBottom: "1px solid rgba(253,164,175,0.15)" }}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg overflow-hidden shrink-0 border border-rose-100">
              <img loading="lazy" src={task.charaAvatar} alt="" className="w-full h-full object-cover object-top" />
            </div>
            <h3
              className="text-base font-bold text-rose-600 truncate"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              {task.charaName} · 任务详情
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-xl cursor-pointer shrink-0 transition-all duration-200"
            style={{ background: "rgba(253,164,175,0.1)" }}
            aria-label="关闭"
          >
            <i className="ri-close-line text-rose-400"></i>
          </button>
        </div>

        <div className="px-5 py-4 space-y-4 overflow-y-auto">
          <div>
            <SectionTitle icon="ri-compass-3-line" text="创意方向" copyText={directionCopyText || undefined} />
            <div
              className="rounded-xl p-3"
              style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.12)" }}
            >
              {directionState.kind === "none" && (
                <p className="text-xs text-rose-400/60">
                  {task.seedPromptSection === "fixed" ? "固定模板任务，未关联创意方向" : "该任务未关联创意方向"}
                </p>
              )}
              {directionState.kind === "loading" && <p className="text-xs text-rose-400/60">加载中…</p>}
              {directionState.kind === "error" && (
                <p className="text-xs text-rose-400/60">创意方向详情加载失败，请稍后重试</p>
              )}
              {directionState.kind === "deleted" && (
                <>
                  {task.creativeDirectionMeta ? (
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <DivergenceBadge divergence={task.creativeDirectionMeta.divergence} compact />
                      <span
                        className="text-sm font-bold text-rose-600"
                        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                      >
                        {task.creativeDirectionMeta.title}
                      </span>
                    </div>
                  ) : null}
                  <p className="text-xs text-rose-400/60">该创意方向已删除，完整描述不可查看</p>
                </>
              )}
              {directionState.kind === "loaded" && (
                <>
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <DivergenceBadge divergence={directionState.direction.divergence} compact />
                    <span
                      className="text-sm font-bold text-rose-600"
                      style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                    >
                      {directionState.direction.title}
                    </span>
                  </div>
                  <p className="text-xs text-rose-600/70 leading-relaxed whitespace-pre-wrap break-words">
                    {directionState.direction.description}
                  </p>
                  {directionState.direction.initial_input ? (
                    <p className="text-xs text-rose-400/60 leading-relaxed mt-1.5">
                      初始输入：{directionState.direction.initial_input}
                    </p>
                  ) : null}
                </>
              )}
            </div>
          </div>

          <div>
            <SectionTitle icon="ri-seedling-line" text="种子提示词" copyText={task.seedPromptText || undefined} />
            <div
              className="rounded-xl p-3"
              style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.12)" }}
            >
              <p className="text-xs text-rose-600/70 leading-relaxed whitespace-pre-wrap break-words">
                {task.seedPromptText}
              </p>
            </div>
          </div>

          <div>
            <SectionTitle icon="ri-quill-pen-line" text={`预生成 Prompt（${task.promptCards.length} 份）`} />
            {task.promptCards.length === 0 ? (
              <div
                className="rounded-xl p-3"
                style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.12)" }}
              >
                <p className="text-xs text-rose-400/60">任务尚未完成或暂无预生成 Prompt</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {task.promptCards.map((card, i) => (
                  <div
                    key={card.id}
                    className="rounded-xl px-3 py-2.5"
                    style={{ background: "rgba(253,164,175,0.05)", border: "1px solid rgba(253,164,175,0.1)" }}
                  >
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span
                        className="w-5 h-5 flex items-center justify-center rounded-md text-white text-xs shrink-0"
                        style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
                      >
                        {i + 1}
                      </span>
                      <span
                        className="text-xs font-bold text-rose-600"
                        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                      >
                        {card.title}
                      </span>
                      <div className="flex items-center gap-1 flex-wrap ml-auto">
                        {card.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs px-1.5 py-0.5 rounded-full"
                            style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
                          >
                            #{tag}
                          </span>
                        ))}
                        <CopyButton text={card.fullPrompt || card.preview} />
                      </div>
                    </div>
                    <p className="text-xs text-rose-600/70 leading-relaxed whitespace-pre-wrap break-words">
                      {card.fullPrompt || card.preview}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
