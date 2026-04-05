import { useState } from "react";
import ImagePreviewModal from "./ImagePreviewModal";

interface ResultDisplayProps {
  results: string[];
  outputCount: 1 | 2 | 4;
  isProcessing: boolean;
  onContinueRepair: (imageUrl: string) => void;
}

const ResultDisplay = ({ results, outputCount, isProcessing, onContinueRepair }: ResultDisplayProps) => {
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);

  const gridClass = "grid-cols-1";

  /* ── Download helper ─── */
  const handleDownload = (url: string, idx: number) => {
    const a = document.createElement("a");
    a.href = url;
    a.download = `repair-result-${idx + 1}.png`;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  /* ── Empty state ─── */
  if (!isProcessing && results.length === 0) {
    return (
      <div className="flex flex-col h-full items-center justify-center px-6 py-8 text-center">
        <div
          className="w-16 h-16 flex items-center justify-center rounded-2xl mb-4"
          style={{
            background: "linear-gradient(135deg, rgba(251,113,133,0.08) 0%, rgba(244,114,182,0.05) 100%)",
            border: "1.5px dashed rgba(251,113,133,0.2)",
          }}
        >
          <span className="text-rose-300/50 text-2xl">
            <i className="ri-image-2-line"></i>
          </span>
        </div>
        <p className="text-sm text-rose-400/50 font-medium mb-1">暂无修补结果</p>
        <p className="text-xs text-rose-300/40 leading-relaxed">
          上传图片并填写 Prompt<br />点击「开始修补」生成结果
        </p>
        <div className="flex gap-1.5 mt-6 opacity-30">
          {[...Array(3)].map((_, i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-rose-300 inline-block"
              style={{ animationDelay: `${i * 0.4}s` }}
            />
          ))}
        </div>
      </div>
    );
  }

  /* ── Processing state ─── */
  if (isProcessing) {
    return (
      <div className="flex flex-col h-full items-center justify-center px-6 py-8 text-center">
        <div className="relative w-16 h-16 flex items-center justify-center mb-4">
          <div
            className="absolute inset-0 rounded-full border-2 border-t-transparent animate-spin"
            style={{ borderColor: "rgba(244,114,182,0.5)", borderTopColor: "transparent" }}
          />
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ background: "linear-gradient(135deg, #fbcfe8, #fce7f3)" }}
          >
            <i className="ri-eraser-line text-rose-400 text-base"></i>
          </div>
        </div>
        <p
          className="text-sm text-rose-500/70 font-medium mb-1"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          正在修补中…
        </p>
        <p className="text-xs text-rose-300/50">AI 正在认真处理，请稍等 ✨</p>
        <div className={`mt-5 w-full grid ${gridClass} gap-2`}>
          {[...Array(outputCount)].map((_, i) => (
            <div
              key={i}
              className="rounded-xl aspect-square animate-pulse"
              style={{ background: "linear-gradient(135deg, #fce7f3 0%, #fdf2f8 100%)" }}
            />
          ))}
        </div>
      </div>
    );
  }

  /* ── Results grid ─── */
  return (
    <>
      <div className="flex flex-col h-full px-4 py-4">
        {/* Count badge */}
        <div className="flex items-center gap-2 mb-3 shrink-0">
          <span className="flex items-center gap-1 text-xs text-rose-400/70">
            <i className="ri-check-double-line text-rose-400"></i>
            已生成 {results.length} 张结果
          </span>
          <span className="text-xs text-rose-300/40">· 点击预览，双击放大查看细节</span>
        </div>

        {/* Image grid */}
        <div className={`grid ${gridClass} gap-2.5 flex-1 min-h-0 overflow-y-auto`}>
          {results.map((url, idx) => (
            <div
              key={idx}
              className="group relative rounded-2xl overflow-hidden border border-rose-100/60 cursor-pointer"
              style={{ aspectRatio: "1 / 1" }}
              onClick={() => setPreviewIndex(idx)}
            >
              <img
                src={url}
                alt={`修补结果 ${idx + 1}`}
                className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
              />

              {/* Hover overlay */}
              <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                {/* Quick download */}
                <button
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-white/90 text-rose-500 text-xs font-medium cursor-pointer hover:bg-white transition-all whitespace-nowrap"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDownload(url, idx);
                  }}
                >
                  <i className="ri-download-2-line text-xs"></i>
                  保存
                </button>
                {/* Continue repair */}
                <button
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-full text-white text-xs font-medium cursor-pointer transition-all whitespace-nowrap"
                  style={{ background: "linear-gradient(135deg, rgba(244,114,182,0.85), rgba(236,72,153,0.85))" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onContinueRepair(url);
                  }}
                >
                  <i className="ri-eraser-line text-xs"></i>
                  继续修补
                </button>
              </div>

              {/* Zoom hint icon */}
              <div className="absolute top-2 right-2 w-6 h-6 flex items-center justify-center rounded-full bg-black/20 text-white/70 opacity-0 group-hover:opacity-100 transition-opacity">
                <i className="ri-zoom-in-line text-xs"></i>
              </div>

              {/* Index badge */}
              <div
                className="absolute top-2 left-2 w-5 h-5 rounded-full flex items-center justify-center text-xs text-white font-medium"
                style={{ background: "rgba(244,114,182,0.7)" }}
              >
                {idx + 1}
              </div>
            </div>
          ))}

          {/* Fill placeholders */}
          {results.length < outputCount &&
            [...Array(outputCount - results.length)].map((_, i) => (
              <div
                key={`ph-${i}`}
                className="rounded-2xl border-2 border-dashed border-rose-100/60 flex items-center justify-center"
                style={{ aspectRatio: "1 / 1" }}
              >
                <i className="ri-image-2-line text-rose-200/60 text-xl"></i>
              </div>
            ))}
        </div>
      </div>

      {/* ── Preview modal ─── */}
      {previewIndex !== null && (
        <ImagePreviewModal
          images={results}
          currentIndex={previewIndex}
          onClose={() => setPreviewIndex(null)}
          onIndexChange={setPreviewIndex}
          onDownload={handleDownload}
          onContinueRepair={onContinueRepair}
        />
      )}
    </>
  );
};

export default ResultDisplay;
