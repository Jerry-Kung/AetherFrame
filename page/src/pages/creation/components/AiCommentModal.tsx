import { useEffect } from "react";
import type { AiComment } from "@/types/quickCreate";

interface AiCommentModalProps {
  comment: AiComment | null;
  imageUrl: string;
  promptTitle: string;
  onClose: () => void;
}

export default function AiCommentModal({
  comment,
  imageUrl,
  promptTitle,
  onClose,
}: AiCommentModalProps) {
  useEffect(() => {
    if (!comment) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [comment, onClose]);

  if (!comment) return null;

  const isGood = comment.overallRating === "good";

  const getScoreColor = (score: number) => {
    if (score >= 85) return { bg: "#fda4af", text: "#e11d48" };
    if (score >= 70) return { bg: "#fb923c", text: "#c2410c" };
    return { bg: "#94a3b8", text: "#64748b" };
  };
  const scoreColor = getScoreColor(comment.score);

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(6px)" }}
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative max-w-xl w-full mx-4 max-h-[90vh] overflow-y-auto rounded-3xl"
        style={{
          background: "rgba(255,255,255,0.98)",
          border: "1px solid rgba(253,164,175,0.3)",
          boxShadow: "0 20px 60px rgba(244,114,182,0.15)",
        }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-comment-modal-title"
      >
        <div
          className="flex items-center justify-between px-6 py-4 border-b"
          style={{ borderColor: "rgba(253,164,175,0.2)" }}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <div
              className="w-7 h-7 flex items-center justify-center rounded-xl text-white shrink-0"
              style={{
                background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              }}
            >
              <i className="ri-robot-2-line text-sm"></i>
            </div>
            <span
              id="ai-comment-modal-title"
              className="text-sm font-bold text-rose-700/80 shrink-0"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              AI 评论员
            </span>
            <span className="text-xs text-rose-400/50 truncate">{promptTitle}</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg cursor-pointer transition-colors duration-200 shrink-0"
            style={{ color: "#fda4af", background: "rgba(253,164,175,0.1)" }}
            aria-label="关闭"
          >
            <i className="ri-close-line text-sm"></i>
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div className="flex items-center gap-4">
            <div
              className="w-28 h-28 rounded-2xl overflow-hidden shrink-0"
              style={{ border: "1px solid rgba(253,164,175,0.2)" }}
            >
              <img
                src={imageUrl}
                alt=""
                className="w-full h-full object-cover object-top"
                draggable={false}
              />
            </div>
            <div className="flex-1 min-w-0 space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-rose-400/60">整体评价</span>
                <span
                  className="text-xs px-3 py-1 rounded-full font-semibold"
                  style={{
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    background: isGood
                      ? "linear-gradient(135deg, rgba(167,243,208,0.3) 0%, rgba(110,231,183,0.2) 100%)"
                      : "linear-gradient(135deg, rgba(254,240,138,0.3) 0%, rgba(253,224,71,0.2) 100%)",
                    color: isGood ? "#059669" : "#a16207",
                    border: isGood
                      ? "1px solid rgba(110,231,183,0.4)"
                      : "1px solid rgba(253,224,71,0.4)",
                  }}
                >
                  {isGood ? "挺不错" : "需修补"}
                </span>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs text-rose-400/60">打分</span>
                  <span
                    className="text-sm font-bold tabular-nums"
                    style={{ color: scoreColor.text, fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    {comment.score}
                    <span className="text-xs font-normal text-rose-400/60"> / 100</span>
                  </span>
                </div>
                <div
                  className="h-2 rounded-full overflow-hidden"
                  style={{ background: "rgba(253,164,175,0.12)" }}
                >
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${comment.score}%`,
                      background: `linear-gradient(90deg, ${scoreColor.bg} 0%, ${isGood ? "#f472b6" : "#fb923c"} 100%)`,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          <div
            className="rounded-2xl p-4"
            style={{
              background:
                "linear-gradient(135deg, rgba(253,164,175,0.08) 0%, rgba(244,114,182,0.04) 100%)",
              border: "1px solid rgba(253,164,175,0.2)",
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-4 h-4 flex items-center justify-center">
                <i className="ri-chat-quote-line text-rose-400 text-xs"></i>
              </div>
              <span
                className="text-xs font-bold text-rose-600"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                评论总结
              </span>
            </div>
            <p className="text-sm text-rose-700/80 leading-relaxed">{comment.summary}</p>
          </div>

          <div
            className="rounded-2xl overflow-hidden"
            style={{
              background: "rgba(255,255,255,0.8)",
              border: "1px solid rgba(253,164,175,0.2)",
            }}
          >
            <div
              className="flex items-center gap-2 px-4 py-3 border-b"
              style={{ borderColor: "rgba(253,164,175,0.15)" }}
            >
              <div className="w-4 h-4 flex items-center justify-center">
                <i className="ri-error-warning-line text-rose-400 text-xs"></i>
              </div>
              <span
                className="text-xs font-bold text-rose-600"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                问题点
              </span>
              <span
                className="text-xs px-1.5 py-0.5 rounded-full"
                style={{
                  background: "rgba(253,164,175,0.12)",
                  color: "#fb7185",
                }}
              >
                {comment.issues.length} 条
              </span>
            </div>
            <div className="p-3 space-y-2">
              {comment.issues.map((issue, idx) => (
                <div key={idx} className="flex items-start gap-2.5">
                  <div
                    className="w-5 h-5 flex items-center justify-center rounded-full shrink-0 mt-0.5"
                    style={{ background: "rgba(253,164,175,0.15)", color: "#fb7185" }}
                  >
                    <span
                      className="text-xs font-bold"
                      style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                    >
                      {idx + 1}
                    </span>
                  </div>
                  <p className="text-sm text-rose-700/75 leading-relaxed">{issue}</p>
                </div>
              ))}
            </div>
          </div>

          <div
            className="rounded-2xl overflow-hidden"
            style={{
              background: "rgba(255,255,255,0.8)",
              border: "1px solid rgba(253,164,175,0.2)",
            }}
          >
            <div
              className="flex items-center gap-2 px-4 py-3 border-b"
              style={{ borderColor: "rgba(253,164,175,0.15)" }}
            >
              <div className="w-4 h-4 flex items-center justify-center">
                <i className="ri-lightbulb-line text-rose-400 text-xs"></i>
              </div>
              <span
                className="text-xs font-bold text-rose-600"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                修补建议
              </span>
              <span
                className="text-xs px-1.5 py-0.5 rounded-full"
                style={{
                  background: "rgba(253,164,175,0.12)",
                  color: "#fb7185",
                }}
              >
                {comment.fixSuggestions.length} 条
              </span>
            </div>
            <div className="p-3 space-y-2">
              {comment.fixSuggestions.map((fix, idx) => (
                <div key={idx} className="flex items-start gap-2.5">
                  <div
                    className="w-5 h-5 flex items-center justify-center rounded-full shrink-0 mt-0.5"
                    style={{
                      background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                      color: "white",
                    }}
                  >
                    <i className="ri-check-line text-xs"></i>
                  </div>
                  <p className="text-sm text-rose-700/75 leading-relaxed">{fix}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
