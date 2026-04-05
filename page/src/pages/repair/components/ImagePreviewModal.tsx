import { useEffect, useCallback, useRef, useState } from "react";

const MIN_SCALE = 1;
const MAX_SCALE = 4;
const ZOOM_STEP = 0.25;
const WHEEL_FACTOR_DOWN = 0.92;
const WHEEL_FACTOR_UP = 1.08;
const DBL_CLICK_ZOOM = 1.5;

interface ImagePreviewModalProps {
  images: string[];
  currentIndex: number;
  onClose: () => void;
  onIndexChange: (idx: number) => void;
  onDownload: (url: string, idx: number) => void;
  showContinueRepair?: boolean;
  onContinueRepair?: (url: string) => void;
  imageAltPrefix?: string;
}

type ViewTransform = { scale: number; tx: number; ty: number };

function clampScale(s: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));
}

function zoomToPoint(
  cx: number,
  cy: number,
  prev: ViewTransform,
  nextScale: number
): ViewTransform {
  const oldS = prev.scale;
  const ns = clampScale(nextScale);
  if (Math.abs(ns - oldS) < 1e-9) return { ...prev, scale: ns };
  return {
    scale: ns,
    tx: cx - ((cx - prev.tx) * ns) / oldS,
    ty: cy - ((cy - prev.ty) * ns) / oldS,
  };
}

const ImagePreviewModal = ({
  images,
  currentIndex,
  onClose,
  onIndexChange,
  onDownload,
  showContinueRepair = true,
  onContinueRepair,
  imageAltPrefix = "修补结果",
}: ImagePreviewModalProps) => {
  const total = images.length;
  const url = images[currentIndex];

  const viewportRef = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState<ViewTransform>({ scale: 1, tx: 0, ty: 0 });
  const [isPanning, setIsPanning] = useState(false);

  const { scale, tx, ty } = transform;
  const isZoomed = scale > 1 + 1e-6;

  useEffect(() => {
    setTransform({ scale: 1, tx: 0, ty: 0 });
  }, [currentIndex]);

  const applyZoomAt = useCallback((cx: number, cy: number, nextScale: number) => {
    setTransform((prev) => zoomToPoint(cx, cy, prev, nextScale));
  }, []);

  const resetView = useCallback(() => {
    setTransform({ scale: 1, tx: 0, ty: 0 });
  }, []);

  const zoomFromWheel = useCallback((e: WheelEvent) => {
    const el = viewportRef.current;
    if (!el) return;
    e.preventDefault();
    const rect = el.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const factor = e.deltaY > 0 ? WHEEL_FACTOR_DOWN : WHEEL_FACTOR_UP;
    setTransform((prev) => zoomToPoint(cx, cy, prev, prev.scale * factor));
  }, []);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    el.addEventListener("wheel", zoomFromWheel, { passive: false });
    return () => el.removeEventListener("wheel", zoomFromWheel);
  }, [zoomFromWheel, url]);

  const handleBackdropClick = useCallback(() => {
    if (!isZoomed) onClose();
  }, [isZoomed, onClose]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (isZoomed) {
          e.preventDefault();
          resetView();
        } else {
          onClose();
        }
        return;
      }
      if (isZoomed) return;
      if (e.key === "ArrowLeft" && currentIndex > 0) onIndexChange(currentIndex - 1);
      if (e.key === "ArrowRight" && currentIndex < total - 1) onIndexChange(currentIndex + 1);
    },
    [isZoomed, resetView, onClose, currentIndex, total, onIndexChange]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [handleKeyDown]);

  const centerZoomPoint = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return { cx: 0, cy: 0 };
    const r = el.getBoundingClientRect();
    return { cx: r.width / 2, cy: r.height / 2 };
  }, []);

  const zoomOutStep = () => {
    const { cx, cy } = centerZoomPoint();
    applyZoomAt(cx, cy, scale - ZOOM_STEP);
  };

  const zoomInStep = () => {
    const { cx, cy } = centerZoomPoint();
    applyZoomAt(cx, cy, scale + ZOOM_STEP);
  };

  const handleDoubleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = viewportRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    if (scale > 1 + 1e-6) {
      resetView();
    } else {
      applyZoomAt(cx, cy, DBL_CLICK_ZOOM);
    }
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isZoomed || e.button !== 0) return;
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startTx = tx;
    const startTy = ty;
    setIsPanning(true);

    const move = (ev: MouseEvent) => {
      setTransform((prev) => ({
        ...prev,
        tx: startTx + ev.clientX - startX,
        ty: startTy + ev.clientY - startY,
      }));
    };
    const up = () => {
      setIsPanning(false);
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const percentLabel = `${Math.round(scale * 100)}%`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(8px)" }}
      onClick={handleBackdropClick}
    >
      {/* Modal card */}
      <div
        className="relative flex flex-col items-center"
        style={{ maxWidth: "min(90vw, 960px)", width: "100%" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Top bar ─── */}
        <div className="w-full flex items-center justify-between mb-3 px-1 gap-2">
          {/* Index indicator */}
          <div
            className={[
              "flex items-center gap-1.5 shrink-0",
              isZoomed ? "pointer-events-none opacity-40" : "",
            ].join(" ")}
          >
            {images.map((_, i) => (
              <button
                key={i}
                type="button"
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

          {/* Zoom controls */}
          <div className="flex items-center gap-1.5 flex-1 justify-center min-w-0">
            <button
              type="button"
              onClick={zoomOutStep}
              disabled={scale <= MIN_SCALE + 1e-9}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white/90 disabled:opacity-30 disabled:pointer-events-none transition-all cursor-pointer"
              aria-label="缩小"
            >
              <i className="ri-subtract-line text-lg" />
            </button>
            <button
              type="button"
              onClick={resetView}
              className="min-w-[3.25rem] px-2 py-1 rounded-full bg-white/10 hover:bg-white/20 text-white/90 text-xs font-medium tabular-nums transition-all cursor-pointer"
            >
              {percentLabel}
            </button>
            <button
              type="button"
              onClick={zoomInStep}
              disabled={scale >= MAX_SCALE - 1e-9}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white/90 disabled:opacity-30 disabled:pointer-events-none transition-all cursor-pointer"
              aria-label="放大"
            >
              <i className="ri-add-line text-lg" />
            </button>
          </div>

          {/* Close */}
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 shrink-0 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-all cursor-pointer whitespace-nowrap"
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
          <div
            ref={viewportRef}
            role="presentation"
            className="relative w-full select-none touch-none"
            style={{
              cursor: isZoomed ? (isPanning ? "grabbing" : "grab") : "default",
              maxHeight: "75vh",
            }}
            onDoubleClick={handleDoubleClick}
            onMouseDown={handleMouseDown}
          >
            <div
              style={{
                transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
                transformOrigin: "0 0",
                willChange: "transform",
              }}
            >
              <img
                src={url}
                alt={`${imageAltPrefix} ${currentIndex + 1}`}
                draggable={false}
                className="w-full object-contain pointer-events-none block"
                style={{ maxHeight: "75vh" }}
              />
            </div>
          </div>

          {/* Prev / Next arrows */}
          {currentIndex > 0 && (
            <button
              type="button"
              onClick={() => !isZoomed && onIndexChange(currentIndex - 1)}
              tabIndex={isZoomed ? -1 : 0}
              className={[
                "absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/30 hover:bg-black/50 text-white transition-all whitespace-nowrap",
                isZoomed ? "opacity-30 pointer-events-none cursor-default" : "cursor-pointer",
              ].join(" ")}
            >
              <i className="ri-arrow-left-s-line text-xl"></i>
            </button>
          )}
          {currentIndex < total - 1 && (
            <button
              type="button"
              onClick={() => !isZoomed && onIndexChange(currentIndex + 1)}
              tabIndex={isZoomed ? -1 : 0}
              className={[
                "absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-black/30 hover:bg-black/50 text-white transition-all whitespace-nowrap",
                isZoomed ? "opacity-30 pointer-events-none cursor-default" : "cursor-pointer",
              ].join(" ")}
            >
              <i className="ri-arrow-right-s-line text-xl"></i>
            </button>
          )}

          {/* Index label */}
          <div
            className={[
              "absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-black/30 text-white/80 text-xs whitespace-nowrap",
              isZoomed ? "opacity-40 pointer-events-none" : "",
            ].join(" ")}
          >
            {currentIndex + 1} / {total}
          </div>
        </div>

        {/* ── Action buttons ─── */}
        <div className="flex items-center gap-3 mt-4 w-full justify-center">
          {/* Download */}
          <button
            type="button"
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

          {showContinueRepair && onContinueRepair ? (
            <button
              type="button"
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
          ) : null}
        </div>

        {/* Hint */}
        <p className="mt-3 text-xs text-white/30 select-none text-center px-2">
          {isZoomed
            ? "滚轮缩放 · 拖拽平移细节 · ESC 先退出缩放"
            : total > 1
              ? "按 ← → 切换图片 · ESC 关闭 · 双击图片放大细节"
              : "ESC 关闭 · 双击图片放大细节"}
        </p>
      </div>
    </div>
  );
};

export default ImagePreviewModal;
