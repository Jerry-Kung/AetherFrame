import { useState } from "react";
import { downloadImageFromUrl } from "@/utils/repairDraftFromImageUrl";
import type { useBeautify } from "@/hooks/useBeautify";

type BeautifyHook = ReturnType<typeof useBeautify>;

interface BeautifyActionsProps {
  beautify: BeautifyHook;
  viewing: "original" | "beautified";
  onViewingChange: (v: "original" | "beautified") => void;
  beautifiedUrl: string | null | undefined;
  disabled?: boolean;
  onActionError?: (msg: string | null) => void;
}

const btnGhost: React.CSSProperties = {
  background: "rgba(255,255,255,0.12)",
  border: "1px solid rgba(255,255,255,0.2)",
  color: "rgba(255,255,255,0.9)",
};

const btnAccent: React.CSSProperties = {
  background: "linear-gradient(135deg, #a78bfa, #8b5cf6)",
  border: "1px solid rgba(167,139,250,0.45)",
  color: "#fff",
};

export default function BeautifyActions({
  beautify,
  viewing,
  onViewingChange,
  beautifiedUrl,
  disabled = false,
  onActionError,
}: BeautifyActionsProps) {
  const { state, start, del, retry, errorMessage, currentStep, busy } = beautify;
  const locked = disabled || busy;
  const [dlBusy, setDlBusy] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    onActionError?.(null);
    await fn();
  };

  if (state === "idle") {
    return (
      <button
        type="button"
        disabled={locked}
        onClick={() => void run(start)}
        className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50 disabled:pointer-events-none"
        style={btnAccent}
      >
        <span className="w-4 h-4 flex items-center justify-center" aria-hidden>
          <i className="ri-magic-line" />
        </span>
        美化
      </button>
    );
  }

  if (state === "running") {
    const stepLabel = currentStep ? `（${currentStep}）` : "";
    return (
      <button
        type="button"
        disabled
        className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium whitespace-nowrap opacity-70 cursor-default"
        style={btnAccent}
      >
        <span className="w-4 h-4 flex items-center justify-center animate-spin" aria-hidden>
          <i className="ri-loader-4-line" />
        </span>
        美化中…{stepLabel}
      </button>
    );
  }

  if (state === "failed") {
    return (
      <BeautifyFailedHint
        errorMessage={errorMessage}
        locked={locked}
        onRetry={() => void run(retry)}
      />
    );
  }

  if (state === "done" && beautifiedUrl) {
    return (
      <>
        <button
          type="button"
          disabled={locked}
          onClick={() => onViewingChange(viewing === "original" ? "beautified" : "original")}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50"
          style={btnGhost}
        >
          <span className="w-4 h-4 flex items-center justify-center" aria-hidden>
            <i className="ri-exchange-line" />
          </span>
          {viewing === "original" ? "查看美化" : "切换原图"}
        </button>
        <button
          type="button"
          disabled={locked || dlBusy}
          onClick={() =>
            void (async () => {
              onActionError?.(null);
              setDlBusy(true);
              try {
                await downloadImageFromUrl(beautifiedUrl);
              } catch (e) {
                onActionError?.(e instanceof Error ? e.message : "下载失败");
              } finally {
                setDlBusy(false);
              }
            })()
          }
          className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50"
          style={btnGhost}
        >
          <span className="w-4 h-4 flex items-center justify-center" aria-hidden>
            <i className="ri-download-2-line" />
          </span>
          {dlBusy ? "下载中…" : "下载美化"}
        </button>
        <button
          type="button"
          disabled={locked}
          onClick={() => {
            onViewingChange("original");
            void run(del);
          }}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50"
          style={{
            ...btnGhost,
            color: "rgba(251,113,133,0.95)",
            border: "1px solid rgba(251,113,133,0.35)",
          }}
        >
          <span className="w-4 h-4 flex items-center justify-center" aria-hidden>
            <i className="ri-delete-bin-line" />
          </span>
          删除美化
        </button>
      </>
    );
  }

  return null;
}

function BeautifyFailedHint({
  errorMessage,
  locked,
  onRetry,
}: {
  errorMessage: string | null;
  locked: boolean;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      <span className="text-xs text-rose-300 max-w-md text-center">
        美化失败：{errorMessage || "未知错误"}
      </span>
      <button
        type="button"
        disabled={locked}
        onClick={onRetry}
        className="px-4 py-2 rounded-full text-xs font-medium cursor-pointer disabled:opacity-50"
        style={btnAccent}
      >
        重试
      </button>
      </div>
  );
}
