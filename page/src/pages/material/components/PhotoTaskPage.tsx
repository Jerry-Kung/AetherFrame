import { useCallback, useEffect, useMemo, useState } from "react";
import type { CharaRawImage, RawImageType } from "@/types/material";
import type { ApiCharacterDetail } from "@/types/material";
import { ApiError } from "@/services/api";
import * as materialApi from "@/services/materialApi";

interface PhotoTaskPageProps {
  characterId: string;
  rawImages: CharaRawImage[];
  onCharacterUpdated: (detail: ApiCharacterDetail) => void;
  showToast: (msg: string) => void;
}

type ShotType = "full_front" | "full_side" | "half_front" | "half_side" | "face_close";
type AspectRatio = "16:9" | "1:1" | "9:16";
type GenCount = 1 | 2 | 4;
type PageState = "config" | "generating" | "result";

const SHOT_TYPES: { id: ShotType; label: string; icon: string; desc: string }[] = [
  { id: "full_front", label: "全身正面", icon: "ri-user-line", desc: "完整全身，正面站姿" },
  { id: "full_side", label: "全身侧面", icon: "ri-user-follow-line", desc: "完整全身，侧面展示" },
  { id: "half_front", label: "半身正面", icon: "ri-user-smile-line", desc: "腰部以上，正面构图" },
  { id: "half_side", label: "半身侧面", icon: "ri-user-star-line", desc: "腰部以上，侧面构图" },
  { id: "face_close", label: "脸部特写", icon: "ri-emotion-line", desc: "面部细节，表情特写" },
];

const ASPECT_RATIOS: { value: AspectRatio; label: string }[] = [
  { value: "16:9", label: "16:9" },
  { value: "1:1", label: "1:1" },
  { value: "9:16", label: "9:16" },
];

const GEN_COUNTS: { value: GenCount; label: string }[] = [
  { value: 1, label: "1 张" },
  { value: 2, label: "2 张" },
  { value: 4, label: "4 张" },
];

const RAW_TYPE_CONFIG: Record<
  RawImageType,
  {
    label: string;
    icon: string;
    accentBg: string;
    accentText: string;
    normalBorder: string;
    selectedBorder: string;
    selectedGlow: string;
    selectedOverlay: string;
  }
> = {
  official: {
    label: "官方形象",
    icon: "ri-award-line",
    accentBg: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
    accentText: "#f472b6",
    normalBorder: "1.5px solid rgba(253,164,175,0.2)",
    selectedBorder: "2.5px solid #f472b6",
    selectedGlow: "0 0 0 3px rgba(244,114,182,0.15)",
    selectedOverlay: "rgba(244,114,182,0.15)",
  },
  fanart: {
    label: "同人立绘",
    icon: "ri-palette-line",
    accentBg: "linear-gradient(135deg, #c4b5fd 0%, #8b5cf6 100%)",
    accentText: "#8b5cf6",
    normalBorder: "1.5px solid rgba(196,181,253,0.28)",
    selectedBorder: "2.5px solid #8b5cf6",
    selectedGlow: "0 0 0 3px rgba(139,92,246,0.18)",
    selectedOverlay: "rgba(139,92,246,0.15)",
  },
};

const RatioPreview = ({ ratio }: { ratio: AspectRatio }) => {
  const map: Record<AspectRatio, string> = {
    "16:9": "w-10 h-[22px]",
    "1:1": "w-7 h-7",
    "9:16": "w-[22px] h-10",
  };
  return <div className={`${map[ratio]} rounded border-2 border-current opacity-70`} />;
};

const GeneratingView = ({ errorMessage }: { errorMessage: string | null }) => {
  return (
    <div className="flex flex-col items-center justify-center h-full py-12 px-8 text-center">
      <div className="relative mb-8">
        <div
          className="w-24 h-24 rounded-3xl flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, rgba(253,164,175,0.2) 0%, rgba(244,114,182,0.15) 100%)",
            border: "2px solid rgba(244,114,182,0.25)",
            animation: "pulse 1.5s ease-in-out infinite",
          }}
        >
          <i className="ri-camera-line text-rose-400 text-4xl" />
        </div>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="absolute w-3 h-3 flex items-center justify-center text-pink-400"
            style={{
              top: "50%",
              left: "50%",
              animation: `orbit${i} 2s linear infinite`,
              animationDelay: `${i * 0.66}s`,
            }}
          >
            <i className="ri-star-fill text-xs" />
          </div>
        ))}
      </div>

      <h3 className="text-lg font-bold text-rose-600 mb-2" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
        正在为她拍摄标准照～
      </h3>
      <p className="text-sm text-rose-400/60 mb-8 leading-relaxed">
        AI 正在认真研究参考图，
        <br />
        马上就好，请稍等一下下 ✨
      </p>
      {errorMessage && (
        <p className="text-xs text-rose-500 bg-rose-50 rounded-lg px-3 py-2 border border-rose-100">
          {errorMessage}
        </p>
      )}

      <style>{`
        @keyframes orbit0 {
          0% { transform: translate(-50%, -50%) rotate(0deg) translateX(52px) rotate(0deg); }
          100% { transform: translate(-50%, -50%) rotate(360deg) translateX(52px) rotate(-360deg); }
        }
        @keyframes orbit1 {
          0% { transform: translate(-50%, -50%) rotate(120deg) translateX(52px) rotate(-120deg); }
          100% { transform: translate(-50%, -50%) rotate(480deg) translateX(52px) rotate(-480deg); }
        }
        @keyframes orbit2 {
          0% { transform: translate(-50%, -50%) rotate(240deg) translateX(52px) rotate(-240deg); }
          100% { transform: translate(-50%, -50%) rotate(600deg) translateX(52px) rotate(-600deg); }
        }
      `}</style>
    </div>
  );
};

const ResultView = ({
  images,
  isSaving,
  onSave,
  onRetry,
  saveSuccess,
}: {
  images: string[];
  isSaving: boolean;
  onSave: (url: string) => void;
  onRetry: () => void;
  saveSuccess: boolean;
}) => {
  const [selected, setSelected] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const displayImages = images;

  const handleSave = () => {
    if (!selected) return;
    onSave(selected);
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-5 py-3 border-b border-rose-100/40 shrink-0">
        <div className="flex items-center gap-2">
          <i className="ri-gallery-line text-rose-400 text-sm" />
          <span className="text-sm font-bold text-rose-600" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
            拍摄结果 · 选一张最满意的吧！
          </span>
          <span className="text-xs text-rose-300/60 bg-rose-50 px-2 py-0.5 rounded-full">共 {images.length} 张候选</span>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs cursor-pointer transition-all duration-200 whitespace-nowrap hover:bg-rose-50"
          style={{ color: "#f472b6", fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <i className="ri-refresh-line text-xs" />
          重新拍摄
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-4xl mx-auto">
          {displayImages.map((url, i) => {
            const isSelected = selected === url;
            return (
              <div
                key={url}
                className="relative rounded-2xl overflow-hidden cursor-pointer group transition-all duration-200"
                style={{
                  border: isSelected ? "2.5px solid #f472b6" : "2px solid rgba(253,164,175,0.2)",
                  boxShadow: isSelected ? "0 0 0 3px rgba(244,114,182,0.15)" : "none",
                  aspectRatio: "3/4",
                }}
                onClick={() => setSelected(isSelected ? null : url)}
              >
                <img src={url} alt={`候选图 ${i + 1}`} className="w-full h-full object-cover object-top" />
                {isSelected && (
                  <div className="absolute inset-0 bg-rose-500/10 flex items-start justify-end p-2">
                    <div
                      className="w-7 h-7 rounded-full flex items-center justify-center text-white text-sm"
                      style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
                    >
                      <i className="ri-check-line" />
                    </div>
                  </div>
                )}
                <div className="absolute inset-0 bg-rose-900/20 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-end justify-center pb-3">
                  <button
                    type="button"
                    className="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs text-white cursor-pointer whitespace-nowrap"
                    style={{ background: "rgba(244,114,182,0.8)", fontFamily: "'ZCOOL KuaiLe', cursive" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setPreviewUrl(url);
                    }}
                  >
                    <i className="ri-zoom-in-line text-xs" />
                    查看大图
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div
        className="px-5 py-4 border-t border-rose-100/40 shrink-0 flex items-center justify-between"
        style={{ background: "rgba(255,255,255,0.6)" }}
      >
        <span className="text-sm text-rose-500/80" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
          {selected ? "已选中 1 张候选图" : "点击图片选择最满意的一张"}
        </span>

        {saveSuccess ? (
          <div
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm"
            style={{
              background: "linear-gradient(135deg, rgba(167,243,208,0.3) 0%, rgba(110,231,183,0.2) 100%)",
              border: "1px solid rgba(110,231,183,0.3)",
              color: "#059669",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            <i className="ri-checkbox-circle-fill text-sm" />
            已保存为正式标准参考图！
          </div>
        ) : (
          <button
            type="button"
            onClick={handleSave}
            disabled={!selected || isSaving}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: selected
                ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                : "rgba(253,164,175,0.3)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              boxShadow: selected ? "0 4px 14px rgba(244,114,182,0.35)" : "none",
            }}
          >
            <i className="ri-save-line text-sm" />
            {isSaving ? "保存中..." : "保存为正式标准参考图"}
          </button>
        )}
      </div>

      {previewUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.65)", backdropFilter: "blur(8px)" }}
          onClick={() => setPreviewUrl(null)}
        >
          <div
            className="relative max-w-lg w-full mx-4 rounded-3xl overflow-hidden"
            style={{ background: "rgba(255,255,255,0.97)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-rose-100/40">
              <span className="text-sm font-bold text-rose-500" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                候选图预览
              </span>
              <button
                type="button"
                onClick={() => setPreviewUrl(null)}
                className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-rose-50 text-rose-400 cursor-pointer transition-all"
              >
                <i className="ri-close-line" />
              </button>
            </div>
            <div className="p-4">
              <img src={previewUrl} alt="预览" className="w-full max-h-[70vh] object-contain rounded-xl" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const PhotoTaskPage = ({ characterId, rawImages, onCharacterUpdated, showToast }: PhotoTaskPageProps) => {
  const [selectedRefIds, setSelectedRefIds] = useState<Set<string>>(new Set());
  const [shotType, setShotType] = useState<ShotType>("full_front");
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("9:16");
  const [genCount, setGenCount] = useState<GenCount>(2);
  const [pageState, setPageState] = useState<PageState>("config");
  const [resultImages, setResultImages] = useState<string[]>([]);
  const [loadingStart, setLoadingStart] = useState(false);
  const [savingResult, setSavingResult] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [pollError, setPollError] = useState<string | null>(null);

  const selectedType = useMemo(() => SHOT_TYPES.find((t) => t.id === shotType), [shotType]);
  const canStart = selectedRefIds.size > 0 && !loadingStart;

  const toggleRef = useCallback((id: string) => {
    setSelectedRefIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const loadStatus = useCallback(async (): Promise<materialApi.StandardPhotoStatusResult | null> => {
    try {
      return await materialApi.getStandardPhotoStatus(characterId);
    } catch {
      return null;
    }
  }, [characterId]);

  useEffect(() => {
    let alive = true;
    let timer: number | null = null;
    if (pageState !== "generating") return;
    const poll = async () => {
      try {
        const status = await materialApi.getStandardPhotoStatus(characterId);
        if (!alive) return;
        if (status.status === "completed") {
          setResultImages(status.result_images || []);
          setPageState("result");
          setPollError(null);
          return;
        }
        if (status.status === "failed") {
          setPollError(status.error_message || "标准照生成失败，请重试");
          return;
        }
      } catch (e) {
        if (!alive) return;
        const msg = e instanceof ApiError ? e.message : "获取任务状态失败";
        setPollError(msg);
      }
      timer = window.setTimeout(() => {
        void poll();
      }, 15000);
    };
    void poll();
    return () => {
      alive = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [characterId, pageState]);

  const handleStart = useCallback(async () => {
    setLoadingStart(true);
    setPollError(null);
    setSaveSuccess(false);
    try {
      await materialApi.startStandardPhotoTask(characterId, {
        shot_type: shotType,
        aspect_ratio: aspectRatio,
        output_count: genCount,
        selected_raw_image_ids: Array.from(selectedRefIds),
      });
      setPageState("generating");
      showToast("标准照任务已提交，正在生成");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "启动标准照任务失败");
    } finally {
      setLoadingStart(false);
    }
  }, [characterId, shotType, aspectRatio, genCount, selectedRefIds, showToast]);

  const handleRetry = useCallback(async () => {
    setPageState("generating");
    setPollError(null);
    setSaveSuccess(false);
    try {
      const status = await loadStatus();
      if (status) {
        await materialApi.retryStandardPhotoTask(characterId);
      } else {
        await materialApi.startStandardPhotoTask(characterId, {
          shot_type: shotType,
          aspect_ratio: aspectRatio,
          output_count: genCount,
          selected_raw_image_ids: Array.from(selectedRefIds),
        });
      }
      showToast("已重新提交标准照任务");
    } catch (e) {
      setPageState("config");
      showToast(e instanceof ApiError ? e.message : "重试失败");
    }
  }, [characterId, loadStatus, shotType, aspectRatio, genCount, selectedRefIds, showToast]);

  const handleSaveResult = useCallback(
    async (url: string) => {
      const fileName = url.split("/").pop();
      if (!fileName) {
        showToast("结果图路径无效");
        return;
      }
      setSavingResult(true);
      try {
        const detail = await materialApi.selectStandardPhotoResult(characterId, {
          selected_result_filename: fileName,
        });
        onCharacterUpdated(detail);
        setSaveSuccess(true);
        showToast("标准照已保存到正式内容");
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "保存标准照失败");
      } finally {
        setSavingResult(false);
      }
    },
    [characterId, onCharacterUpdated, showToast]
  );

  if (pageState === "generating") {
    return <GeneratingView errorMessage={pollError} />;
  }
  if (pageState === "result") {
    return (
      <ResultView
        images={resultImages}
        isSaving={savingResult}
        onSave={handleSaveResult}
        onRetry={handleRetry}
        saveSuccess={saveSuccess}
      />
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="flex flex-col gap-5 p-5">
        <div
          className="rounded-2xl overflow-hidden"
          style={{ border: "1px solid rgba(253,164,175,0.25)", background: "rgba(255,255,255,0.7)" }}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-rose-100/40">
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 rounded-lg flex items-center justify-center text-white text-xs"
                style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
              >
                1
              </div>
              <span className="text-sm font-bold text-rose-600" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                选择参考图
              </span>
            </div>
            {selectedRefIds.size > 0 && (
              <span
                className="text-xs px-2.5 py-0.5 rounded-full text-white"
                style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
              >
                已选 {selectedRefIds.size} 张
              </span>
            )}
          </div>
          <div className="p-4">
            {rawImages.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <i className="ri-image-add-line text-rose-300 text-xl mb-2" />
                <p className="text-sm text-rose-300/60" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                  还没有参考图哦，先去「原始资料」上传几张吧～
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {(["official", "fanart"] as RawImageType[]).map((type) => {
                  const images = rawImages.filter((img) => img.type === type);
                  if (images.length === 0) return null;
                  const cfg = RAW_TYPE_CONFIG[type];
                  return (
                    <div key={type}>
                      <div className="flex items-center gap-1.5 mb-2">
                        <span
                          className="w-4 h-4 rounded-md flex items-center justify-center text-white"
                          style={{ background: cfg.accentBg, fontSize: 10 }}
                        >
                          <i className={cfg.icon} />
                        </span>
                        <span
                          className="text-xs font-bold"
                          style={{ color: cfg.accentText, fontFamily: "'ZCOOL KuaiLe', cursive" }}
                        >
                          {cfg.label}
                        </span>
                        <span className="text-xs" style={{ color: `${cfg.accentText}99` }}>
                          {images.length} 张
                        </span>
                      </div>
                      <div className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 gap-2.5">
                        {images.map((img) => {
                          const isSelected = selectedRefIds.has(img.id);
                          return (
                            <button
                              key={img.id}
                              type="button"
                              className="relative rounded-xl overflow-hidden cursor-pointer transition-all duration-200 group"
                              style={{
                                aspectRatio: "1",
                                border: isSelected ? cfg.selectedBorder : cfg.normalBorder,
                                boxShadow: isSelected ? cfg.selectedGlow : "none",
                              }}
                              onClick={() => toggleRef(img.id)}
                            >
                              <img src={img.url} alt="参考图" className="w-full h-full object-cover object-top" />
                              {isSelected && (
                                <div
                                  className="absolute inset-0 flex items-start justify-end p-1"
                                  style={{ background: cfg.selectedOverlay }}
                                >
                                  <div
                                    className="w-5 h-5 rounded-full flex items-center justify-center text-white text-xs"
                                    style={{ background: cfg.accentBg }}
                                  >
                                    <i className="ri-check-line text-xs" />
                                  </div>
                                </div>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div
          className="rounded-2xl overflow-hidden"
          style={{ border: "1px solid rgba(253,164,175,0.25)", background: "rgba(255,255,255,0.7)" }}
        >
          <div className="flex items-center gap-2 px-4 py-3 border-b border-rose-100/40">
            <div
              className="w-6 h-6 rounded-lg flex items-center justify-center text-white text-xs"
              style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
            >
              2
            </div>
            <span className="text-sm font-bold text-rose-600" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              选择标准照类型
            </span>
          </div>
          <div className="p-4">
            <div className="flex flex-wrap gap-2">
              {SHOT_TYPES.map((type) => {
                const isActive = shotType === type.id;
                return (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() => setShotType(type.id)}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                    style={{
                      fontFamily: "'ZCOOL KuaiLe', cursive",
                      background: isActive
                        ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                        : "rgba(253,164,175,0.08)",
                      color: isActive ? "white" : "#f472b6",
                      border: isActive ? "1.5px solid transparent" : "1.5px solid rgba(253,164,175,0.25)",
                    }}
                  >
                    <i className={`${type.icon} text-sm`} />
                    {type.label}
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-rose-400/50 mt-2.5 ml-0.5">{selectedType?.desc}</p>
          </div>
        </div>

        <div
          className="rounded-2xl overflow-hidden"
          style={{ border: "1px solid rgba(253,164,175,0.25)", background: "rgba(255,255,255,0.7)" }}
        >
          <div className="flex items-center gap-2 px-4 py-3 border-b border-rose-100/40">
            <div
              className="w-6 h-6 rounded-lg flex items-center justify-center text-white text-xs"
              style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
            >
              3
            </div>
            <span className="text-sm font-bold text-rose-600" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              图片规格
            </span>
          </div>
          <div className="p-4 flex flex-col gap-4">
            <div>
              <p className="text-xs text-rose-500/70 mb-2.5 font-medium">长宽比</p>
              <div className="flex items-center gap-2">
                {ASPECT_RATIOS.map((r) => {
                  const isActive = aspectRatio === r.value;
                  return (
                    <button
                      key={r.value}
                      type="button"
                      onClick={() => setAspectRatio(r.value)}
                      className="flex items-center gap-2.5 px-4 py-2 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                      style={{
                        background: isActive
                          ? "linear-gradient(135deg, rgba(253,164,175,0.2) 0%, rgba(244,114,182,0.15) 100%)"
                          : "rgba(253,164,175,0.06)",
                        color: isActive ? "#f472b6" : "#fda4af",
                        border: isActive
                          ? "1.5px solid rgba(244,114,182,0.4)"
                          : "1.5px solid rgba(253,164,175,0.15)",
                      }}
                    >
                      <RatioPreview ratio={r.value} />
                      {r.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <p className="text-xs text-rose-500/70 mb-2.5 font-medium">生成数量</p>
              <div className="flex items-center gap-2">
                {GEN_COUNTS.map((c) => {
                  const isActive = genCount === c.value;
                  return (
                    <button
                      key={c.value}
                      type="button"
                      onClick={() => setGenCount(c.value)}
                      className="px-5 py-2 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
                      style={{
                        background: isActive
                          ? "linear-gradient(135deg, rgba(253,164,175,0.2) 0%, rgba(244,114,182,0.15) 100%)"
                          : "rgba(253,164,175,0.06)",
                        color: isActive ? "#f472b6" : "#fda4af",
                        border: isActive
                          ? "1.5px solid rgba(244,114,182,0.4)"
                          : "1.5px solid rgba(253,164,175,0.15)",
                      }}
                    >
                      {c.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-center gap-3 pb-2">
          {!canStart && (
            <p className="text-xs text-rose-400/50" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              先选择至少一张参考图，才能开始拍摄哦～
            </p>
          )}
          <button
            type="button"
            onClick={() => void handleStart()}
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
            <i className="ri-camera-fill text-lg" />
            {loadingStart ? "提交中..." : "开始拍摄标准照"}
            {canStart && (
              <span className="text-sm opacity-80">
                · {selectedRefIds.size} 张参考 · {selectedType?.label} · {genCount} 张
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PhotoTaskPage;
