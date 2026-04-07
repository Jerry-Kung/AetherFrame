import type { CharaBio } from "@/types/material";

interface OfficialContentTabProps {
  officialPhotos: [string | null, string | null, string | null];
  bio: CharaBio;
  onPhotoClick: (slotIndex: number) => void;
}

const PHOTO_LABELS = ["标准参考 1", "标准参考 2", "标准参考 3"] as const;

const BIO_FIELDS: { key: keyof CharaBio; label: string }[] = [
  { key: "displayName", label: "姓名" },
  { key: "age", label: "年龄" },
  { key: "height", label: "身高" },
  { key: "personality", label: "性格" },
  { key: "ability", label: "能力" },
  { key: "appearance", label: "外观" },
];

const OfficialContentTab = ({ officialPhotos, bio, onPhotoClick }: OfficialContentTabProps) => {
  return (
    <div className="flex flex-col gap-6 min-h-0 overflow-y-auto pr-1">
      <section>
        <h3
          className="text-sm font-semibold text-rose-700/80 mb-3 flex items-center gap-1.5"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <i className="ri-vip-crown-line text-rose-400" />
          标准参考照
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {officialPhotos.map((url, i) => (
            <button
              key={i}
              type="button"
              onClick={() => url && onPhotoClick(i)}
              className={[
                "relative aspect-[3/4] rounded-2xl overflow-hidden border transition-all text-left group",
                url
                  ? "border-rose-100/80 cursor-zoom-in hover:shadow-lg hover:border-pink-200"
                  : "border-dashed border-rose-200/70 bg-rose-50/40 cursor-default",
              ].join(" ")}
            >
              {url ? (
                <>
                  <img src={url} alt="" className="w-full h-full object-cover" draggable={false} />
                  <div className="absolute inset-x-0 bottom-0 py-1.5 px-2 bg-gradient-to-t from-black/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-[10px] text-white/90">{PHOTO_LABELS[i]} · 点击预览</span>
                  </div>
                </>
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-rose-300/70 text-xs gap-1">
                  <i className="ri-image-add-line text-2xl" />
                  <span>待生成</span>
                </div>
              )}
              <span className="absolute top-2 left-2 text-[10px] px-2 py-0.5 rounded-full bg-black/35 text-white/95 pointer-events-none">
                {PHOTO_LABELS[i]}
              </span>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h3
          className="text-sm font-semibold text-rose-700/80 mb-3 flex items-center gap-1.5"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <i className="ri-contacts-line text-rose-400" />
          角色小档案
        </h3>
        <div
          className="rounded-2xl overflow-hidden border border-rose-100/80"
          style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.85) 0%, rgba(255,250,252,0.9) 100%)" }}
        >
          <dl className="divide-y divide-rose-100/60">
            {BIO_FIELDS.map(({ key, label }) => (
              <div key={key} className="grid grid-cols-[5rem_1fr] sm:grid-cols-[6.5rem_1fr] gap-2 px-4 py-3 text-sm">
                <dt className="text-rose-400/80 font-medium shrink-0">{label}</dt>
                <dd className="text-rose-800/85 leading-relaxed break-words">{bio[key]}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
    </div>
  );
};

export default OfficialContentTab;
