import { useState } from "react";

type ArtSubTab = "quick" | "fine";

interface ArtSubTabConfig {
  id: ArtSubTab;
  label: string;
  icon: string;
  desc: string;
  comingSoon: string;
  color: string;
  gradient: string;
}

const ART_SUB_TABS: ArtSubTabConfig[] = [
  {
    id: "quick",
    label: "一键创作",
    icon: "ri-flashlight-line",
    desc: "选好角色和 Prompt，一键生成美图，快速出图不费力",
    comingSoon:
      "一键创作功能正在开发中，很快就会和你见面！届时你只需要选择角色和 Prompt，点击一下就能生成精美的二次元美图～",
    color: "#f472b6",
    gradient: "from-rose-100/60 to-pink-50/60",
  },
  {
    id: "fine",
    label: "精细创作",
    icon: "ri-settings-4-line",
    desc: "精细调整每一个参数，打造属于你的专属画风",
    comingSoon:
      "精细创作功能正在精心打磨中，将支持 LoRA 权重调整、采样器选择、CFG 参数设定等高级选项，让你对每一张图都有完全的掌控权～",
    color: "#e879f9",
    gradient: "from-fuchsia-100/60 to-pink-50/60",
  },
];

const ArtCreationPage = () => {
  const [activeSubTab, setActiveSubTab] = useState<ArtSubTab>("quick");

  const currentTab = ART_SUB_TABS.find((t) => t.id === activeSubTab)!;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div
        className="shrink-0 px-6 py-4 border-b border-rose-100/40 flex items-center gap-3"
        style={{ background: "rgba(255,255,255,0.3)" }}
      >
        <span
          className="text-xs text-rose-400/60 mr-1"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          创作模式：
        </span>
        <div
          className="flex items-center gap-1 p-1 rounded-2xl"
          style={{
            background: "rgba(253,164,175,0.1)",
            border: "1px solid rgba(253,164,175,0.18)",
          }}
        >
          {ART_SUB_TABS.map((tab) => {
            const isActive = activeSubTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveSubTab(tab.id)}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                style={{
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                  background: isActive
                    ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                    : "transparent",
                  color: isActive ? "white" : "#f472b6",
                  boxShadow: isActive ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
                }}
              >
                <div className="w-4 h-4 flex items-center justify-center">
                  <i className={`${tab.icon} text-sm`}></i>
                </div>
                {tab.label}
              </button>
            );
          })}
        </div>
        <span className="text-xs text-rose-300/50 ml-1">{currentTab.desc}</span>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col items-center justify-center px-8 py-12">
        <div
          className={`w-full max-w-lg rounded-3xl p-10 flex flex-col items-center text-center bg-gradient-to-br ${currentTab.gradient}`}
          style={{
            border: "1.5px dashed rgba(253,164,175,0.3)",
          }}
        >
          <div
            className="w-20 h-20 flex items-center justify-center rounded-3xl mb-6"
            style={{
              background: `linear-gradient(135deg, ${currentTab.color}20 0%, ${currentTab.color}10 100%)`,
              border: `1.5px solid ${currentTab.color}30`,
            }}
          >
            <i
              className={`${currentTab.icon} text-4xl`}
              style={{ color: currentTab.color }}
            ></i>
          </div>

          <span
            className="inline-flex items-center gap-1.5 px-4 py-1 rounded-full text-xs font-semibold mb-4 text-white"
            style={{
              background: `linear-gradient(135deg, ${currentTab.color} 0%, ${currentTab.color}cc 100%)`,
            }}
          >
            <i className={`${currentTab.icon} text-xs`}></i>
            {currentTab.label}
          </span>

          <h3
            className="text-lg font-bold text-rose-700/70 mb-3"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            功能正在精心准备中～
          </h3>

          <p className="text-sm text-rose-500/60 leading-relaxed mb-6">{currentTab.comingSoon}</p>

          <div className="flex items-center gap-3 w-full">
            <span className="flex-1 h-px bg-rose-200/40"></span>
            <span
              className="text-xs text-rose-300/50 tracking-widest"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              敬请期待
            </span>
            <span className="flex-1 h-px bg-rose-200/40"></span>
          </div>

          <div className="flex items-center gap-2 mt-6 opacity-30">
            <span className="w-2 h-2 rounded-full bg-rose-300 inline-block"></span>
            <span className="w-1.5 h-1.5 rounded-full bg-pink-200 inline-block"></span>
            <span className="w-2 h-2 rounded-full bg-fuchsia-200 inline-block"></span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ArtCreationPage;
