import { useEffect, useCallback } from "react";

export type CuteConfirmIcon = "warning" | "delete" | "info";

export interface CuteConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  icon?: CuteConfirmIcon;
  confirmText?: string;
  cancelText?: string;
  /** 用于 aria-labelledby，多实例时需唯一 */
  titleId?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

const ICON_CONFIG: Record<
  CuteConfirmIcon,
  { icon: string; bg: string; confirmBg: string; shadow: string }
> = {
  warning: {
    icon: "ri-alert-line",
    bg: "from-amber-300 to-orange-400",
    confirmBg: "from-amber-400 to-orange-500",
    shadow: "rgba(251,191,36,0.35)",
  },
  delete: {
    icon: "ri-delete-bin-6-line",
    bg: "from-rose-400 to-pink-500",
    confirmBg: "from-rose-500 to-pink-600",
    shadow: "rgba(244,114,182,0.4)",
  },
  info: {
    icon: "ri-information-line",
    bg: "from-sky-300 to-blue-400",
    confirmBg: "from-sky-400 to-blue-500",
    shadow: "rgba(125,211,252,0.4)",
  },
};

const CuteConfirmModal = ({
  isOpen,
  title,
  message,
  icon = "warning",
  confirmText = "确认",
  cancelText = "取消",
  titleId = "cute-confirm-title",
  onConfirm,
  onCancel,
}: CuteConfirmModalProps) => {
  const config = ICON_CONFIG[icon];

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      }
    },
    [onCancel]
  );

  useEffect(() => {
    if (!isOpen) return;

    document.addEventListener("keydown", handleKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={onCancel}
    >
      <div className="absolute inset-0 bg-rose-900/20 backdrop-blur-sm" />

      <div
        className="relative w-full max-w-sm rounded-3xl border border-rose-100/70 shadow-2xl overflow-hidden"
        style={{
          background: "rgba(255,255,255,0.72)",
          WebkitBackdropFilter: "blur(16px)",
          backdropFilter: "blur(16px)",
          boxShadow:
            "0 25px 50px -12px rgba(244,114,182,0.22), 0 0 0 1px rgba(255,255,255,0.6) inset",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-0 left-5 right-5 h-1 rounded-b-full bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300" />

        <div className="absolute top-3 right-4 w-5 h-5 flex items-center justify-center text-rose-300/55 pointer-events-none">
          <i className="ri-star-fill text-sm animate-pulse" />
        </div>
        <div
          className="absolute bottom-3 left-4 w-4 h-4 flex items-center justify-center text-pink-300/45 pointer-events-none"
          style={{ animation: "cuteModalTwinkle 2.2s ease-in-out infinite" }}
        >
          <i className="ri-sparkling-fill text-xs" />
        </div>
        <div
          className="absolute top-10 left-5 w-3 h-3 flex items-center justify-center text-amber-200/50 pointer-events-none"
          style={{ animation: "cuteModalTwinkle 2.8s ease-in-out infinite 0.5s" }}
        >
          <i className="ri-star-fill text-[10px]" />
        </div>

        <div className="px-6 pt-8 pb-5">
          <div className="flex justify-center mb-4">
            <div
              className={`w-16 h-16 rounded-2xl flex items-center justify-center text-white text-2xl bg-gradient-to-br ${config.bg}`}
              style={{
                boxShadow: `0 8px 22px ${config.shadow}`,
              }}
            >
              <i className={config.icon} />
            </div>
          </div>

          <h3
            id={titleId}
            className="text-center text-lg font-semibold text-rose-700 mb-2"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            {title}
          </h3>

          <p className="text-center text-sm text-rose-500/75 leading-relaxed px-1 whitespace-pre-wrap">
            {message}
          </p>
        </div>

        <div className="px-6 pb-6 flex items-center gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium text-rose-500/80 bg-rose-50/90 border border-rose-100/70 hover:bg-rose-100/70 hover:text-rose-600 cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <span className="flex items-center justify-center gap-1">
              <i className="ri-close-line" />
              {cancelText}
            </span>
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`flex-1 py-2.5 rounded-xl text-sm font-medium text-white bg-gradient-to-r ${config.confirmBg} hover:opacity-92 active:scale-[0.98] cursor-pointer transition-all duration-200 whitespace-nowrap`}
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              boxShadow: `0 4px 16px ${config.shadow}`,
            }}
          >
            <span className="flex items-center justify-center gap-1">
              <i className="ri-check-line" />
              {confirmText}
            </span>
          </button>
        </div>
      </div>

      <style>{`
        @keyframes cuteModalTwinkle {
          0%, 100% { opacity: 0.35; transform: scale(1) rotate(0deg); }
          50% { opacity: 0.85; transform: scale(1.15) rotate(12deg); }
        }
      `}</style>
    </div>
  );
};

export default CuteConfirmModal;
