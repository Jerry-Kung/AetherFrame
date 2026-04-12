import { useCallback, useMemo, useState } from "react";
import type { CharaBio, OfficialSeedPrompts } from "@/types/material";
import { cloneOfficialSeedPrompts } from "@/types/material";

interface OfficialContentTabProps {
  officialPhotos: [string | null, string | null, string | null, string | null, string | null];
  bio: CharaBio;
  onPhotoClick: (slotIndex: number) => void;
  onOfficialPhotoDelete: (slotIndex: number) => void | Promise<void>;
  onGoProfileTask?: () => void;
  onToggleUsedSeed: (next: OfficialSeedPrompts) => void | Promise<void>;
}

const PHOTO_LABELS = [
  "全身正面",
  "全身侧面",
  "半身正面",
  "半身侧面",
  "脸部特写",
] as const;

const BIO_FIELDS: { key: keyof CharaBio; label: string }[] = [
  { key: "displayName", label: "姓名" },
  { key: "age", label: "年龄" },
  { key: "height", label: "身高" },
  { key: "personality", label: "性格" },
  { key: "ability", label: "能力" },
  { key: "appearance", label: "外观" },
];

type StandardPhotoItem = {
  id: string;
  slotIndex: number;
  label: (typeof PHOTO_LABELS)[number];
  url: string;
};

type SeedSubTab = "character" | "general";

function countUsedSeeds(p: OfficialSeedPrompts | null | undefined): number {
  if (!p) return 0;
  return (
    p.characterSpecific.filter((s) => s.used).length + p.general.filter((s) => s.used).length
  );
}

const OfficialContentTab = ({
  officialPhotos,
  bio,
  onPhotoClick,
  onOfficialPhotoDelete,
  onGoProfileTask,
  onToggleUsedSeed,
}: OfficialContentTabProps) => {
  const [deletePhotoId, setDeletePhotoId] = useState<string | null>(null);
  const [seedSubTab, setSeedSubTab] = useState<SeedSubTab>("character");
  const [togglingId, setTogglingId] = useState<string | null>(null);

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
  const hasSeedRows =
    !!officialSeeds &&
    (officialSeeds.characterSpecific.length > 0 || officialSeeds.general.length > 0);
  const usedSeedCount = countUsedSeeds(officialSeeds);

  const handleConfirmDelete = () => {
    if (photoPendingDelete === undefined) return;
    const idx = photoPendingDelete.slotIndex;
    setDeletePhotoId(null);
    void onOfficialPhotoDelete(idx);
  };

  const handleCancelDelete = () => {
    setDeletePhotoId(null);
  };

  const flipUsed = useCallback(
    async (scope: keyof Pick<OfficialSeedPrompts, "characterSpecific" | "general">, id: string) => {
      if (!officialSeeds) return;
      const next = cloneOfficialSeedPrompts(officialSeeds);
      const arr = next[scope];
      const idx = arr.findIndex((s) => s.id === id);
      if (idx < 0) return;
      arr[idx] = { ...arr[idx], used: !arr[idx].used };
      setTogglingId(id);
      try {
        await onToggleUsedSeed(next);
      } finally {
        setTogglingId(null);
      }
    },
    [officialSeeds, onToggleUsedSeed]
  );

  const seedList = (items: { id: string; text: string; used: boolean }[], scope: "characterSpecific" | "general") =>
    items.length === 0 ? (
      <div
        className="rounded-2xl border border-dashed border-rose-200/80 flex flex-col items-center justify-center py-12 px-4 text-center"
        style={{ background: "rgba(253,164,175,0.06)" }}
      >
        <i className="ri-seedling-line text-rose-300 text-2xl mb-2" />
        <p className="text-sm text-rose-400/75 max-w-sm leading-relaxed" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
          暂无该分类下的正式种子，请在「加工任务 → 角色小档案 → 创作建议 → 种子提示词」中生成并保存
        </p>
        {onGoProfileTask && (
          <button
            type="button"
            onClick={onGoProfileTask}
            className="mt-4 text-xs px-4 py-2 rounded-xl cursor-pointer transition-all hover:opacity-90"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              color: "white",
              boxShadow: "0 2px 10px rgba(244,114,182,0.25)",
            }}
          >
            去加工任务
          </button>
        )}
      </div>
    ) : (
      <ul className="flex flex-col gap-2">
        {items.map((s) => (
          <li
            key={s.id}
            className="rounded-2xl border border-rose-100/80 px-4 py-3 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3"
            style={{ background: "rgba(255,255,255,0.85)" }}
          >
            <p className="text-sm text-rose-800/90 leading-relaxed flex-1 min-w-0">{s.text}</p>
            <button
              type="button"
              disabled={togglingId === s.id}
              onClick={() => void flipUsed(scope, s.id)}
              className="shrink-0 self-start sm:self-center text-xs px-3 py-1.5 rounded-xl cursor-pointer transition-all disabled:opacity-50 whitespace-nowrap"
              style={{
                fontFamily: "'ZCOOL KuaiLe', cursive",
                background: s.used ? "rgba(110,231,183,0.2)" : "rgba(253,164,175,0.12)",
                color: s.used ? "#059669" : "#db2777",
                border: s.used ? "1px solid rgba(110,231,183,0.35)" : "1px solid rgba(244,114,182,0.25)",
              }}
            >
              {togglingId === s.id ? "…" : s.used ? "已使用" : "标记使用"}
            </button>
          </li>
        ))}
      </ul>
    );

  return (
    <div className="flex flex-col gap-6 min-h-0 overflow-y-auto pr-1">
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

      <section>
        <h3
          className="text-sm font-semibold text-rose-700/80 mb-3 flex items-center gap-1.5"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <i className="ri-file-list-3-line text-rose-400" />
          角色小档案
        </h3>
        {charaProfileText ? (
          <div
            className="rounded-2xl overflow-hidden border border-rose-100/80 px-4 py-4 text-sm text-rose-800/90 leading-relaxed whitespace-pre-wrap break-words"
            style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(255,250,252,0.95) 100%)" }}
          >
            {bio.charaProfile}
          </div>
        ) : (
          <div
            className="rounded-2xl border border-dashed border-rose-200/80 flex flex-col items-center justify-center py-12 px-6 text-center"
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
        <h3
          className="text-sm font-semibold text-rose-700/80 mb-1 flex items-center gap-2 flex-wrap"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <span className="flex items-center gap-1.5">
            <i className="ri-seedling-line text-rose-400" />
            种子提示词
          </span>
          <span className="text-xs font-medium text-rose-400/90 bg-rose-50/90 px-2.5 py-0.5 rounded-full border border-rose-100/80">
            已用 {usedSeedCount} 条
          </span>
        </h3>
        <p className="text-xs text-rose-400/70 mb-3" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
          来自加工任务中保存的正式种子；可随时标记是否已在创作中使用。
        </p>

        {!hasSeedRows ? (
          <div
            className="rounded-2xl border border-dashed border-rose-200/80 flex flex-col items-center justify-center py-12 px-6 text-center"
            style={{ background: "rgba(253,164,175,0.06)" }}
          >
            <i className="ri-inbox-line text-rose-300 text-2xl mb-2" />
            <p className="text-sm text-rose-400/80 max-w-md leading-relaxed mb-4" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              暂无正式种子提示词。请在加工任务中生成创作建议后，在「种子提示词」Tab 勾选并保存为正式内容。
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
                去加工任务
              </button>
            )}
          </div>
        ) : (
          <>
            <div
              className="inline-flex items-center gap-1 p-1 rounded-2xl mb-3"
              style={{
                background: "rgba(253,164,175,0.1)",
                border: "1px solid rgba(253,164,175,0.2)",
              }}
            >
              <button
                type="button"
                onClick={() => setSeedSubTab("character")}
                className="px-3 py-1.5 rounded-xl text-xs sm:text-sm transition-all cursor-pointer whitespace-nowrap"
                style={{
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                  background:
                    seedSubTab === "character"
                      ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                      : "transparent",
                  color: seedSubTab === "character" ? "white" : "#f472b6",
                  boxShadow: seedSubTab === "character" ? "0 2px 8px rgba(244,114,182,0.3)" : "none",
                }}
              >
                角色专属
                {officialSeeds && (
                  <span className="ml-1 opacity-80">({officialSeeds.characterSpecific.length})</span>
                )}
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
                {officialSeeds && <span className="ml-1 opacity-80">({officialSeeds.general.length})</span>}
              </button>
            </div>
            {seedSubTab === "character"
              ? seedList(officialSeeds!.characterSpecific, "characterSpecific")
              : seedList(officialSeeds!.general, "general")}
          </>
        )}
      </section>

      <section>
        <h3
          className="text-sm font-semibold text-rose-700/80 mb-3 flex items-center gap-1.5"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <i className="ri-contacts-line text-rose-400" />
          结构化档案字段
        </h3>
        <div
          className="rounded-2xl overflow-hidden border border-rose-100/80"
          style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.85) 0%, rgba(255,250,252,0.9) 100%)" }}
        >
          <dl className="divide-y divide-rose-100/60">
            {BIO_FIELDS.map(({ key, label }) => {
              const v = bio[key];
              if (typeof v !== "string") return null;
              return (
                <div key={key} className="grid grid-cols-[5rem_1fr] sm:grid-cols-[6.5rem_1fr] gap-2 px-4 py-3 text-sm">
                  <dt className="text-rose-400/80 font-medium shrink-0">{label}</dt>
                  <dd className="text-rose-800/85 leading-relaxed break-words">{v}</dd>
                </div>
              );
            })}
          </dl>
        </div>
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
    </div>
  );
};

export default OfficialContentTab;
