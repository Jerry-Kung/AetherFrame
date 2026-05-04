import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import type { ApiCharacterSummary, CharaProfile } from "@/types/material";
import { summaryToListProfile, toCharaProfile } from "@/types/material";
import * as materialApi from "@/services/materialApi";
import { ApiError } from "@/services/api";
import type { SeedPromptSection } from "@/mocks/materialChara";
import { persistMarkSeedAsUsed } from "@/mocks/materialChara";
import Header from "./components/Header";
import ModeSwitch, { type ModeId } from "./components/ModeSwitch";
import BatchCreationPage from "./components/BatchCreationPage";

const decorations = [
  { size: 320, top: "-8%", left: "-6%", opacity: 0.18, delay: "0s" },
  { size: 200, top: "60%", left: "-4%", opacity: 0.12, delay: "1.2s" },
  { size: 260, top: "-5%", right: "-6%", opacity: 0.15, delay: "0.6s" },
  { size: 160, top: "70%", right: "-3%", opacity: 0.1, delay: "1.8s" },
  { size: 100, top: "40%", left: "5%", opacity: 0.08, delay: "0.9s" },
  { size: 80, top: "20%", right: "8%", opacity: 0.1, delay: "2.2s" },
];

const sparkles = [
  { top: "10%", left: "12%", size: 14, delay: "0s" },
  { top: "22%", right: "16%", size: 10, delay: "0.8s" },
  { top: "70%", left: "8%", size: 8, delay: "1.5s" },
  { top: "80%", right: "12%", size: 12, delay: "2.1s" },
];

const DETAIL_CHUNK = 4;

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

export default function Home() {
  const navigate = useNavigate();
  const [activeMode, setActiveMode] = useState<ModeId>("material");
  const [charas, setCharas] = useState<CharaProfile[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const loadCharacters = useCallback(async () => {
    setListLoading(true);
    setListError(null);
    try {
      const { characters } = await materialApi.listCharacters(0, 100);
      const list = profilesFromSummaries(characters);
      const byId = new Map(list.map((c) => [c.id, c] as const));
      const doneIds = list.filter((c) => c.status === "done").map((c) => c.id);

      for (let i = 0; i < doneIds.length; i += DETAIL_CHUNK) {
        const chunk = doneIds.slice(i, i + DETAIL_CHUNK);
        const results = await Promise.allSettled(chunk.map((id) => materialApi.getCharacter(id)));
        results.forEach((res, j) => {
          const id = chunk[j];
          if (!id) return;
          if (res.status === "fulfilled") {
            byId.set(id, toCharaProfile(res.value));
          }
        });
      }

      setCharas(list.map((c) => byId.get(c.id)!));
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

  const handleMarkSeedUsed = useCallback(
    async (charaId: string, section: SeedPromptSection, seedId: string) => {
      if (section === "fixed") {
        await persistMarkSeedAsUsed({ section: "fixed", seedId });
        setCharas((prev) => [...prev]);
        return;
      }
      const profile = charas.find((c) => c.id === charaId);
      if (!profile) return;
      const next = await persistMarkSeedAsUsed({
        characterId: charaId,
        profile,
        section,
        seedId,
      });
      if (next) {
        setCharas((prev) => prev.map((c) => (c.id === charaId ? next : c)));
      }
    },
    [charas]
  );

  const handleModeSwitch = (id: ModeId) => {
    if (id === "material") {
      navigate("/material");
      return;
    }
    if (id === "repair") {
      navigate("/repair");
      return;
    }
    if (id === "creation") {
      navigate("/creation");
      return;
    }
    setActiveMode(id);
  };

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
          opacity: 0.13,
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
            animation: `floatUp 8s ease-in-out infinite`,
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
            animation: `twinkle 3s ease-in-out infinite`,
            animationDelay: s.delay,
          }}
        >
          <i className="ri-star-fill"></i>
        </div>
      ))}

      <div className="relative z-10 flex flex-col h-full">
        <div className="flex items-center justify-between px-7 pt-5 pb-4 shrink-0">
          <Header />
          <div className="hidden md:block w-px h-10 bg-rose-200/40 mx-6" />
          <ModeSwitch activeMode={activeMode} onSwitch={handleModeSwitch} />
        </div>

        <div className="flex-1 flex flex-col px-6 pb-6 min-h-0">
          <div
            className="flex-1 relative flex flex-col min-h-0 overflow-hidden rounded-3xl border border-rose-100/80"
            style={{
              background: "rgba(255,255,255,0.55)",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
            }}
          >
            <div className="h-[3px] w-full shrink-0 bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300 opacity-70" />
            <div className="flex-1 min-h-0 overflow-auto relative">
              <BatchCreationPage
                charas={charas}
                listLoading={listLoading}
                listError={listError}
                onMarkSeedUsed={handleMarkSeedUsed}
              />
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes floatUp {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-18px) scale(1.04); }
        }
        @keyframes twinkle {
          0%, 100% { opacity: 0.3; transform: scale(1) rotate(0deg); }
          50% { opacity: 0.7; transform: scale(1.3) rotate(20deg); }
        }
      `}</style>
    </div>
  );
}
