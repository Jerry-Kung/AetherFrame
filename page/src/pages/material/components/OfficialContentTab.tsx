import { useCallback, useMemo, useState } from "react";
import type { CharaBio, OfficialSeedPrompts, SeedPrompt } from "@/types/material";
import { emptyOfficialSeedPrompts } from "@/types/material";
import type { SeedPromptSection } from "@/mocks/materialChara";
import SeedPromptSection from "./SeedPromptSection";

interface OfficialContentTabProps {
  officialPhotos: [string | null, string | null, string | null, string | null, string | null];
  bio: CharaBio;
  fixedTemplates: SeedPrompt[];
  onPhotoClick: (slotIndex: number) => void;
  onOfficialPhotoDelete: (slotIndex: number) => void | Promise<void>;
  onGoProfileTask?: () => void;
  onAddSeed: (section: SeedPromptSection, text: string) => void | Promise<void>;
  onEditSeed: (section: SeedPromptSection, seedId: string, text: string) => void | Promise<void>;
  onToggleSeedUsed: (section: SeedPromptSection, seedId: string) => void | Promise<void>;
  onDeleteSeed: (section: SeedPromptSection, id: string) => void | Promise<void>;
  onClearSeedsAll: () => void | Promise<void>;
}

const PHOTO_LABELS = [
  "全身正面",
  "全身侧面",
  "半身正面",
  "半身侧面",
  "脸部特写",
] as const;

type StandardPhotoItem = {
  id: string;
  slotIndex: number;
  label: (typeof PHOTO_LABELS)[number];
  url: string;
};

function countUsedSeedsBio(p: OfficialSeedPrompts | null | undefined): number {
  if (!p) return 0;
  return (
    p.characterSpecific.filter((s) => s.used).length + p.general.filter((s) => s.used).length
  );
}

function countUsedFixed(fixed: SeedPrompt[]): number {
  return fixed.filter((s) => s.used).length;
}

const OfficialContentTab = ({
  officialPhotos,
  bio,
  fixedTemplates,
  onPhotoClick,
  onOfficialPhotoDelete,
  onGoProfileTask,
  onAddSeed,
  onEditSeed,
  onToggleSeedUsed,
  onDeleteSeed,
  onClearSeedsAll,
}: OfficialContentTabProps) => {
  const [deletePhotoId, setDeletePhotoId] = useState<string | null>(null);
  const [seedSubTab, setSeedSubTab] = useState<SeedPromptSection>("characterSpecific");
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [seedDeleteTarget, setSeedDeleteTarget] = useState<{
    section: SeedPromptSection;
    id: string;
    text: string;
  } | null>(null);
  const [clearSeedsOpen, setClearSeedsOpen] = useState(false);
  const [deletingSeedId, setDeletingSeedId] = useState<string | null>(null);
  const [clearingSeeds, setClearingSeeds] = useState(false);
  /** 正式内容页角色小档案正文默认折叠，避免长文撑破布局并挡住下方模块 */
  const [charaProfileExpanded, setCharaProfileExpanded] = useState(false);

  const standardPhotos: StandardPhotoItem[] = useMemo(
    () =>
      officialPhotos
        .map((url, slotIndex) => ({
          id: `slot-${slotIndex}`,
          slotIndex,
          label: PHOTO_LABELS[slotIndex],
          url,
        }))
        .filter((p): p is StandardPhotoItem => typeof p.url === "string" && p.url.length > 0),
    [officialPhotos]
  );

  const filledCount = standardPhotos.length;
  const photoPendingDelete = standardPhotos.find((p) => p.id === deletePhotoId);

  const charaProfileText = (bio.charaProfile ?? "").trim();
  const officialSeeds = bio.officialSeedPrompts ?? null;
  const effectiveSeeds = officialSeeds ?? emptyOfficialSeedPrompts();
  const bioSeedRowCount =
    (officialSeeds?.characterSpecific.length ?? 0) + (officialSeeds?.general.length ?? 0);
  const hasAnySeedContent = bioSeedRowCount > 0 || fixedTemplates.length > 0;
  const usedSeedCount = countUsedSeedsBio(officialSeeds) + countUsedFixed(fixedTemplates);

  const handleConfirmDelete = () => {
    if (photoPendingDelete === undefined) return;
    const idx = photoPendingDelete.slotIndex;
    setDeletePhotoId(null);
    void onOfficialPhotoDelete(idx);
  };

  const handleCancelDelete = () => {
    setDeletePhotoId(null);
  };

  const runToggle = useCallback(
    async (section: SeedPromptSection, id: string) => {
      setTogglingId(id);
      try {
        await onToggleSeedUsed(section, id);
      } finally {
        setTogglingId(null);
      }
    },
    [onToggleSeedUsed]
  );

  const requestSeedDelete = useCallback((section: SeedPromptSection, id: string, text: string) => {
    setSeedDeleteTarget({ section, id, text });
  }, []);

  const cancelSeedDelete = useCallback(() => {
    if (deletingSeedId) return;
    setSeedDeleteTarget(null);
  }, [deletingSeedId]);

  const confirmSeedDelete = useCallback(async () => {
    if (!seedDeleteTarget) return;
    const { section, id } = seedDeleteTarget;
    setDeletingSeedId(id);
    try {
      await onDeleteSeed(section, id);
      setSeedDeleteTarget(null);
    } finally {
      setDeletingSeedId(null);
    }
  }, [seedDeleteTarget, onDeleteSeed]);

  const cancelClearSeeds = useCallback(() => {
    if (clearingSeeds) return;
    setClearSeedsOpen(false);
  }, [clearingSeeds]);

  const confirmClearSeeds = useCallback(async () => {
    setClearingSeeds(true);
    try {
      await onClearSeedsAll();
      setClearSeedsOpen(false);
    } finally {
      setClearingSeeds(false);
    }
  }, [onClearSeedsAll]);

  return (
    <div className="flex flex-col gap-6 min-h-0">
      <section>
        <h3
          className="text-sm font-semibold text-rose-700/80 mb-3 flex items-center gap-2 flex-wrap"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <span className="flex items-center gap-1.5">
            <i className="ri-vip-crown-line text-rose-400" />
            标准参考照
          </span>
          <span className="text-xs font-medium text-rose-400/90 bg-rose-50/90 px-2.5 py-0.5 rounded-full border border-rose-100/80">
            {filledCount} 张
          </span>
        </h3>

        {filledCount === 0 ? (
          <div
            className="rounded-2xl border border-dashed border-rose-200/80 flex flex-col items-center justify-center py-14 px-6 text-center"
            style={{ background: "rgba(253,164,175,0.06)" }}
          >
            <div
              className="w-14 h-14 flex items-center justify-center rounded-2xl mb-3"
              style={{
                background: "rgba(253,164,175,0.1)",
                border: "1.5px dashed rgba(244,114,182,0.22)",
              }}
            >
              <i className="ri-image-line text-rose-300 text-2xl" />
            </div>
            <p className="text-sm text-rose-400/75 max-w-sm leading-relaxed" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              所有标准照已删除，可重新绘制哦～
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {officialPhotos.map((url, i) => (
              <div key={i} className="relative">
                {url ? (
                  <div
                    className={[
                      "relative aspect-[3/4] rounded-2xl overflow-hidden border transition-all text-left group",
                      "border-rose-100/80 hover:shadow-lg hover:border-pink-200",
                    ].join(" ")}
                  >
                    <button
                      type="button"
                      onClick={() => onPhotoClick(i)}
                      className="absolute inset-0 z-0 cursor-zoom-in text-left"
                      aria-label={`${PHOTO_LABELS[i]}，点击预览`}
                    >
                      <img src={url} alt="" className="w-full h-full object-cover pointer-events-none" draggable={false} />
                      <div className="absolute inset-x-0 bottom-0 py-1.5 px-2 bg-gradient-to-t from-black/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                        <span className="text-[10px] text-white/90">{PHOTO_LABELS[i]} · 点击预览</span>
                      </div>
                      <div className="absolute inset-0 bg-rose-900/0 group-hover:bg-rose-900/15 transition-colors pointer-events-none" />
                      <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                        <div className="w-8 h-8 flex items-center justify-center rounded-full bg-white/90 text-rose-500 shadow-sm">
                          <i className="ri-zoom-in-line text-sm" />
                        </div>
                      </div>
                    </button>
                    <button
                      type="button"
                      className="absolute top-2 right-2 z-10 w-7 h-7 flex items-center justify-center rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 cursor-pointer"
                      style={{
                        background: "rgba(255,255,255,0.95)",
                        boxShadow: "0 1px 6px rgba(244,114,182,0.2)",
                      }}
                      title="删除此标准照"
                      aria-label={`删除${PHOTO_LABELS[i]}`}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setDeletePhotoId(`slot-${i}`);
                      }}
                    >
                      <i className="ri-delete-bin-line text-rose-400 text-sm" />
                    </button>
                    <span className="absolute top-2 left-2 z-[5] text-[10px] px-2 py-0.5 rounded-full bg-black/35 text-white/95 pointer-events-none">
                      {PHOTO_LABELS[i]}
                    </span>
                  </div>
                ) : (
                  <button
                    type="button"
                    disabled
                    className="relative w-full aspect-[3/4] rounded-2xl overflow-hidden border border-dashed border-rose-200/70 bg-rose-50/40 cursor-default text-left"
                  >
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-rose-300/70 text-xs gap-1">
                      <i className="ri-image-add-line text-2xl" />
                      <span>待生成</span>
                    </div>
                    <span className="absolute top-2 left-2 text-[10px] px-2 py-0.5 rounded-full bg-black/20 text-white/90 pointer-events-none">
                      {PHOTO_LABELS[i]}
                    </span>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1">
          <h3
            className="text-sm font-semibold text-rose-700/80 flex items-center gap-1.5 min-w-0"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <i className="ri-file-list-3-line text-rose-400 shrink-0" />
            <span className="truncate">角色小档案</span>
          </h3>
          <button
            type="button"
            onClick={() => setCharaProfileExpanded((v) => !v)}
            className="shrink-0 flex items-center gap-1 text-xs px-2.5 py-1 rounded-xl cursor-pointer transition-all hover:opacity-90 border border-rose-200/80 bg-white/80 text-rose-600"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            aria-expanded={charaProfileExpanded}
          >
            <i className={charaProfileExpanded ? "ri-arrow-up-s-line" : "ri-arrow-down-s-line"} />
            {charaProfileExpanded ? "收起" : "展开"}
          </button>
        </div>
        <p className="text-[11px] text-rose-400/55 leading-snug mb-2 pl-0.5">
          正文与「加工任务 → 角色小档案」中保存并写入服务器的档案一致（bio_json.chara_profile）。
        </p>

        {!charaProfileExpanded ? (
          <p className="text-xs text-rose-400/75 leading-relaxed pl-0.5" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
            {charaProfileText
              ? `已保存正文（约 ${charaProfileText.length} 字），点击「展开」查看；下方种子提示词等模块可滚动浏览。`
              : "尚未在加工任务中生成并保存小档案正文。点击「展开」查看说明与入口。"}
          </p>
        ) : charaProfileText ? (
          <div
            className="rounded-2xl border border-rose-100/80 overflow-hidden min-w-0"
            style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(255,250,252,0.95) 100%)" }}
          >
            <div className="max-h-[min(55vh,28rem)] overflow-y-auto overflow-x-hidden px-4 py-4 text-sm text-rose-800/90 leading-relaxed whitespace-pre-wrap break-words">
              {bio.charaProfile}
            </div>
          </div>
        ) : (
          <div
            className="rounded-2xl border border-dashed border-rose-200/80 flex flex-col items-center justify-center py-10 px-6 text-center"
            style={{ background: "rgba(253,164,175,0.06)" }}
          >
            <i className="ri-quill-pen-line text-rose-300 text-2xl mb-2" />
            <p className="text-sm text-rose-400/80 max-w-md leading-relaxed mb-4" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              还没有从加工任务生成并保存的角色小档案正文。完成标准照后，在「加工任务 → 角色小档案」中整理并保存即可在此查看。
            </p>
            {onGoProfileTask && (
              <button
                type="button"
                onClick={onGoProfileTask}
                className="text-xs px-4 py-2 rounded-xl cursor-pointer transition-all hover:opacity-90"
                style={{
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                  background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                  color: "white",
                  boxShadow: "0 2px 10px rgba(244,114,182,0.25)",
                }}
              >
                去生成小档案
              </button>
            )}
          </div>
        )}
      </section>

      <section>
        <div className="flex items-start justify-between gap-2 mb-1">
          <h3
            className="text-sm font-semibold text-rose-700/80 flex items-center gap-2 flex-wrap min-w-0"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <span className="flex items-center gap-1.5 min-w-0">
              <i className="ri-seedling-line text-rose-400 shrink-0" />
              <span className="truncate">种子提示词</span>
            </span>
            <span className="text-xs font-medium text-rose-400/90 bg-rose-50/90 px-2.5 py-0.5 rounded-full border border-rose-100/80 shrink-0">
              已用 {usedSeedCount} 条
            </span>
          </h3>
          {hasAnySeedContent && (
            <button
              type="button"
              onClick={() => setClearSeedsOpen(true)}
              className="shrink-0 text-xs px-3 py-1.5 rounded-xl cursor-pointer transition-all hover:opacity-90 whitespace-nowrap"
              style={{
                fontFamily: "'ZCOOL KuaiLe', cursive",
                background: "rgba(253,164,175,0.12)",
                color: "#db2777",
                border: "1px solid rgba(244,114,182,0.28)",
              }}
            >
              一键清空
            </button>
          )}
        </div>
        <p className="text-xs text-rose-400/70 mb-3" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
          支持手动添加与编辑；也可从加工任务保存为正式种子。固定模板全角色共享，不写入当前角色档案。
        </p>

        <div
          className="inline-flex flex-wrap items-center gap-1 p-1 rounded-2xl mb-3"
          style={{
            background: "rgba(253,164,175,0.1)",
            border: "1px solid rgba(253,164,175,0.2)",
          }}
        >
          <button
            type="button"
            onClick={() => setSeedSubTab("characterSpecific")}
            className="px-3 py-1.5 rounded-xl text-xs sm:text-sm transition-all cursor-pointer whitespace-nowrap"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              background:
                seedSubTab === "characterSpecific"
                  ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                  : "transparent",
              color: seedSubTab === "characterSpecific" ? "white" : "#f472b6",
              boxShadow: seedSubTab === "characterSpecific" ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
            }}
          >
            角色专属
            <span className="ml-1 opacity-80">({effectiveSeeds.characterSpecific.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setSeedSubTab("general")}
            className="px-3 py-1.5 rounded-xl text-xs sm:text-sm transition-all cursor-pointer whitespace-nowrap"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              background:
                seedSubTab === "general"
                  ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                  : "transparent",
              color: seedSubTab === "general" ? "white" : "#f472b6",
              boxShadow: seedSubTab === "general" ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
            }}
          >
            通用种子
            <span className="ml-1 opacity-80">({effectiveSeeds.general.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setSeedSubTab("fixed")}
            className="px-3 py-1.5 rounded-xl text-xs sm:text-sm transition-all cursor-pointer whitespace-nowrap"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              background:
                seedSubTab === "fixed"
                  ? "linear-gradient(135deg, #fb7185 0%, #e11d48 100%)"
                  : "transparent",
              color: seedSubTab === "fixed" ? "white" : "#e11d48",
              boxShadow: seedSubTab === "fixed" ? "0 2px 8px rgba(225,29,72,0.25)" : "none",
            }}
          >
            固定模板
            <span className="ml-1 opacity-80">({fixedTemplates.length})</span>
          </button>
        </div>

        {seedSubTab === "characterSpecific" && (
          <SeedPromptSection
            title="角色专属"
            icon="ri-user-star-line"
            accentColor="#f472b6"
            prompts={effectiveSeeds.characterSpecific}
            busyId={togglingId ?? deletingSeedId}
            onToggle={(id) => void runToggle("characterSpecific", id)}
            onDelete={(id) => {
              const s = effectiveSeeds.characterSpecific.find((x) => x.id === id);
              if (s) requestSeedDelete("characterSpecific", id, s.text);
            }}
            onAdd={(text) => void onAddSeed("characterSpecific", text)}
            onEdit={(id, text) => void onEditSeed("characterSpecific", id, text)}
          />
        )}
        {seedSubTab === "general" && (
          <SeedPromptSection
            title="通用种子"
            icon="ri-global-line"
            accentColor="#fb923c"
            prompts={effectiveSeeds.general}
            busyId={togglingId ?? deletingSeedId}
            onToggle={(id) => void runToggle("general", id)}
            onDelete={(id) => {
              const s = effectiveSeeds.general.find((x) => x.id === id);
              if (s) requestSeedDelete("general", id, s.text);
            }}
            onAdd={(text) => void onAddSeed("general", text)}
            onEdit={(id, text) => void onEditSeed("general", id, text)}
          />
        )}
        {seedSubTab === "fixed" && (
          <SeedPromptSection
            title="固定模板"
            icon="ri-shield-star-line"
            accentColor="#e11d48"
            prompts={fixedTemplates}
            busyId={togglingId ?? deletingSeedId}
            onToggle={(id) => void runToggle("fixed", id)}
            onDelete={(id) => {
              const s = fixedTemplates.find((x) => x.id === id);
              if (s) requestSeedDelete("fixed", id, s.text);
            }}
            onAdd={(text) => void onAddSeed("fixed", text)}
            onEdit={(id, text) => void onEditSeed("fixed", id, text)}
          />
        )}
      </section>

      {deletePhotoId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
          onClick={handleCancelDelete}
          role="presentation"
        >
          <div
            className="relative w-[min(100%,20rem)] rounded-3xl overflow-hidden mx-4"
            style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="official-photo-delete-title"
          >
            <div className="flex flex-col items-center pt-7 pb-4 px-6">
              <div
                className="w-14 h-14 flex items-center justify-center rounded-2xl mb-4"
                style={{
                  background: "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
                  border: "1.5px solid rgba(244,114,182,0.2)",
                }}
              >
                <i className="ri-delete-bin-2-line text-rose-400 text-2xl" />
              </div>
              <h3
                id="official-photo-delete-title"
                className="text-base font-bold text-rose-600 mb-1.5"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                确认删除标准照？
              </h3>
              <p className="text-sm text-rose-400/80 text-center leading-relaxed">
                将删除「{photoPendingDelete?.label ?? "该照片"}」。删除后需要重新绘制才能恢复。
              </p>
            </div>

            <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />

            <div className="flex gap-3 p-4">
              <button
                type="button"
                onClick={handleCancelDelete}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap"
                style={{
                  background: "rgba(253,164,175,0.08)",
                  color: "#f472b6",
                  border: "1px solid rgba(244,114,182,0.2)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                再想想
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white"
                style={{
                  background: "linear-gradient(135deg, #fb7185 0%, #f472b6 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {seedDeleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
          onClick={cancelSeedDelete}
          role="presentation"
        >
          <div
            className="relative w-full max-w-md rounded-3xl overflow-hidden"
            style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="official-seed-delete-title"
          >
            <div className="flex flex-col items-center pt-7 pb-4 px-6">
              <div
                className="w-14 h-14 flex items-center justify-center rounded-2xl mb-4"
                style={{
                  background: "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
                  border: "1.5px solid rgba(244,114,182,0.2)",
                }}
              >
                <i className="ri-delete-bin-2-line text-rose-400 text-2xl" />
              </div>
              <h3
                id="official-seed-delete-title"
                className="text-base font-bold text-rose-600 mb-1.5"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                确认删除这条种子提示词？
              </h3>
              <p className="text-xs text-rose-400/75 mb-2 text-center">删除后无法恢复，请核对正文是否为你要删的那一条。</p>
              {seedDeleteTarget.section === "fixed" && (
                <p className="text-xs text-rose-500 font-medium mb-2 text-center" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                  此为全角色共享的固定模板，删除后所有角色列表中都会消失。
                </p>
              )}
              <div
                className="w-full max-h-40 overflow-y-auto rounded-2xl border border-rose-100/90 px-3 py-2.5 text-left mt-1"
                style={{ background: "rgba(253,164,175,0.06)" }}
              >
                <p className="text-sm text-rose-800/90 leading-relaxed whitespace-pre-wrap break-words">
                  {seedDeleteTarget.text}
                </p>
              </div>
            </div>

            <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />

            <div className="flex gap-3 p-4">
              <button
                type="button"
                onClick={cancelSeedDelete}
                disabled={deletingSeedId !== null}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50"
                style={{
                  background: "rgba(253,164,175,0.08)",
                  color: "#f472b6",
                  border: "1px solid rgba(244,114,182,0.2)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                再想想
              </button>
              <button
                type="button"
                onClick={() => void confirmSeedDelete()}
                disabled={deletingSeedId !== null}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white disabled:opacity-60"
                style={{
                  background: "linear-gradient(135deg, #fb7185 0%, #f472b6 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                {deletingSeedId ? "删除中…" : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}

      {clearSeedsOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
          onClick={cancelClearSeeds}
          role="presentation"
        >
          <div
            className="relative w-full max-w-md rounded-3xl overflow-hidden"
            style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="official-seed-clear-title"
          >
            <div className="flex flex-col items-center pt-7 pb-4 px-6">
              <div
                className="w-14 h-14 flex items-center justify-center rounded-2xl mb-4"
                style={{
                  background: "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
                  border: "1.5px solid rgba(244,114,182,0.2)",
                }}
              >
                <i className="ri-error-warning-line text-rose-400 text-2xl" />
              </div>
              <h3
                id="official-seed-clear-title"
                className="text-base font-bold text-rose-600 mb-2 text-center"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                确认清空全部种子提示词？
              </h3>
              <p className="text-sm text-rose-500/90 text-center leading-relaxed" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                将清空当前角色的「角色专属」「通用种子」全部条目，并清空<strong className="text-rose-600">所有角色共享</strong>的「固定模板」列表。此操作无法撤销。
              </p>
            </div>

            <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />

            <div className="flex gap-3 p-4">
              <button
                type="button"
                onClick={cancelClearSeeds}
                disabled={clearingSeeds}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50"
                style={{
                  background: "rgba(253,164,175,0.08)",
                  color: "#f472b6",
                  border: "1px solid rgba(244,114,182,0.2)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void confirmClearSeeds()}
                disabled={clearingSeeds}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white disabled:opacity-60"
                style={{
                  background: "linear-gradient(135deg, #fb7185 0%, #f472b6 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                {clearingSeeds ? "清空中…" : "确认清空"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OfficialContentTab;
