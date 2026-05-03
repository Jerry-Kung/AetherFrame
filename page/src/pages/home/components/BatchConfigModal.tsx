import { useEffect, useState } from "react";
import type { BatchTaskConfig } from "@/types/batchAutomation";

const ASPECT_RATIO_OPTIONS = [
  { label: "16:9", value: "16:9" },
  { label: "4:3", value: "4:3" },
  { label: "1:1", value: "1:1" },
  { label: "3:4", value: "3:4" },
  { label: "9:16", value: "9:16" },
] as const;

const PROMPT_COUNT_OPTIONS = [1, 2, 3, 4] as const;
const IMAGES_PER_PROMPT_OPTIONS = [1, 2, 3, 4] as const;

interface BatchConfigModalProps {
  visible: boolean;
  initialConfig: BatchTaskConfig;
  onConfirm: (config: BatchTaskConfig) => void;
  onCancel: () => void;
}

export default function BatchConfigModal({
  visible,
  initialConfig,
  onConfirm,
  onCancel,
}: BatchConfigModalProps) {
  const [config, setConfig] = useState<BatchTaskConfig>(initialConfig);

  useEffect(() => {
    if (visible) setConfig(initialConfig);
  }, [visible, initialConfig]);

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(253,164,175,0.15)", backdropFilter: "blur(6px)" }}
        onClick={onCancel}
        aria-hidden
      />

      <div
        className="relative rounded-3xl px-8 py-7 w-[420px] max-w-[90vw] flex flex-col gap-5"
        style={{
          background: "linear-gradient(160deg, #fff8fa 0%, #fffaf5 100%)",
          border: "1.5px solid rgba(253,164,175,0.3)",
          boxShadow: "0 8px 32px rgba(244,114,182,0.12)",
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 flex items-center justify-center rounded-2xl shrink-0"
            style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
          >
            <i className="ri-settings-3-line text-white text-lg"></i>
          </div>
          <div>
            <h3
              className="text-base font-bold text-rose-700"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              任务配置
            </h3>
            <p className="text-xs text-rose-400/60 mt-0.5">设置每条批量任务的 Prompt 与出图参数</p>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div>
            <label
              className="block text-xs font-medium text-rose-500 mb-2"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              <i className="ri-stack-line mr-1"></i>Prompt 预生成数量
            </label>
            <div
              className="flex items-center gap-1 p-1 rounded-2xl"
              style={{
                background: "rgba(253,164,175,0.1)",
                border: "1px solid rgba(253,164,175,0.18)",
              }}
            >
              {PROMPT_COUNT_OPTIONS.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setConfig((c) => ({ ...c, promptCount: n }))}
                  className="flex-1 h-8 flex items-center justify-center rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                  style={{
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    background:
                      config.promptCount === n
                        ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                        : "transparent",
                    color: config.promptCount === n ? "white" : "#f472b6",
                    boxShadow:
                      config.promptCount === n ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
                  }}
                >
                  {n} 个
                </button>
              ))}
            </div>
          </div>

          <div>
            <label
              className="block text-xs font-medium text-rose-500 mb-2"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              <i className="ri-image-line mr-1"></i>每个 Prompt 生成图片数
            </label>
            <div
              className="flex items-center gap-1 p-1 rounded-2xl"
              style={{
                background: "rgba(253,164,175,0.1)",
                border: "1px solid rgba(253,164,175,0.18)",
              }}
            >
              {IMAGES_PER_PROMPT_OPTIONS.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setConfig((c) => ({ ...c, imagesPerPrompt: n }))}
                  className="flex-1 h-8 flex items-center justify-center rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                  style={{
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    background:
                      config.imagesPerPrompt === n
                        ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                        : "transparent",
                    color: config.imagesPerPrompt === n ? "white" : "#f472b6",
                    boxShadow:
                      config.imagesPerPrompt === n ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
                  }}
                >
                  {n} 张
                </button>
              ))}
            </div>
          </div>

          <div>
            <label
              className="block text-xs font-medium text-rose-500 mb-2"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              <i className="ri-aspect-ratio-line mr-1"></i>图片长宽比
            </label>
            <div
              className="flex flex-wrap items-center gap-1 p-1 rounded-2xl"
              style={{
                background: "rgba(253,164,175,0.1)",
                border: "1px solid rgba(253,164,175,0.18)",
              }}
            >
              {ASPECT_RATIO_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setConfig((c) => ({ ...c, aspectRatio: opt.value }))}
                  className="flex-1 min-w-[3.5rem] h-8 flex items-center justify-center rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                  style={{
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    background:
                      config.aspectRatio === opt.value
                        ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                        : "transparent",
                    color: config.aspectRatio === opt.value ? "white" : "#f472b6",
                    boxShadow:
                      config.aspectRatio === opt.value ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 py-2 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "rgba(253,164,175,0.1)",
              border: "1px solid rgba(253,164,175,0.25)",
              color: "#f472b6",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            取消
          </button>
          <button
            type="button"
            onClick={() => onConfirm(config)}
            className="flex-1 py-2 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              color: "white",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            确认
          </button>
        </div>
      </div>
    </div>
  );
}
