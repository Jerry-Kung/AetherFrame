import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { QuickCreateImage } from "@/types/quickCreate";
import {
  OPEN_REPAIR_TASK_SESSION_KEY,
  createRepairDraftFromImageUrl,
  downloadImageFromUrl,
} from "@/utils/repairDraftFromImageUrl";

export interface CreationResultLightboxProps {
  images: QuickCreateImage[];
  index: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}

export default function CreationResultLightbox({
  images,
  index,
  onClose,
  onPrev,
  onNext,
}: CreationResultLightboxProps) {
  const navigate = useNavigate();
  const img = images[index];
  const total = images.length;

  const [downloadBusy, setDownloadBusy] = useState(false);
  const [repairBusy, setRepairBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setActionError(null);
  }, [index]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") onPrev();
      if (e.key === "ArrowRight") onNext();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, onPrev, onNext]);

  const handleDownload = useCallback(async () => {
    if (!img?.url || downloadBusy || repairBusy) return;
    setActionError(null);
    setDownloadBusy(true);
    try {
      await downloadImageFromUrl(img.url);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "下载失败";
      setActionError(msg);
    } finally {
      setDownloadBusy(false);
    }
  }, [img?.url, downloadBusy, repairBusy]);

  const handleRepair = useCallback(async () => {
    if (!img?.url || downloadBusy || repairBusy) return;
    setActionError(null);
    setRepairBusy(true);
    try {
      const taskId = await createRepairDraftFromImageUrl(img.url);
      try {
        sessionStorage.setItem(OPEN_REPAIR_TASK_SESSION_KEY, taskId);
      } catch {
        // ignore quota / private mode
      }
      onClose();
      navigate("/repair", { state: { openRepairTaskId: taskId } });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "创建修补任务失败";
      setActionError(msg);
    } finally {
      setRepairBusy(false);
    }
  }, [img?.url, downloadBusy, repairBusy, navigate, onClose]);

  if (!img) return null;

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
                {index + 1} / {total}
              </div>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3 w-full">
          <button
            type="button"
            onClick={() => void handleDownload()}
            disabled={downloadBusy || repairBusy}
            className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50 disabled:pointer-events-none"
            style={{
              background: "rgba(255,255,255,0.12)",
              border: "1px solid rgba(255,255,255,0.2)",
              color: "rgba(255,255,255,0.9)",
            }}
          >
            <span className="w-4 h-4 flex items-center justify-center" aria-hidden>
              <i className="ri-download-2-line" />
            </span>
            {downloadBusy ? "下载中…" : "下载"}
          </button>
          <button
            type="button"
            onClick={() => void handleRepair()}
            disabled={downloadBusy || repairBusy}
            className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50 disabled:pointer-events-none"
            style={{
              background: "linear-gradient(135deg, #f472b6, #ec4899)",
              border: "1px solid rgba(244,114,182,0.4)",
              color: "#fff",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            <span className="w-4 h-4 flex items-center justify-center" aria-hidden>
              <i className="ri-eraser-line" />
            </span>
            {repairBusy ? "准备中…" : "修补"}
          </button>
        </div>

        {actionError ? (
          <p className="text-xs text-rose-300 text-center max-w-md px-2">{actionError}</p>
        ) : null}

        <p className="text-xs text-white/70 text-center">
          键盘 <kbd className="px-1 py-0.5 rounded bg-white/10">←</kbd>{" "}
          <kbd className="px-1 py-0.5 rounded bg-white/10">→</kbd> 切换 ·{" "}
          <kbd className="px-1 py-0.5 rounded bg-white/10">Esc</kbd> 关闭
        </p>
      </div>
    </div>
  );
}
