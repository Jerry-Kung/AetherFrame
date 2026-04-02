import { useEffect, useCallback } from "react";

interface ImagePreviewModalProps {
  images: string[];
  currentIndex: number;
  onClose: () => void;
  onIndexChange: (idx: number) => void;
  onDownload: (url: string, idx: number) => void;
  onContinueRepair: (url: string) => void;
}

const ImagePreviewModal = ({
  images,
  currentIndex,
  onClose,
  onIndexChange,
  onDownload,
  onContinueRepair,
}: ImagePreviewModalProps) => {
  const total = images.length;
  const url = images[currentIndex];

  /* ── Keyboard navigation ─── */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft" && currentIndex > 0) onIndexChange(currentIndex - 1);
      if (e.key === "ArrowRight" && currentIndex < total - 1) onIndexChange(currentIndex + 1);
    },
    [onClose, currentIndex, total, onIndexChange]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [handleKeyDown]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
    >
      {/* Modal card */}
      <div
        className="relative flex flex-col items-center"
        style={{ maxWidth: "min(90vw, 720px)", width: "100%" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Top bar ─── */}
        <div className="w-full flex items-center justify-between mb-3 px-1">
          {/* Index indicator */}
          <div className="flex items-center gap-1.5">
            {images.map((_, i) => (
              <button
                key={i}
                onClick={() => onIndexChange(i)}
                className={[
                  "rounded-full transition-all duration-200 cursor-pointer",
                  i === currentIndex
                    ? "w-5 h-2 bg-pink-400"
                    : "w-2 h-2 bg-white/30 hover:bg-white/50",
                ].join(" ")}
              />
            ))}
          </div>

          {/* Close */}
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-all cursor-pointer whitespace-nowrap"
          >
            <i className="ri-close-line text-lg"></i>
          </button>
        </div>

        {/* ── Image area ─── */}
        <div
          className="relative w-full rounded-2xl overflow-hidden"
          style={{
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.12)",
          }}
        >
          <img
            src={url}
            alt={`修补结果 ${currentIndex + 1}`}
            className="w-full object-contain"
            style={{ maxHeight: "65vh" }}
          />

          {/* Prev / Next arrows */}
          {currentIndex > 0 && (
            <button
              onClick={() => onIndexChange(currentIndex - 1)}
              className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/30 hover:bg-black/50 text-white transition-all cursor-pointer whitespace-nowrap"
            >
              <i className="ri-arrow-left-s-line text-xl"></i>
            </button>
          )}
          {currentIndex < total - 1 && (
            <button
              onClick={() => onIndexChange(currentIndex + 1)}
              className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/30 hover:bg-black/50 text-white transition-all cursor-pointer whitespace-nowrap"
            >
              <i className="ri-arrow-right-s-line text-xl"></i>
            </button>
          )}

          {/* Index label */}
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-black/30 text-white/80 text-xs whitespace-nowrap">
            {currentIndex + 1} / {total}
          </div>
        </div>

        {/* ── Action buttons ─── */}
        <div className="flex items-center gap-3 mt-4 w-full justify-center">
          {/* Download */}
          <button
            onClick={() => onDownload(url, currentIndex)}
            className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "rgba(255,255,255,0.12)",
              border: "1px solid rgba(255,255,255,0.2)",
              color: "rgba(255,255,255,0.85)",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.2)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.12)";
            }}
          >
            <span className="w-4 h-4 flex items-center justify-center">
              <i className="ri-download-2-line"></i>
            </span>
            下载图片
          </button>

          {/* Continue repair */}
          <button
            onClick={() => {
              onContinueRepair(url);
              onClose();
            }}
            className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "linear-gradient(135deg, #f472b6, #ec4899)",
              border: "1px solid rgba(244,114,182,0.4)",
              color: "#fff",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "linear-gradient(135deg, #ec4899, #db2777)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "linear-gradient(135deg, #f472b6, #ec4899)";
            }}
          >
            <span className="w-4 h-4 flex items-center justify-center">
              <i className="ri-eraser-line"></i>
            </span>
            继续修补
          </button>
        </div>

        {/* Hint */}
        <p className="mt-3 text-xs text-white/30 select-none">
          按 ← → 切换图片 · ESC 关闭
        </p>
      </div>
    </div>
  );
};

export default ImagePreviewModal;
