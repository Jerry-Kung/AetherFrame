import { useState, useEffect } from "react";
import { type ModeId, MODES } from "./ModeSwitch";

interface ContentAreaProps {
  activeMode: ModeId;
}

const emptyStateConfig: Record<ModeId, { emoji: string; hint: string }> = {
  material: {
    emoji: "✂️",
    hint: "支持裁剪、压缩、格式转换、批量导出等素材处理能力",
  },
  creation: {
    emoji: "🎨",
    hint: "基于 AI 的风格化绘图与美化创作功能即将上线",
  },
  repair: {
    emoji: "🖌️",
    hint: "智能去水印、背景抹除、画质修复一键搞定",
  },
};

const ContentArea = ({ activeMode }: ContentAreaProps) => {
  const [visible, setVisible] = useState(true);
  const [currentMode, setCurrentMode] = useState<ModeId>(activeMode);

  useEffect(() => {
    setVisible(false);
    const timer = setTimeout(() => {
      setCurrentMode(activeMode);
      setVisible(true);
    }, 160);
    return () => clearTimeout(timer);
  }, [activeMode]);

  const mode = MODES.find((m) => m.id === currentMode)!;
  const extra = emptyStateConfig[currentMode];

  return (
    <div
      className="h-full flex flex-col items-center justify-center px-8 py-12 transition-all duration-300"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(8px)",
      }}
    >
      {/* Central empty-state block */}
      <div className="flex flex-col items-center text-center max-w-md">
        {/* Big decorative icon */}
        <div
          className="w-24 h-24 flex items-center justify-center rounded-2xl mb-6"
          style={{
            background:
              "linear-gradient(135deg, rgba(251,113,133,0.1) 0%, rgba(244,114,182,0.07) 100%)",
            border: "1.5px solid rgba(251,113,133,0.15)",
          }}
        >
          <span className="text-rose-400" style={{ fontSize: 40 }}>
            <i className={mode.icon}></i>
          </span>
        </div>

        {/* Mode name badge */}
        <span
          className={`inline-flex items-center gap-1.5 px-4 py-1 rounded-full text-xs font-semibold mb-4 bg-gradient-to-r ${mode.activeGradient} text-white tracking-wide`}
        >
          <i className={`${mode.icon} text-xs`}></i>
          {mode.label}
        </span>

        {/* Coming soon title */}
        <h2 className="text-xl font-bold text-rose-900/60 mb-3">
          模块功能后续接入
        </h2>

        {/* Hint */}
        <p className="text-sm text-rose-400/50 leading-relaxed">{extra.hint}</p>

        {/* Emoji accent */}
        <div className="mt-10 text-3xl opacity-25 select-none">{extra.emoji}</div>

        {/* Divider */}
        <div className="mt-6 flex items-center gap-3">
          <span className="block w-10 h-px bg-rose-200/60"></span>
          <span className="text-xs text-rose-300/40 tracking-widest select-none">
            敬请期待
          </span>
          <span className="block w-10 h-px bg-rose-200/60"></span>
        </div>
      </div>

      {/* Bottom-right corner dot decoration */}
      <div className="absolute bottom-6 right-6 flex items-center gap-1.5 opacity-25 pointer-events-none">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-200 inline-block"></span>
        <span className="w-1 h-1 rounded-full bg-rose-100 inline-block"></span>
        <span className="w-1.5 h-1.5 rounded-full bg-pink-200 inline-block"></span>
      </div>
    </div>
  );
};

export default ContentArea;
