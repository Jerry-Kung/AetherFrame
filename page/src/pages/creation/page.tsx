import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ApiCharacterSummary, CharaProfile } from "@/types/material";
import { summaryToListProfile } from "@/types/material";
import type { CreationPromptSession } from "@/mocks/promptGen";
import * as materialApi from "@/services/materialApi";
import { ApiError } from "@/services/api";
import PromptGenPage from "./components/PromptGenPage";
import ArtCreationPage from "./components/ArtCreationPage";

type MainTabId = "prompt" | "art";

interface MainTab {
  id: MainTabId;
  label: string;
  icon: string;
  badge?: string;
}

const MAIN_TABS: MainTab[] = [
  { id: "prompt", label: "Prompt 预生成", icon: "ri-quill-pen-line" },
  { id: "art", label: "美图创作", icon: "ri-image-ai-line", badge: "即将上线" },
];

const decorations = [
  { size: 280, top: "-6%", left: "-5%", opacity: 0.14, delay: "0s" },
  { size: 180, top: "65%", left: "-3%", opacity: 0.1, delay: "1.2s" },
  { size: 220, top: "-4%", right: "-5%", opacity: 0.12, delay: "0.6s" },
  { size: 140, top: "72%", right: "-2%", opacity: 0.08, delay: "1.8s" },
];

const sparkles = [
  { top: "8%", left: "14%", size: 12, delay: "0s" },
  { top: "20%", right: "18%", size: 9, delay: "0.8s" },
  { top: "75%", left: "10%", size: 7, delay: "1.5s" },
  { top: "82%", right: "14%", size: 11, delay: "2.1s" },
];

function profilesFromSummaries(characters: ApiCharacterSummary[]): CharaProfile[] {
  return characters.map((s) => {
    const base = summaryToListProfile(s);
    const preview = (s.setting_preview ?? "").trim();
    if (preview) {
      return { ...base, settingText: preview };
    }
    return base;
  });
}

export default function CreationPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<MainTabId>("prompt");
  const [charas, setCharas] = useState<CharaProfile[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [promptSession, setPromptSession] = useState<CreationPromptSession | null>(null);

  const handlePromptSessionChange = useCallback((session: CreationPromptSession | null) => {
    setPromptSession(session);
  }, []);

  const loadCharacters = useCallback(async () => {
    setListLoading(true);
    setListError(null);
    try {
      const { characters } = await materialApi.listCharacters(0, 100);
      setCharas(profilesFromSummaries(characters));
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "加载角色列表失败";
      setListError(msg);
      setCharas([]);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCharacters();
  }, [loadCharacters]);

  return (
    <div
      className="relative h-screen w-full overflow-hidden flex flex-col"
      style={{
        background:
          "linear-gradient(145deg, #fff5f7 0%, #fffaf5 45%, #fef2f8 80%, #fff8f0 100%)",
      }}
    >
      <div
        className="absolute inset-0 z-0 pointer-events-none"
        style={{
          backgroundImage: `url("https://readdy.ai/api/search-image?query=soft%20dreamy%20anime%20aesthetic%20background%20art%20with%20delicate%20cherry%20blossom%20sakura%20petals%20floating%20in%20gentle%20breeze%2C%20warm%20pastel%20pink%20and%20creamy%20white%20watercolor%20illustration%20style%2C%20kawaii%20japanese%20aesthetic%2C%20soft%20bokeh%20circular%20lights%2C%20no%20people%20no%20characters%2C%20light%20and%20airy%20misty%20atmosphere%2C%20subtle%20floral%20pattern%20elements%2C%20beautiful%20pastel%20digital%20painting%20art%20with%20pink%20rose%20tones&width=1920&height=1080&seq=2001&orientation=landscape")`,
          backgroundSize: "cover",
          backgroundPosition: "center",
          opacity: 0.1,
        }}
      />

      {decorations.map((d, i) => (
        <div
          key={i}
          className="absolute rounded-full pointer-events-none"
          style={{
            width: d.size,
            height: d.size,
            top: d.top,
            left: (d as { left?: string }).left,
            right: (d as { right?: string }).right,
            opacity: d.opacity,
            background:
              i % 2 === 0
                ? "radial-gradient(circle, #fda4af 0%, #fecdd3 60%, transparent 100%)"
                : "radial-gradient(circle, #fbcfe8 0%, #fce7f3 60%, transparent 100%)",
            animation: "creation-floatUp 8s ease-in-out infinite",
            animationDelay: d.delay,
          }}
        />
      ))}

      {sparkles.map((s, i) => (
        <div
          key={i}
          className="absolute pointer-events-none text-rose-300/40 select-none"
          style={{
            top: s.top,
            left: (s as { left?: string }).left,
            right: (s as { right?: string }).right,
            fontSize: s.size,
            animation: "creation-twinkle 3s ease-in-out infinite",
            animationDelay: s.delay,
          }}
        >
          <i className="ri-star-fill"></i>
        </div>
      ))}

      <div className="relative z-10 flex flex-col h-full">
        <div className="flex items-center justify-between px-7 pt-5 pb-4 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => navigate("/")}
              className="w-8 h-8 shrink-0 flex items-center justify-center rounded-xl cursor-pointer transition-all duration-200 hover:bg-rose-100/60"
              style={{ color: "#f472b6" }}
              aria-label="返回首页"
            >
              <i className="ri-arrow-left-line text-base"></i>
            </button>
            <div className="flex items-center gap-2 min-w-0">
              <div
                className="w-7 h-7 shrink-0 flex items-center justify-center rounded-lg"
                style={{
                  background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                }}
              >
                <i className="ri-image-ai-line text-white text-sm"></i>
              </div>
              <h1
                className="text-base font-bold text-transparent bg-clip-text truncate"
                style={{
                  backgroundImage: "linear-gradient(135deg, #f472b6 0%, #ec4899 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                美图创作
              </h1>
              <span className="text-xs text-rose-300/60 hidden md:inline shrink-0">
                · 二次元美图开发引擎
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span
              className="text-xs text-rose-400/60 hidden md:inline"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              从 Prompt 到美图，一站式创作体验
            </span>
          </div>
        </div>

        <div className="flex-1 flex flex-col px-6 pb-6 min-h-0">
          <div
            className="flex-1 flex flex-col rounded-3xl overflow-hidden min-w-0"
            style={{
              background: "rgba(255,255,255,0.55)",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              border: "1px solid rgba(253,164,175,0.2)",
            }}
          >
            <div className="h-[3px] w-full shrink-0 bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300 opacity-60" />

            <div className="flex items-center gap-1 px-5 pt-4 pb-0 shrink-0 flex-wrap">
              <div
                className="flex items-center gap-0.5 p-1 rounded-2xl"
                style={{
                  background: "rgba(253,164,175,0.1)",
                  border: "1px solid rgba(253,164,175,0.18)",
                }}
              >
                {MAIN_TABS.map((tab) => {
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTab(tab.id)}
                      className="relative flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
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
                      {tab.badge && (
                        <span
                          className="ml-1 text-xs px-1.5 py-0.5 rounded-full"
                          style={{
                            background: isActive
                              ? "rgba(255,255,255,0.25)"
                              : "rgba(253,164,175,0.2)",
                            color: isActive ? "white" : "#f472b6",
                            fontSize: "10px",
                          }}
                        >
                          {tab.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              <span className="ml-3 text-xs text-rose-300/60 hidden md:inline">
                {activeTab === "prompt"
                  ? "根据角色设定和种子提示词，自动生成多个可用 Prompt"
                  : "选择 Prompt 和角色，生成专属二次元美图"}
              </span>
            </div>

            <div className="mx-5 mt-3 mb-0 h-px bg-rose-100/40 shrink-0" />

            <div className="flex-1 min-h-0 overflow-hidden">
              {activeTab === "prompt" && (
                <PromptGenPage
                  charas={charas}
                  listLoading={listLoading}
                  listError={listError}
                  onPromptSessionChange={handlePromptSessionChange}
                />
              )}
              {activeTab === "art" && (
                <ArtCreationPage charas={charas} promptSession={promptSession} />
              )}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes creation-floatUp {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-18px) scale(1.04); }
        }
        @keyframes creation-twinkle {
          0%, 100% { opacity: 0.3; transform: scale(1) rotate(0deg); }
          50% { opacity: 0.7; transform: scale(1.3) rotate(20deg); }
        }
      `}</style>
    </div>
  );
}
