import { useState } from "react";
import type { BatchTask } from "@/types/batchAutomation";

interface BatchTaskCardProps {
  task: BatchTask;
  index: number;
  onDelete: (taskId: string) => void | Promise<void>;
  onMarkUsed: (taskId: string) => void | Promise<void>;
}

function seedPreview(text: string): string {
  if (text.length <= 36) return text;
  return `${text.slice(0, 36)}…`;
}

export default function BatchTaskCard({ task, index, onDelete, onMarkUsed }: BatchTaskCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [hoveredImg, setHoveredImg] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showUsedConfirm, setShowUsedConfirm] = useState(false);

  const totalImages = task.images.length;

  return (
    <div
      className="rounded-2xl overflow-hidden transition-all duration-300"
      style={{
        background: "rgba(255,255,255,0.7)",
        border: "1px solid rgba(253,164,175,0.2)",
      }}
    >
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer"
        style={{ borderBottom: expanded ? "1px solid rgba(253,164,175,0.15)" : "none" }}
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div
            className="w-7 h-7 flex items-center justify-center rounded-xl text-xs font-bold text-white shrink-0"
            style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
          >
            {index + 1}
          </div>
          <div className="w-8 h-8 rounded-lg overflow-hidden shrink-0 border border-rose-100">
            <img src={task.charaAvatar} alt="" className="w-full h-full object-cover object-top" />
          </div>
          <div className="min-w-0">
            <p
              className="text-sm font-bold text-rose-700/80 truncate"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              {task.charaName}
            </p>
            <p className="text-xs text-rose-400/50 truncate">{seedPreview(task.seedPromptText)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {task.itemStatus === "failed" && (
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: "rgba(251,113,133,0.15)", color: "#e11d48" }}
            >
              失败
            </span>
          )}
          {task.itemStatus === "running" || task.itemStatus === "pending" ? (
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: "rgba(253,224,71,0.2)", color: "#a16207" }}
            >
              {task.itemStatus === "pending" ? "排队" : "进行中"}
            </span>
          ) : null}
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{ background: "rgba(253,164,175,0.15)", color: "#f472b6" }}
          >
            {totalImages} 张
          </span>
          <div className="w-5 h-5 flex items-center justify-center">
            <i
              className="ri-arrow-down-s-line text-rose-400 text-sm transition-transform duration-200"
              style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}
            ></i>
          </div>
        </div>
      </div>

      {!expanded && (
        <div className="px-4 pb-3 pt-1">
          <div className="flex items-center gap-2">
            {task.images.slice(0, 3).map((img) => (
              <div
                key={img.id}
                className="w-16 h-16 rounded-xl overflow-hidden shrink-0"
                style={{ border: "1px solid rgba(253,164,175,0.2)" }}
              >
                <img src={img.url} alt="" className="w-full h-full object-cover object-top" />
              </div>
            ))}
            {totalImages > 3 && (
              <div
                className="w-16 h-16 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: "rgba(253,164,175,0.08)", border: "1px dashed rgba(253,164,175,0.3)" }}
              >
                <span className="text-xs text-rose-400/60">+{totalImages - 3}</span>
              </div>
            )}
            <span className="text-xs text-rose-300/60 ml-auto shrink-0">{task.createdAt}</span>
          </div>
        </div>
      )}

      {expanded && (
        <div className="px-4 pb-4 pt-2 space-y-3">
          {task.errorMessage && (
            <div
              className="rounded-xl p-3 text-xs text-rose-700"
              style={{ background: "rgba(251,113,133,0.08)", border: "1px solid rgba(251,113,133,0.25)" }}
            >
              {task.errorMessage}
            </div>
          )}
          <div
            className="rounded-xl p-3"
            style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.12)" }}
          >
            <div className="flex items-center gap-1.5 mb-1.5">
              <i className="ri-seedling-line text-rose-400 text-xs"></i>
              <span className="text-xs font-medium text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                种子提示词
              </span>
            </div>
            <p className="text-xs text-rose-600/70 leading-relaxed">{task.seedPromptText}</p>
          </div>

          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <i className="ri-quill-pen-line text-rose-400 text-xs"></i>
              <span className="text-xs font-medium text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                预生成 Prompt
              </span>
              <span className="text-xs text-rose-300/60 ml-1">{task.promptCards.length} 份</span>
            </div>
            <div className="flex flex-col gap-1.5">
              {task.promptCards.map((card, i) => (
                <div
                  key={card.id}
                  className="rounded-xl px-3 py-2"
                  style={{ background: "rgba(253,164,175,0.05)", border: "1px solid rgba(253,164,175,0.1)" }}
                >
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span
                      className="w-5 h-5 flex items-center justify-center rounded-md text-white text-xs shrink-0"
                      style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
                    >
                      {i + 1}
                    </span>
                    <span className="text-xs font-bold text-rose-600" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
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
                    </div>
                  </div>
                  <p className="text-xs text-rose-400/60 leading-relaxed truncate ml-7">{card.preview}</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <i className="ri-gallery-line text-rose-400 text-xs"></i>
              <span className="text-xs font-medium text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                创作结果
              </span>
              <span className="text-xs text-rose-300/60">{totalImages} 张</span>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {task.images.map((img) => (
                <div
                  key={img.id}
                  className="relative rounded-xl overflow-hidden cursor-pointer"
                  style={{ border: "1px solid rgba(253,164,175,0.2)", aspectRatio: "1" }}
                  onMouseEnter={() => setHoveredImg(img.id)}
                  onMouseLeave={() => setHoveredImg(null)}
                >
                  <img src={img.url} alt="" className="w-full h-full object-cover object-top" />
                  {hoveredImg === img.id && (
                    <div className="absolute inset-0 bg-rose-900/20 flex items-center justify-center">
                      <div className="w-7 h-7 flex items-center justify-center rounded-full bg-white/80">
                        <i className="ri-zoom-in-line text-rose-500 text-xs"></i>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => setShowUsedConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
              style={{
                background: "rgba(110,231,183,0.1)",
                border: "1px solid rgba(110,231,183,0.3)",
                color: "#059669",
                fontFamily: "'ZCOOL KuaiLe', cursive",
              }}
            >
              <i className="ri-check-double-line text-xs"></i>
              标记种子为已使用
            </button>
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="ml-auto flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
              style={{
                background: "rgba(253,164,175,0.08)",
                border: "1px solid rgba(253,164,175,0.2)",
                color: "#fb7185",
                fontFamily: "'ZCOOL KuaiLe', cursive",
              }}
            >
              <i className="ri-delete-bin-line text-xs"></i>
              删除任务
            </button>
          </div>
        </div>
      )}

      {showDeleteConfirm && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center">
          <div
            className="absolute inset-0"
            style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
            onClick={() => setShowDeleteConfirm(false)}
          />
          <div
            className="relative w-80 rounded-3xl overflow-hidden mx-4"
            style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex flex-col items-center pt-7 pb-4 px-6">
              <div
                className="w-14 h-14 flex items-center justify-center rounded-2xl mb-4"
                style={{
                  background: "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
                  border: "1.5px solid rgba(244,114,182,0.2)",
                }}
              >
                <i className="ri-delete-bin-2-line text-rose-400 text-2xl"></i>
              </div>
              <h3 className="text-base font-bold text-rose-600 mb-1.5" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                删除这条创作任务？
              </h3>
              <p className="text-sm text-rose-400/70 text-center leading-relaxed">
                这会同步删除对应的 Prompt 预生成记录和美图创作记录，不可恢复哦～
              </p>
            </div>
            <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />
            <div className="flex gap-3 p-4">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 py-2.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                style={{
                  background: "rgba(253,164,175,0.08)",
                  color: "#f472b6",
                  border: "1px solid rgba(244,114,182,0.2)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                再想想
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  void onDelete(task.id);
                }}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white"
                style={{
                  background: "linear-gradient(135deg, #fb7185 0%, #f472b6 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {showUsedConfirm && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center">
          <div
            className="absolute inset-0"
            style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
            onClick={() => setShowUsedConfirm(false)}
          />
          <div
            className="relative w-80 rounded-3xl overflow-hidden mx-4"
            style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex flex-col items-center pt-7 pb-4 px-6">
              <div
                className="w-14 h-14 flex items-center justify-center rounded-2xl mb-4"
                style={{
                  background: "linear-gradient(135deg, rgba(110,231,183,0.15) 0%, rgba(52,211,153,0.1) 100%)",
                  border: "1.5px solid rgba(110,231,183,0.25)",
                }}
              >
                <i className="ri-check-double-line text-emerald-500 text-2xl"></i>
              </div>
              <h3 className="text-base font-bold text-rose-600 mb-1.5" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                标记种子为已使用？
              </h3>
              <p className="text-xs text-rose-400/70 text-center leading-relaxed break-all mb-1">「{task.seedPromptText}」</p>
              <p className="text-sm text-rose-400/70 text-center leading-relaxed">
                该种子提示词在素材加工模块中会被标记为「已使用」状态，后续批量创作时不再自动选中～
              </p>
            </div>
            <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />
            <div className="flex gap-3 p-4">
              <button
                type="button"
                onClick={() => setShowUsedConfirm(false)}
                className="flex-1 py-2.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                style={{
                  background: "rgba(253,164,175,0.08)",
                  color: "#f472b6",
                  border: "1px solid rgba(244,114,182,0.2)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                再想想
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowUsedConfirm(false);
                  void onMarkUsed(task.id);
                }}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white"
                style={{
                  background: "linear-gradient(135deg, #6ee7b7 0%, #34d399 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                确认标记
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
