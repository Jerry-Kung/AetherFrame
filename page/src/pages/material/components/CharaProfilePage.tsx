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

/** 从结果页返回配置后写入，避免刷新时仍被已完成的任务拉回「仅结果」心智；重新 start 时会清除 */
const PROFILE_CONTINUE_CFG_KEY = (id: string) => `material_chara_profile_continue_config_${id}`;

function setProfileContinueConfigFlag(characterId: string, on: boolean) {
  try {
    if (on) window.sessionStorage.setItem(PROFILE_CONTINUE_CFG_KEY(characterId), "1");
    else window.sessionStorage.removeItem(PROFILE_CONTINUE_CFG_KEY(characterId));
  } catch {
    /* private mode */
  }
}

function isProfileContinueConfigFlagSet(characterId: string): boolean {
  try {
    return window.sessionStorage.getItem(PROFILE_CONTINUE_CFG_KEY(characterId)) === "1";
  } catch {
    return false;
  }
}

const PROFILE_STEP_LABELS: Record<string, string> = {
  text_understanding: "正在理解人设文本…",
  visual_official: "正在分析标准参考图…",
  visual_fanart: "正在分析同人立绘…",
  text_integration: "正在整合为小档案…",
  done: "即将完成…",
};

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

/* ── 创作建议占位动画（后端未接时仍用短时动画） ── */
const TimedGeneratingView = ({
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
              animation: `profileOrbit${i} 2s linear infinite`,
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
        @keyframes profileOrbit0 {
          0% { transform: translate(-50%, -50%) rotate(0deg) translateX(46px) rotate(0deg); }
          100% { transform: translate(-50%, -50%) rotate(360deg) translateX(46px) rotate(-360deg); }
        }
        @keyframes profileOrbit1 {
          0% { transform: translate(-50%, -50%) rotate(120deg) translateX(46px) rotate(-120deg); }
          100% { transform: translate(-50%, -50%) rotate(480deg) translateX(46px) rotate(-480deg); }
        }
        @keyframes profileOrbit2 {
          0% { transform: translate(-50%, -50%) rotate(240deg) translateX(46px) rotate(-240deg); }
          100% { transform: translate(-50%, -50%) rotate(600deg) translateX(46px) rotate(-600deg); }
        }
      `}</style>
    </div>
  );
};

/** 角色小档案：异步任务进行中 / 失败（轮询由父组件负责） */
const ProfileTaskGeneratingView = ({
  currentStep,
  errorMessage,
  onBackToConfig,
}: {
  currentStep: string | null;
  errorMessage: string | null;
  onBackToConfig: () => void;
}) => {
  if (errorMessage) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-8 text-center max-w-md mx-auto">
        <div
          className="rounded-xl px-4 py-3 text-sm text-rose-600 border border-rose-100 bg-rose-50/90 mb-6 w-full"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          {errorMessage}
        </div>
        <button
          type="button"
          onClick={onBackToConfig}
          className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all hover:opacity-90"
          style={{
            fontFamily: "'ZCOOL KuaiLe', cursive",
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            color: "white",
            boxShadow: "0 4px 14px rgba(244,114,182,0.3)",
          }}
        >
          <i className="ri-arrow-go-back-line"></i>
          返回配置
        </button>
      </div>
    );
  }

  const stepLabel =
    (currentStep && PROFILE_STEP_LABELS[currentStep]) || "任务已提交，正在排队处理…";

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
              animation: `profileOrbit${i} 2s linear infinite`,
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
        正在整理角色小档案～
      </h3>
      <p className="text-sm text-rose-500/80 leading-relaxed mb-1" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
        {stepLabel}
      </p>
      <p className="text-xs text-rose-400/60 leading-relaxed">
        多步推理可能需要数分钟，页面会自动刷新结果，请勿关闭标签页
      </p>
      <style>{`
        @keyframes profileOrbit0 {
          0% { transform: translate(-50%, -50%) rotate(0deg) translateX(46px) rotate(0deg); }
          100% { transform: translate(-50%, -50%) rotate(360deg) translateX(46px) rotate(-360deg); }
        }
        @keyframes profileOrbit1 {
          0% { transform: translate(-50%, -50%) rotate(120deg) translateX(46px) rotate(-120deg); }
          100% { transform: translate(-50%, -50%) rotate(480deg) translateX(46px) rotate(-480deg); }
        }
        @keyframes profileOrbit2 {
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
        <span className="text-xs text-rose-300/60">1–5 张（API 单次上限）</span>
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

type ProfilePhase = "hydrating" | "config" | "generating" | "done";

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
  const [profilePhase, setProfilePhase] = useState<ProfilePhase>("hydrating");
  const [hydrated, setHydrated] = useState(false);
  const [selectedFanartIds, setSelectedFanartIds] = useState<Set<string>>(new Set());
  const [profileText, setProfileText] = useState(chara.bio.charaProfile || "");
  const [pollError, setPollError] = useState<string | null>(null);
  const [loadingStart, setLoadingStart] = useState(false);
  const [taskStep, setTaskStep] = useState<string | null>(null);

  useEffect(() => {
    setProfileText(chara.bio.charaProfile || "");
  }, [chara.bio.charaProfile]);

  useEffect(() => {
    let cancelled = false;
    setHydrated(false);
    void (async () => {
      try {
        const status = await materialApi.getCharaProfileStatus(characterId);
        if (cancelled) return;
        setSelectedFanartIds(new Set(status.selected_fanart_ids || []));
        setPollError(null);
        if (status.status === "processing" || status.status === "pending") {
          setProfilePhase("generating");
          setTaskStep(status.current_step ?? null);
        } else if (status.status === "failed") {
          setProfilePhase("config");
          setPollError(status.error_message || "角色小档案生成失败");
        } else if (status.status === "completed") {
          if (isProfileContinueConfigFlagSet(characterId)) {
            setProfilePhase("config");
          } else if ((chara.bio.charaProfile || "").trim()) {
            setProfilePhase("done");
          } else {
            setProfilePhase("config");
          }
        } else {
          setProfilePhase("config");
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setProfilePhase("config");
          setPollError(null);
        } else {
          setProfilePhase("config");
          setPollError(e instanceof ApiError ? e.message : "加载任务状态失败");
        }
      } finally {
        if (!cancelled) setHydrated(true);
      }
    })();
    return () => {
      cancelled = true;
    };
    // chara.bio 仅用于首屏 completed 分支；不把 chara 放入 deps，避免详情刷新打断当前界面
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [characterId]);

  useEffect(() => {
    let alive = true;
    let timer: number | null = null;
    if (profilePhase !== "generating" || pollError) return;

    const poll = async () => {
      try {
        const status = await materialApi.getCharaProfileStatus(characterId);
        if (!alive) return;
        setTaskStep(status.current_step ?? null);
        if (status.status === "completed") {
          setProfileContinueConfigFlag(characterId, false);
          const detail = await materialApi.getCharacter(characterId);
          if (!alive) return;
          onCharacterUpdated(detail);
          const p = toCharaProfile(detail);
          setProfileText(p.bio.charaProfile || "");
          setProfilePhase("done");
          setPollError(null);
          showToast("角色小档案已生成");
          return;
        }
        if (status.status === "failed") {
          setPollError(status.error_message || "角色小档案生成失败");
          return;
        }
      } catch (e) {
        if (!alive) return;
        setPollError(e instanceof ApiError ? e.message : "获取任务状态失败");
        return;
      }
      timer = window.setTimeout(() => {
        void poll();
      }, 10000);
    };

    void poll();
    return () => {
      alive = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [characterId, profilePhase, pollError, onCharacterUpdated, showToast]);

  const toggleFanart = useCallback(
    (id: string) => {
      setSelectedFanartIds((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else {
          if (next.size >= 5) {
            showToast("最多选择 5 张同人立绘");
            return prev;
          }
          next.add(id);
        }
        return next;
      });
    },
    [showToast]
  );

  const runStartTask = useCallback(async () => {
    if (!characterId || characterId === "undefined" || characterId === "null") {
      showToast("当前角色ID无效，请重新选择角色后再试");
      return;
    }
    const ids = Array.from(selectedFanartIds);
    if (ids.length === 0) return;
    setLoadingStart(true);
    setPollError(null);
    setProfileContinueConfigFlag(characterId, false);
    try {
      await materialApi.startCharaProfileTask(characterId, { selected_fanart_ids: ids });
      setTaskStep(null);
      setProfilePhase("generating");
      showToast("任务已提交，正在生成角色小档案…");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "启动任务失败");
    } finally {
      setLoadingStart(false);
    }
  }, [characterId, selectedFanartIds, showToast]);

  const handleSave = useCallback(async () => {
    if (!characterId || characterId === "undefined" || characterId === "null") {
      showToast("当前角色ID无效，请重新选择角色后再试");
      return;
    }
    try {
      const detail = await materialApi.saveCharaProfile(characterId, profileText);
      onCharacterUpdated(detail);
      showToast("角色小档案已保存");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "保存角色小档案失败");
    }
  }, [characterId, profileText, onCharacterUpdated, showToast]);

  const handleRegenerate = useCallback(() => {
    if (selectedFanartIds.size === 0) {
      showToast("请先返回配置页选择同人立绘");
      setProfilePhase("config");
      return;
    }
    void runStartTask();
  }, [selectedFanartIds.size, runStartTask, showToast]);

  const handleBackToConfigFromDone = useCallback(() => {
    setProfileContinueConfigFlag(characterId, true);
    setProfilePhase("config");
    setPollError(null);
  }, [characterId]);

  const handleBackFromError = useCallback(() => {
    setPollError(null);
    setProfilePhase("config");
  }, []);

  if (!hydrated) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-6 text-rose-400 text-sm gap-2">
        <i className="ri-loader-4-line text-2xl animate-spin" aria-hidden />
        <span style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>加载任务状态…</span>
      </div>
    );
  }

  if (profilePhase === "generating") {
    return (
      <ProfileTaskGeneratingView
        currentStep={taskStep}
        errorMessage={pollError}
        onBackToConfig={pollError ? handleBackFromError : () => {}}
      />
    );
  }

  if (profilePhase === "done") {
    return (
      <div className="flex flex-col gap-4 p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
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
          <button
            type="button"
            onClick={handleBackToConfigFromDone}
            className="self-start sm:self-auto flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg cursor-pointer transition-all hover:opacity-85 whitespace-nowrap"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              background: "rgba(253,164,175,0.12)",
              color: "#db2777",
              border: "1px solid rgba(244,114,182,0.25)",
            }}
          >
            <i className="ri-settings-3-line"></i>
            返回配置重新提交
          </button>
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

      {pollError && (
        <div
          className="rounded-xl px-4 py-3 text-sm text-rose-600 border border-rose-100 bg-rose-50/90"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          {pollError}
        </div>
      )}

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
            type="button"
            onClick={() => setProfilePhase("done")}
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
        {!selectedFanartIds.size && (
          <p
            className="text-xs text-rose-400/50"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            先选择至少一张同人立绘，才能开始整理哦～
          </p>
        )}
        <button
          type="button"
          onClick={() => void runStartTask()}
          disabled={!selectedFanartIds.size || loadingStart}
          className="flex items-center gap-2.5 px-8 py-3.5 rounded-2xl text-base font-bold text-white cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            fontFamily: "'ZCOOL KuaiLe', cursive",
            background:
              selectedFanartIds.size && !loadingStart
                ? "linear-gradient(135deg, #fda4af 0%, #f472b6 50%, #ec4899 100%)"
                : "rgba(253,164,175,0.3)",
            boxShadow:
              selectedFanartIds.size && !loadingStart ? "0 6px 20px rgba(244,114,182,0.4)" : "none",
          }}
        >
          <div className="w-5 h-5 flex items-center justify-center">
            <i className="ri-id-card-fill text-lg"></i>
          </div>
          {loadingStart ? "提交中…" : chara.bio.charaProfile ? "重新整理角色小档案" : "开始整理角色小档案"}
          {!!selectedFanartIds.size && !loadingStart && (
            <span className="text-sm opacity-80">· {selectedFanartIds.size} 张同人立绘</span>
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
  const [genState, setGenState] = useState<GenState>("idle");
  const [adviceText, setAdviceText] = useState(chara.bio.creativeAdvice || "");

  useEffect(() => {
    setAdviceText(chara.bio.creativeAdvice || "");
  }, [chara.bio.creativeAdvice]);

  const handleStart = () => {
    setGenState("generating");
  };

  const handleGenDone = () => {
    setAdviceText(chara.bio.creativeAdvice || generateMockAdvice(chara.name));
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
    return <TimedGeneratingView label="正在整理角色创作建议～" onDone={handleGenDone} />;
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
      {chara.bio.creativeAdvice && (
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
        {chara.bio.creativeAdvice ? "重新整理创作建议" : "开始整理创作建议"}
      </button>
    </div>
  );
};

/* ── Mock（创作建议后端未接时） ── */
const generateMockAdvice = (name: string) =>
  `【角色创作建议 · ${name}】\n\n视觉创作方向\n· 根据角色配色和风格，建议使用协调的色调\n· 背景元素可参考角色的世界观设定\n\n场景创作建议\n· 日常场景：结合角色的日常习惯和爱好\n· 特殊场景：展现角色的独特能力和魅力\n\n性格表现技巧\n· 通过细节动作体现角色性格\n· 表情设计要符合角色的情感特征\n\n注意事项\n· 保持角色设定的一致性\n· 适当留白，给观者想象空间`;

/* ── Main component ── */
const CharaProfilePage = ({
  characterId,
  chara,
  onCharacterUpdated,
  showToast,
  onGoRaw,
  onGoPhoto,
}: CharaProfilePageProps) => {
  const { hasSettingText, hasOfficialImage, hasFanartImage, hasAllStandardPhotos } =
    checkPrerequisites(chara);

  const isUnlocked =
    hasSettingText && hasOfficialImage && hasFanartImage && hasAllStandardPhotos;

  const [activeStage, setActiveStage] = useState<StageTab>("profile");
  const [profileSaved, setProfileSaved] = useState(!!chara.bio.charaProfile?.trim());

  useEffect(() => {
    setProfileSaved(!!chara.bio.charaProfile?.trim());
  }, [chara.bio.charaProfile]);

  const handleSaveAdvice = useCallback(
    async (text: string) => {
      try {
        const d = await materialApi.saveCreativeAdvice(chara.id, text);
        onCharacterUpdated(d);
        showToast("创作建议已保存");
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "保存失败");
      }
    },
    [chara.id, onCharacterUpdated, showToast]
  );

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
          <ProfileStage
            chara={chara}
            characterId={characterId}
            onCharacterUpdated={onCharacterUpdated}
            showToast={showToast}
          />
        ) : (
          <AdviceStage
            chara={chara}
            profileUnlocked={profileSaved}
            onSave={(text) => void handleSaveAdvice(text)}
          />
        )}
      </div>
    </div>
  );
};

export default CharaProfilePage;
