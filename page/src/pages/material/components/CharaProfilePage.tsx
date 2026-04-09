import { useState, useCallback, useEffect } from "react";
import {
  type CharaProfile,
  type CharaRawImage,
  type ApiCharacterDetail,
  ALL_STANDARD_PHOTO_TYPES,
  STANDARD_PHOTO_LABELS,
} from "@/types/material";
import { toCharaProfile } from "@/types/material";
import * as materialApi from "@/services/materialApi";
import { ApiError } from "@/services/api";

interface CharaProfilePageProps {
  characterId: string;
  chara: CharaProfile;
  onCharacterUpdated: (detail: ApiCharacterDetail) => void;
  showToast: (msg: string) => void;
  onGoRaw: () => void;
  onGoPhoto: () => void;
}

type StageTab = "profile" | "advice";
type GenState = "idle" | "generating" | "done";

/* ── Prerequisite check helpers ── */
const checkPrerequisites = (chara: CharaProfile) => {
  const hasSettingText = chara.settingText.trim().length > 0;
  const hasOfficialImage = chara.rawImages.some((img) => img.type === "official");
  const hasFanartImage = chara.rawImages.some((img) => img.type === "fanart");
  const completedPhotoTypes = new Set(chara.standardPhotos.map((p) => p.type));
  const hasAllStandardPhotos = ALL_STANDARD_PHOTO_TYPES.every((t) =>
    completedPhotoTypes.has(t)
  );
  return { hasSettingText, hasOfficialImage, hasFanartImage, hasAllStandardPhotos };
};

/* ── Locked state card ── */
const LockedCard = ({
  chara,
  onGoRaw,
  onGoPhoto,
}: {
  chara: CharaProfile;
  onGoRaw: () => void;
  onGoPhoto: () => void;
}) => {
  const { hasSettingText, hasOfficialImage, hasFanartImage, hasAllStandardPhotos } =
    checkPrerequisites(chara);

  const completedPhotoTypes = new Set(chara.standardPhotos.map((p) => p.type));

  const checks = [
    {
      label: "已填写角色人设说明",
      done: hasSettingText,
      action: onGoRaw,
      actionLabel: "去填写",
    },
    {
      label: "已上传至少 1 张官方形象图",
      done: hasOfficialImage,
      action: onGoRaw,
      actionLabel: "去上传",
    },
    {
      label: "已上传至少 1 张同人立绘图",
      done: hasFanartImage,
      action: onGoRaw,
      actionLabel: "去上传",
    },
    {
      label: "已完成全部 5 种标准参考照",
      done: hasAllStandardPhotos,
      action: onGoPhoto,
      actionLabel: "去拍摄",
      sub: ALL_STANDARD_PHOTO_TYPES.map((t) => ({
        label: STANDARD_PHOTO_LABELS[t],
        done: completedPhotoTypes.has(t),
      })),
    },
  ];

  const doneCount = checks.filter((c) => c.done).length;

  return (
    <div className="flex flex-col items-center justify-center h-full py-10 px-6">
      <div className="w-full max-w-md">
        {/* Lock icon */}
        <div className="flex flex-col items-center mb-7">
          <div
            className="w-16 h-16 flex items-center justify-center rounded-3xl mb-4"
            style={{
              background:
                "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
              border: "1.5px dashed rgba(244,114,182,0.3)",
            }}
          >
            <i className="ri-lock-2-line text-rose-300 text-3xl"></i>
          </div>
          <h3
            className="text-base font-bold text-rose-500 mb-1"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            还差一点点就能解锁啦～
          </h3>
          <p className="text-xs text-rose-400/60 text-center leading-relaxed">
            完成下面的准备工作，角色小档案就会向你敞开大门
          </p>
          {/* Progress bar */}
          <div className="w-48 mt-4">
            <div className="flex items-center justify-between mb-1.5">
              <span
                className="text-xs text-rose-400/60"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                准备进度
              </span>
              <span
                className="text-xs font-bold text-rose-500"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                {doneCount} / {checks.length}
              </span>
            </div>
            <div
              className="h-2 rounded-full overflow-hidden"
              style={{ background: "rgba(253,164,175,0.15)" }}
            >
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(doneCount / checks.length) * 100}%`,
                  background:
                    "linear-gradient(90deg, #fda4af 0%, #f472b6 100%)",
                }}
              />
            </div>
          </div>
        </div>

        {/* Checklist */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            border: "1px solid rgba(253,164,175,0.2)",
            background: "rgba(255,255,255,0.7)",
          }}
        >
          {checks.map((item, idx) => (
            <div key={idx}>
              {idx > 0 && (
                <div className="h-px mx-4" style={{ background: "rgba(253,164,175,0.12)" }} />
              )}
              <div className="flex items-start gap-3 px-4 py-3.5">
                {/* Check icon */}
                <div
                  className="w-5 h-5 flex items-center justify-center rounded-full shrink-0 mt-0.5"
                  style={{
                    background: item.done
                      ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                      : "rgba(253,164,175,0.12)",
                    border: item.done ? "none" : "1.5px solid rgba(253,164,175,0.3)",
                  }}
                >
                  {item.done ? (
                    <i className="ri-check-line text-white text-xs"></i>
                  ) : (
                    <i className="ri-circle-line text-rose-300 text-xs"></i>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className="text-sm"
                      style={{
                        color: item.done ? "#f472b6" : "#fda4af",
                        fontFamily: "'ZCOOL KuaiLe', cursive",
                        textDecoration: item.done ? "none" : "none",
                        opacity: item.done ? 1 : 0.8,
                      }}
                    >
                      {item.label}
                    </span>
                    {!item.done && (
                      <button
                        onClick={item.action}
                        className="shrink-0 text-xs px-2.5 py-1 rounded-lg cursor-pointer transition-all duration-200 whitespace-nowrap hover:opacity-80"
                        style={{
                          background:
                            "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
                          color: "#f472b6",
                          border: "1px solid rgba(244,114,182,0.2)",
                          fontFamily: "'ZCOOL KuaiLe', cursive",
                        }}
                      >
                        {item.actionLabel}
                      </button>
                    )}
                  </div>

                  {/* Sub-items for standard photos */}
                  {item.sub && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {item.sub.map((s) => (
                        <span
                          key={s.label}
                          className="text-xs px-2 py-0.5 rounded-full"
                          style={{
                            background: s.done
                              ? "rgba(244,114,182,0.1)"
                              : "rgba(253,164,175,0.06)",
                            color: s.done ? "#f472b6" : "#fda4af",
                            border: s.done
                              ? "1px solid rgba(244,114,182,0.25)"
                              : "1px solid rgba(253,164,175,0.15)",
                            fontFamily: "'ZCOOL KuaiLe', cursive",
                          }}
                        >
                          {s.done ? (
                            <><i className="ri-check-line mr-0.5"></i>{s.label}</>
                          ) : (
                            s.label
                          )}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Hint */}
        <p
          className="text-center text-xs text-rose-300/50 mt-4"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          完成所有准备后，这里会自动解锁，不用刷新页面哦 ✨
        </p>
      </div>
    </div>
  );
};

/* ── Generating animation ── */
const GeneratingView = ({
  label,
  onDone,
}: {
  label: string;
  onDone: () => void;
}) => {
  useEffect(() => {
    const timer = setTimeout(onDone, 2800);
    return () => clearTimeout(timer);
  }, [onDone]);

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
          <i className="ri-quill-pen-line text-rose-400 text-3xl"></i>
        </div>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="absolute w-2.5 h-2.5 flex items-center justify-center text-pink-400"
            style={{
              top: "50%",
              left: "50%",
              animation: `orbit${i} 2s linear infinite`,
              animationDelay: `${i * 0.66}s`,
            }}
          >
            <i className="ri-star-fill text-xs"></i>
          </div>
        ))}
      </div>
      <h3
        className="text-base font-bold text-rose-600 mb-2"
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        {label}
      </h3>
      <p className="text-sm text-rose-400/60 leading-relaxed">
        AI 正在认真阅读角色资料，马上就好，请稍等一下下 ✨
      </p>
      <style>{`
        @keyframes orbit0 {
          0% { transform: translate(-50%, -50%) rotate(0deg) translateX(46px) rotate(0deg); }
          100% { transform: translate(-50%, -50%) rotate(360deg) translateX(46px) rotate(-360deg); }
        }
        @keyframes orbit1 {
          0% { transform: translate(-50%, -50%) rotate(120deg) translateX(46px) rotate(-120deg); }
          100% { transform: translate(-50%, -50%) rotate(480deg) translateX(46px) rotate(-480deg); }
        }
        @keyframes orbit2 {
          0% { transform: translate(-50%, -50%) rotate(240deg) translateX(46px) rotate(-240deg); }
          100% { transform: translate(-50%, -50%) rotate(600deg) translateX(46px) rotate(-600deg); }
        }
      `}</style>
    </div>
  );
};

/* ── Fanart image selector ── */
const FanartSelector = ({
  fanartImages,
  selectedIds,
  onToggle,
}: {
  fanartImages: CharaRawImage[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
}) => (
  <div
    className="rounded-2xl overflow-hidden"
    style={{
      border: "1px solid rgba(253,164,175,0.25)",
      background: "rgba(255,255,255,0.7)",
    }}
  >
    <div className="flex items-center justify-between px-4 py-3 border-b border-rose-100/40">
      <div className="flex items-center gap-2">
        <div
          className="w-6 h-6 rounded-lg flex items-center justify-center text-white text-xs"
          style={{
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
          }}
        >
          <i className="ri-palette-line text-xs"></i>
        </div>
        <span
          className="text-sm font-bold text-rose-600"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          选择同人立绘参考
        </span>
        <span className="text-xs text-rose-300/60">至少选 1 张</span>
      </div>
      {selectedIds.size > 0 && (
        <span
          className="text-xs px-2.5 py-0.5 rounded-full text-white"
          style={{
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            fontFamily: "'ZCOOL KuaiLe', cursive",
          }}
        >
          已选 {selectedIds.size} 张
        </span>
      )}
    </div>
    <div className="p-4">
      {fanartImages.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <i className="ri-image-line text-rose-200 text-2xl mb-2"></i>
          <p
            className="text-sm text-rose-300/60"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            还没有同人立绘，先去「原始资料」上传吧～
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 gap-2.5">
          {fanartImages.map((img) => {
            const isSelected = selectedIds.has(img.id);
            return (
              <div
                key={img.id}
                className="relative rounded-xl overflow-hidden cursor-pointer transition-all duration-200 group"
                style={{
                  aspectRatio: "1",
                  border: isSelected
                    ? "2.5px solid #a78bfa"
                    : "1.5px solid rgba(196,181,253,0.25)",
                  boxShadow: isSelected
                    ? "0 0 0 3px rgba(167,139,250,0.18)"
                    : "none",
                }}
                onClick={() => onToggle(img.id)}
              >
                <img
                  src={img.url}
                  alt="同人立绘"
                  className="w-full h-full object-cover object-top transition-transform duration-200 group-hover:scale-105"
                />
                {isSelected && (
                  <div
                    className="absolute inset-0 flex items-start justify-end p-1"
                    style={{ background: "rgba(167,139,250,0.15)" }}
                  >
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center text-white text-xs"
                      style={{
                        background:
                          "linear-gradient(135deg, #c4b5fd 0%, #a78bfa 100%)",
                      }}
                    >
                      <i className="ri-check-line text-xs"></i>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  </div>
);

/* ── Auto-included info card ── */
const AutoIncludedCard = ({ chara }: { chara: CharaProfile }) => (
  <div
    className="rounded-2xl overflow-hidden"
    style={{
      border: "1px solid rgba(253,164,175,0.2)",
      background:
        "linear-gradient(135deg, rgba(253,164,175,0.06) 0%, rgba(244,114,182,0.04) 100%)",
    }}
  >
    <div className="flex items-center gap-2 px-4 py-3 border-b border-rose-100/30">
      <div className="w-5 h-5 flex items-center justify-center">
        <i className="ri-magic-line text-rose-400 text-sm"></i>
      </div>
      <span
        className="text-sm font-bold text-rose-500"
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        已自动带入的资料
      </span>
      <span className="text-xs text-rose-300/60">无需手动选择</span>
    </div>
    <div className="p-4 flex flex-wrap gap-2">
      <div
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs"
        style={{
          background: "rgba(253,164,175,0.1)",
          border: "1px solid rgba(253,164,175,0.2)",
          color: "#f472b6",
          fontFamily: "'ZCOOL KuaiLe', cursive",
        }}
      >
        <i className="ri-file-text-line text-xs"></i>
        角色人设说明
        <span className="opacity-60">· 已带入</span>
      </div>
      {ALL_STANDARD_PHOTO_TYPES.map((t) => (
        <div
          key={t}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs"
          style={{
            background: "rgba(253,164,175,0.1)",
            border: "1px solid rgba(253,164,175,0.2)",
            color: "#f472b6",
            fontFamily: "'ZCOOL KuaiLe', cursive",
          }}
        >
          <i className="ri-camera-line text-xs"></i>
          {STANDARD_PHOTO_LABELS[t]}
          <span className="opacity-60">· 已带入</span>
        </div>
      ))}
    </div>
  </div>
);

/* ── Editable text result ── */
const EditableResult = ({
  value,
  onChange,
  onSave,
  onRegenerate,
  saveLabel,
  savedLabel,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  onSave: () => void;
  onRegenerate: () => void;
  saveLabel: string;
  savedLabel: string;
  placeholder: string;
}) => {
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    onSave();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="flex flex-col gap-3">
      <textarea
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setSaved(false);
        }}
        placeholder={placeholder}
        rows={14}
        className="w-full resize-none rounded-2xl text-sm leading-relaxed outline-none transition-all duration-200"
        style={{
          background: "rgba(255,255,255,0.8)",
          border: "1.5px solid rgba(253,164,175,0.25)",
          color: "#7c3f5e",
          padding: "16px",
          fontFamily: "inherit",
        }}
        onFocus={(e) => {
          e.currentTarget.style.border = "1.5px solid rgba(244,114,182,0.45)";
          e.currentTarget.style.boxShadow = "0 0 0 3px rgba(244,114,182,0.08)";
        }}
        onBlur={(e) => {
          e.currentTarget.style.border = "1.5px solid rgba(253,164,175,0.25)";
          e.currentTarget.style.boxShadow = "none";
        }}
      />
      <div className="flex items-center justify-between">
        <button
          onClick={onRegenerate}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap hover:bg-rose-50"
          style={{
            color: "#f472b6",
            border: "1px solid rgba(244,114,182,0.2)",
            fontFamily: "'ZCOOL KuaiLe', cursive",
          }}
        >
          <i className="ri-refresh-line text-sm"></i>
          重新生成
        </button>

        {saved ? (
          <div
            className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm"
            style={{
              background:
                "linear-gradient(135deg, rgba(167,243,208,0.3) 0%, rgba(110,231,183,0.2) 100%)",
              border: "1px solid rgba(110,231,183,0.3)",
              color: "#059669",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            <i className="ri-checkbox-circle-fill text-sm"></i>
            {savedLabel}
          </div>
        ) : (
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-medium text-white cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background:
                "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              boxShadow: "0 4px 14px rgba(244,114,182,0.3)",
            }}
          >
            <i className="ri-save-line text-sm"></i>
            {saveLabel}
          </button>
        )}
      </div>
    </div>
  );
};

/* ── Stage 1: Profile ── */
const ProfileStage = ({
  chara,
  characterId,
  onCharacterUpdated,
  showToast,
}: {
  chara: CharaProfile;
  characterId: string;
  onCharacterUpdated: (detail: ApiCharacterDetail) => void;
  showToast: (msg: string) => void;
}) => {
  const fanartImages = chara.rawImages.filter((img) => img.type === "fanart");
  const [selectedFanartIds, setSelectedFanartIds] = useState<Set<string>>(new Set());
  const [genState, setGenState] = useState<GenState>("idle");
  const [profileText, setProfileText] = useState(chara.bio.charaProfile || "");

  const toggleFanart = useCallback((id: string) => {
    setSelectedFanartIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const canStart = selectedFanartIds.size > 0;

  const handleStart = () => {
    setGenState("generating");
  };

  const handleGenDone = useCallback(async () => {
    try {
      const detail = await materialApi.saveCharaProfile(characterId, profileText || generateMockProfile(chara.name));
      onCharacterUpdated(detail);
      setGenState("done");
      showToast("角色小档案已生成");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "生成角色小档案失败");
      setGenState("idle");
    }
  }, [characterId, chara.name, profileText, onCharacterUpdated, showToast]);

  const handleSave = useCallback(async () => {
    try {
      const detail = await materialApi.saveCharaProfile(characterId, profileText);
      onCharacterUpdated(detail);
      showToast("角色小档案已保存");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "保存角色小档案失败");
    }
  }, [characterId, profileText, onCharacterUpdated, showToast]);

  const handleRegenerate = useCallback(() => {
    setGenState("generating");
  }, []);

  if (genState === "generating") {
    return <GeneratingView label="正在整理角色小档案～" onDone={handleGenDone} />;
  }

  if (genState === "done") {
    return (
      <div className="flex flex-col gap-4 p-5">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            }}
          >
            <i className="ri-checkbox-circle-fill text-white text-xs"></i>
          </div>
          <span
            className="text-sm font-bold text-rose-600"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            角色小档案已生成，可以继续修改哦～
          </span>
        </div>
        <EditableResult
          value={profileText}
          onChange={setProfileText}
          onSave={handleSave}
          onRegenerate={handleRegenerate}
          saveLabel="保存小档案"
          savedLabel="小档案已保存！"
          placeholder="角色小档案内容..."
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-5">
      <AutoIncludedCard chara={chara} />

      {chara.bio.charaProfile && (
        <div
          className="flex items-center justify-between px-4 py-3 rounded-2xl"
          style={{
            background: "linear-gradient(135deg, rgba(167,243,208,0.15) 0%, rgba(110,231,183,0.1) 100%)",
            border: "1px solid rgba(110,231,183,0.25)",
          }}
        >
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 flex items-center justify-center">
              <i className="ri-checkbox-circle-fill text-emerald-500 text-sm"></i>
            </div>
            <span
              className="text-sm text-emerald-600"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              已有保存的小档案，重新生成会覆盖哦
            </span>
          </div>
          <button
            onClick={() => setGenState("done")}
            className="text-xs px-3 py-1 rounded-lg cursor-pointer whitespace-nowrap transition-all hover:opacity-80"
            style={{
              background: "rgba(110,231,183,0.15)",
              color: "#059669",
              border: "1px solid rgba(110,231,183,0.3)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            查看已保存内容
          </button>
        </div>
      )}

      <FanartSelector
        fanartImages={fanartImages}
        selectedIds={selectedFanartIds}
        onToggle={toggleFanart}
      />

      <div className="flex flex-col items-center gap-2 pb-2">
        {!canStart && (
          <p
            className="text-xs text-rose-400/50"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            先选择至少一张同人立绘，才能开始整理哦～
          </p>
        )}
        <button
          onClick={handleStart}
          disabled={!canStart}
          className="flex items-center gap-2.5 px-8 py-3.5 rounded-2xl text-base font-bold text-white cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            fontFamily: "'ZCOOL KuaiLe', cursive",
            background: canStart
              ? "linear-gradient(135deg, #fda4af 0%, #f472b6 50%, #ec4899 100%)"
              : "rgba(253,164,175,0.3)",
            boxShadow: canStart ? "0 6px 20px rgba(244,114,182,0.4)" : "none",
          }}
        >
          <div className="w-5 h-5 flex items-center justify-center">
            <i className="ri-id-card-fill text-lg"></i>
          </div>
          {chara.bio.charaProfile ? "重新整理角色小档案" : "开始整理角色小档案"}
          {canStart && (
            <span className="text-sm opacity-80">
              · {selectedFanartIds.size} 张同人立绘
            </span>
          )}
        </button>
      </div>
    </div>
  );
};

/* ── Stage 2: Creative advice ── */
const AdviceStage = ({
  chara,
  profileUnlocked,
  onSave,
}: {
  chara: CharaProfile;
  profileUnlocked: boolean;
  onSave: (text: string) => void;
}) => {
  // Always start from idle so user sees the start button first
  const [genState, setGenState] = useState<GenState>("idle");
  const [adviceText, setAdviceText] = useState(chara.creativeAdvice);

  const handleStart = () => {
    setGenState("generating");
  };

  const handleGenDone = () => {
    setAdviceText(chara.creativeAdvice || generateMockAdvice(chara.name));
    setGenState("done");
  };

  const handleRegenerate = () => {
    setGenState("generating");
  };

  if (!profileUnlocked) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
        <div
          className="w-14 h-14 flex items-center justify-center rounded-2xl mb-4 opacity-50"
          style={{
            background:
              "linear-gradient(135deg, rgba(253,164,175,0.12) 0%, rgba(244,114,182,0.08) 100%)",
            border: "1.5px dashed rgba(244,114,182,0.2)",
          }}
        >
          <i className="ri-lock-2-line text-rose-300 text-2xl"></i>
        </div>
        <h3
          className="text-sm font-bold text-rose-400/60 mb-2"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          先完成角色小档案吧～
        </h3>
        <p className="text-xs text-rose-300/50 leading-relaxed max-w-xs">
          角色小档案生成并保存后，创作建议就会自动解锁，让 AI 基于完整档案给出更精准的建议
        </p>
      </div>
    );
  }

  if (genState === "generating") {
    return <GeneratingView label="正在整理角色创作建议～" onDone={handleGenDone} />;
  }

  if (genState === "done") {
    return (
      <div className="flex flex-col gap-4 p-5">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            }}
          >
            <i className="ri-checkbox-circle-fill text-white text-xs"></i>
          </div>
          <span
            className="text-sm font-bold text-rose-600"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            创作建议已生成，可以继续修改哦～
          </span>
        </div>
        <EditableResult
          value={adviceText}
          onChange={setAdviceText}
          onSave={() => onSave(adviceText)}
          onRegenerate={handleRegenerate}
          saveLabel="保存创作建议"
          savedLabel="创作建议已保存！"
          placeholder="角色创作建议内容..."
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-12 px-8 text-center">
      <div
        className="w-16 h-16 flex items-center justify-center rounded-3xl mb-5"
        style={{
          background:
            "linear-gradient(135deg, rgba(253,164,175,0.15) 0%, rgba(244,114,182,0.1) 100%)",
          border: "1.5px solid rgba(244,114,182,0.2)",
        }}
      >
        <i className="ri-lightbulb-line text-rose-400 text-2xl"></i>
      </div>
      <h3
        className="text-base font-bold text-rose-600 mb-2"
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        准备好了！
      </h3>
      <p className="text-sm text-rose-400/60 leading-relaxed mb-6 max-w-xs">
        AI 将基于角色小档案，为你整理出视觉创作方向、场景建议和性格表现技巧
      </p>

      {/* Already-saved hint */}
      {chara.creativeAdvice && (
        <div
          className="flex items-center justify-between px-4 py-3 rounded-2xl mb-5 w-full max-w-sm"
          style={{
            background: "linear-gradient(135deg, rgba(167,243,208,0.15) 0%, rgba(110,231,183,0.1) 100%)",
            border: "1px solid rgba(110,231,183,0.25)",
          }}
        >
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 flex items-center justify-center">
              <i className="ri-checkbox-circle-fill text-emerald-500 text-sm"></i>
            </div>
            <span
              className="text-sm text-emerald-600"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              已有保存的创作建议
            </span>
          </div>
          <button
            onClick={() => setGenState("done")}
            className="text-xs px-3 py-1 rounded-lg cursor-pointer whitespace-nowrap transition-all hover:opacity-80"
            style={{
              background: "rgba(110,231,183,0.15)",
              color: "#059669",
              border: "1px solid rgba(110,231,183,0.3)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            查看已保存内容
          </button>
        </div>
      )}

      <button
        onClick={handleStart}
        className="flex items-center gap-2.5 px-8 py-3.5 rounded-2xl text-base font-bold text-white cursor-pointer transition-all duration-200 whitespace-nowrap"
        style={{
          fontFamily: "'ZCOOL KuaiLe', cursive",
          background:
            "linear-gradient(135deg, #fda4af 0%, #f472b6 50%, #ec4899 100%)",
          boxShadow: "0 6px 20px rgba(244,114,182,0.4)",
        }}
      >
        <div className="w-5 h-5 flex items-center justify-center">
          <i className="ri-lightbulb-fill text-lg"></i>
        </div>
        {chara.creativeAdvice ? "重新整理创作建议" : "开始整理创作建议"}
      </button>
    </div>
  );
};

/* ── Mock text generators ── */
const generateMockProfile = (name: string) =>
  `【角色小档案 · ${name}】\n\n基本信息\n姓名：${name}\n年龄：待补充\n身高：待补充\n\n外观特征\n（根据参考图自动提取）\n\n性格特征\n（根据人设说明自动整理）\n\n能力设定\n（根据人设说明自动整理）\n\n爱好与日常\n（根据人设说明自动整理）`;

const generateMockAdvice = (name: string) =>
  `【角色创作建议 · ${name}】\n\n视觉创作方向\n· 根据角色配色和风格，建议使用协调的色调\n· 背景元素可参考角色的世界观设定\n\n场景创作建议\n· 日常场景：结合角色的日常习惯和爱好\n· 特殊场景：展现角色的独特能力和魅力\n\n性格表现技巧\n· 通过细节动作体现角色性格\n· 表情设计要符合角色的情感特征\n\n注意事项\n· 保持角色设定的一致性\n· 适当留白，给观者想象空间`;

/* ── Main component ── */
const CharaProfilePage = ({
  chara,
  onSaveProfile,
  onSaveAdvice,
  onGoRaw,
  onGoPhoto,
}: CharaProfilePageProps) => {
  const { hasSettingText, hasOfficialImage, hasFanartImage, hasAllStandardPhotos } =
    checkPrerequisites(chara);

  const isUnlocked =
    hasSettingText && hasOfficialImage && hasFanartImage && hasAllStandardPhotos;

  const [activeStage, setActiveStage] = useState<StageTab>("profile");
  const [profileSaved, setProfileSaved] = useState(!!chara.charaProfile);

  const handleSaveProfile = (text: string) => {
    onSaveProfile(text);
    setProfileSaved(true);
  };

  if (!isUnlocked) {
    return (
      <LockedCard chara={chara} onGoRaw={onGoRaw} onGoPhoto={onGoPhoto} />
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Stage tab bar */}
      <div className="px-5 pt-4 pb-0 shrink-0">
        <div
          className="inline-flex items-center gap-1 p-1 rounded-2xl"
          style={{
            background: "rgba(253,164,175,0.1)",
            border: "1px solid rgba(253,164,175,0.2)",
          }}
        >
          {/* Stage 1 */}
          <button
            onClick={() => setActiveStage("profile")}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              background:
                activeStage === "profile"
                  ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                  : "transparent",
              color: activeStage === "profile" ? "white" : "#f472b6",
              boxShadow:
                activeStage === "profile"
                  ? "0 2px 8px rgba(244,114,182,0.3)"
                  : "none",
            }}
          >
            <div className="w-4 h-4 flex items-center justify-center">
              <i className="ri-id-card-line text-sm"></i>
            </div>
            生成角色小档案
            {profileSaved && (
              <span
                className="ml-1 text-xs px-1.5 py-0.5 rounded-full"
                style={{
                  background:
                    activeStage === "profile"
                      ? "rgba(255,255,255,0.25)"
                      : "rgba(244,114,182,0.12)",
                  color: activeStage === "profile" ? "white" : "#f472b6",
                }}
              >
                ✓
              </span>
            )}
          </button>

          {/* Stage 2 */}
          <button
            onClick={() => profileSaved && setActiveStage("advice")}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm transition-all duration-200 whitespace-nowrap"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              background:
                activeStage === "advice"
                  ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                  : "transparent",
              color:
                activeStage === "advice"
                  ? "white"
                  : profileSaved
                  ? "#f472b6"
                  : "rgba(244,114,182,0.35)",
              boxShadow:
                activeStage === "advice"
                  ? "0 2px 8px rgba(244,114,182,0.3)"
                  : "none",
              cursor: profileSaved ? "pointer" : "not-allowed",
            }}
          >
            <div className="w-4 h-4 flex items-center justify-center">
              {profileSaved ? (
                <i className="ri-lightbulb-line text-sm"></i>
              ) : (
                <i className="ri-lock-2-line text-sm"></i>
              )}
            </div>
            生成创作建议
          </button>
        </div>

        {!profileSaved && activeStage === "profile" && (
          <p
            className="text-xs text-rose-400/50 mt-2 ml-1"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            保存角色小档案后，创作建议将自动解锁
          </p>
        )}

        <div className="mt-3 h-px bg-rose-100/40" />
      </div>

      {/* Stage content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeStage === "profile" ? (
          <ProfileStage chara={chara} onSave={handleSaveProfile} />
        ) : (
          <AdviceStage
            chara={chara}
            profileUnlocked={profileSaved}
            onSave={onSaveAdvice}
          />
        )}
      </div>
    </div>
  );
};

export default CharaProfilePage;
