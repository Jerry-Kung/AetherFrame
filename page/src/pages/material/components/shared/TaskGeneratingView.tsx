import type { ReactNode } from "react";

interface TaskGeneratingViewProps {
  icon: string;
  title: string;
  stepLabel?: string;
  hint?: string;
  errorMessage?: string | null;
  onBack?: () => void;
  onRetry?: () => void;
  children?: ReactNode;
}

export default function TaskGeneratingView({
  icon,
  title,
  stepLabel,
  hint,
  errorMessage,
  onBack,
  onRetry,
  children,
}: TaskGeneratingViewProps) {
  if (errorMessage) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-8 text-center max-w-md mx-auto">
        <div
          className="rounded-xl px-4 py-3 text-sm text-rose-600 border border-rose-100 bg-rose-50/90 mb-6 w-full"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          {errorMessage}
        </div>
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all hover:opacity-90"
              style={{
                fontFamily: "'ZCOOL KuaiLe', cursive",
                background: "rgba(253,164,175,0.12)",
                color: "#db2777",
                border: "1px solid rgba(244,114,182,0.28)",
              }}
            >
              <i className="ri-arrow-go-back-line" />
              返回
            </button>
          )}
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all hover:opacity-90 text-white"
              style={{
                fontFamily: "'ZCOOL KuaiLe', cursive",
                background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                boxShadow: "0 4px 14px rgba(244,114,182,0.3)",
              }}
            >
              <i className="ri-refresh-line" />
              重试
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
      <div className="relative mb-8">
        <div
          className="w-20 h-20 rounded-3xl flex items-center justify-center"
          style={{
            background:
              "linear-gradient(135deg, rgba(253,164,175,0.2) 0%, rgba(244,114,182,0.15) 100%)",
            border: "2px solid rgba(244,114,182,0.25)",
            animation: "pulse 1.5s ease-in-out infinite",
          }}
        >
          <i className={`${icon} text-rose-400 text-3xl`} />
        </div>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="absolute w-2.5 h-2.5 flex items-center justify-center text-pink-400"
            style={{
              top: "50%",
              left: "50%",
              animation: `tgv_orbit${i} 2s linear infinite`,
              animationDelay: `${i * 0.66}s`,
            }}
          >
            <i className="ri-star-fill text-xs" />
          </div>
        ))}
      </div>
      <h3
        className="text-base font-bold text-rose-600 mb-2"
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        {title}
      </h3>
      {stepLabel && (
        <p
          className="text-sm text-rose-500/80 leading-relaxed mb-1"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          {stepLabel}
        </p>
      )}
      {hint && <p className="text-xs text-rose-400/60 leading-relaxed">{hint}</p>}
      {children}
      <style>{`
        @keyframes tgv_orbit0 {
          0%   { transform: translate(-50%, -50%) rotate(0deg)   translateX(46px) rotate(0deg); }
          100% { transform: translate(-50%, -50%) rotate(360deg) translateX(46px) rotate(-360deg); }
        }
        @keyframes tgv_orbit1 {
          0%   { transform: translate(-50%, -50%) rotate(120deg) translateX(46px) rotate(-120deg); }
          100% { transform: translate(-50%, -50%) rotate(480deg) translateX(46px) rotate(-480deg); }
        }
        @keyframes tgv_orbit2 {
          0%   { transform: translate(-50%, -50%) rotate(240deg) translateX(46px) rotate(-240deg); }
          100% { transform: translate(-50%, -50%) rotate(600deg) translateX(46px) rotate(-600deg); }
        }
      `}</style>
    </div>
  );
}
