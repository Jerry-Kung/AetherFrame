import { useCallback, useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import type { CharaProfile } from "@/types/material";
import { STANDARD_PHOTO_LABELS } from "@/types/material";

interface AvatarPickerModalProps {
  isOpen: boolean;
  chara: CharaProfile;
  onConfirm: (avatarUrl: string) => void;
  onCancel: () => void;
}

type SourceTab = "official" | "fanart" | "standard";

const SOURCE_TABS: { id: SourceTab; label: string; icon: string }[] = [
  { id: "official", label: "官方形象", icon: "ri-star-line" },
  { id: "fanart", label: "同人立绘", icon: "ri-palette-line" },
  { id: "standard", label: "角色标准照", icon: "ri-camera-line" },
];

interface CropRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

const DEFAULT_CROP: CropRect = { x: 0.1, y: 0.05, w: 0.8, h: 0.8 };

type GridRow = { key: string; url: string; label?: string };

const ImageCropper = ({
  imageUrl,
  onConfirm,
  onBack,
}: {
  imageUrl: string;
  onConfirm: (croppedUrl: string) => void;
  onBack: () => void;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [crop, setCrop] = useState<CropRect>(DEFAULT_CROP);
  const [dragging, setDragging] = useState<"move" | "tl" | "tr" | "bl" | "br" | null>(null);
  const dragStart = useRef<{ mx: number; my: number; crop: CropRect } | null>(null);
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    setImgLoaded(false);
    setCrop(DEFAULT_CROP);
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      imgRef.current = img;
      setImgLoaded(true);
    };
    img.onerror = () => {
      imgRef.current = img;
      setImgLoaded(true);
    };
    img.src = imageUrl;
  }, [imageUrl]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setContainerSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    setContainerSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v));

  const handleMouseDown = useCallback(
    (e: MouseEvent, type: "move" | "tl" | "tr" | "bl" | "br") => {
      e.preventDefault();
      e.stopPropagation();
      setDragging(type);
      dragStart.current = { mx: e.clientX, my: e.clientY, crop: { ...crop } };
    },
    [crop]
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!dragging || !dragStart.current || containerSize.w === 0) return;
      const dx = (e.clientX - dragStart.current.mx) / containerSize.w;
      const dy = (e.clientY - dragStart.current.my) / containerSize.h;
      const base = dragStart.current.crop;
      const MIN_SIZE = 0.1;

      let next = { ...base };

      if (dragging === "move") {
        next.x = clamp(base.x + dx, 0, 1 - base.w);
        next.y = clamp(base.y + dy, 0, 1 - base.h);
      } else if (dragging === "tl") {
        const newX = clamp(base.x + dx, 0, base.x + base.w - MIN_SIZE);
        const newY = clamp(base.y + dy, 0, base.y + base.h - MIN_SIZE);
        next.w = base.x + base.w - newX;
        next.h = base.y + base.h - newY;
        next.x = newX;
        next.y = newY;
      } else if (dragging === "tr") {
        const newW = clamp(base.w + dx, MIN_SIZE, 1 - base.x);
        const newY = clamp(base.y + dy, 0, base.y + base.h - MIN_SIZE);
        next.w = newW;
        next.h = base.y + base.h - newY;
        next.y = newY;
      } else if (dragging === "bl") {
        const newX = clamp(base.x + dx, 0, base.x + base.w - MIN_SIZE);
        const newH = clamp(base.h + dy, MIN_SIZE, 1 - base.y);
        next.x = newX;
        next.w = base.x + base.w - newX;
        next.h = newH;
      } else if (dragging === "br") {
        next.w = clamp(base.w + dx, MIN_SIZE, 1 - base.x);
        next.h = clamp(base.h + dy, MIN_SIZE, 1 - base.y);
      }

      setCrop(next);
    },
    [dragging, containerSize]
  );

  const handleMouseUp = useCallback(() => {
    setDragging(null);
    dragStart.current = null;
  }, []);

  const handleConfirmCrop = useCallback(() => {
    const img = imgRef.current;
    if (!img) {
      onConfirm(imageUrl);
      return;
    }
    const canvas = canvasRef.current;
    if (!canvas) {
      onConfirm(imageUrl);
      return;
    }
    const srcX = Math.round(crop.x * img.naturalWidth);
    const srcY = Math.round(crop.y * img.naturalHeight);
    const srcW = Math.round(crop.w * img.naturalWidth);
    const srcH = Math.round(crop.h * img.naturalHeight);
    const size = 256;
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      onConfirm(imageUrl);
      return;
    }
    try {
      ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, size, size);
      const dataUrl = canvas.toDataURL("image/png");
      onConfirm(dataUrl);
    } catch {
      onConfirm(imageUrl);
    }
  }, [crop, imageUrl, onConfirm]);

  const cropPx = {
    left: `${crop.x * 100}%`,
    top: `${crop.y * 100}%`,
    width: `${crop.w * 100}%`,
    height: `${crop.h * 100}%`,
  };

  const handleSize = 14;

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-rose-100/40 shrink-0">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm cursor-pointer transition-all hover:opacity-70 whitespace-nowrap"
          style={{ color: "#f472b6", fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <i className="ri-arrow-left-line text-sm" />
          重新选图
        </button>
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-4 h-4 flex items-center justify-center shrink-0">
            <i className="ri-crop-line text-rose-400 text-sm" />
          </div>
          <span
            className="text-sm font-bold text-rose-600 truncate"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            拖动选框，选择头像区域
          </span>
        </div>
        <button
          type="button"
          onClick={handleConfirmCrop}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-sm font-bold text-white cursor-pointer transition-all duration-200 whitespace-nowrap shrink-0"
          style={{
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            fontFamily: "'ZCOOL KuaiLe', cursive",
            boxShadow: "0 3px 10px rgba(244,114,182,0.35)",
          }}
        >
          <i className="ri-check-line text-sm" />
          确认裁剪
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center p-4 min-h-0">
        <div
          ref={containerRef}
          className="relative w-full max-w-5xl select-none overflow-hidden rounded-2xl"
          style={{
            height: "min(72vh, 78vw)",
            maxHeight: "640px",
            background: "#1a1a2e",
            cursor: dragging === "move" ? "grabbing" : "default",
          }}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {imgLoaded && (
            <img
              src={imageUrl}
              alt="选择区域"
              className="absolute inset-0 z-0 w-full h-full object-contain"
              draggable={false}
            />
          )}
          {imgLoaded && (
            <div
              className="absolute"
              style={{
                ...cropPx,
                cursor: "grab",
                zIndex: 10,
              }}
              onMouseDown={(e) => handleMouseDown(e, "move")}
            >
              <div
                className="absolute inset-0 rounded-sm"
                style={{
                  border: "2px solid rgba(244,114,182,0.9)",
                  boxShadow: "0 0 0 9999px rgba(0,0,0,0.55)",
                }}
              />

              <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 1 }}>
                <div
                  className="absolute inset-0"
                  style={{
                    backgroundImage:
                      "linear-gradient(rgba(255,255,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.15) 1px, transparent 1px)",
                    backgroundSize: "33.33% 33.33%",
                  }}
                />
              </div>

              {(["tl", "tr", "bl", "br"] as const).map((corner) => (
                <div
                  key={corner}
                  className="absolute rounded-full"
                  style={{
                    width: handleSize,
                    height: handleSize,
                    background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                    border: "2px solid white",
                    zIndex: 20,
                    cursor: corner === "tl" || corner === "br" ? "nwse-resize" : "nesw-resize",
                    top: corner.startsWith("t") ? -handleSize / 2 : undefined,
                    bottom: corner.startsWith("b") ? -handleSize / 2 : undefined,
                    left: corner.endsWith("l") ? -handleSize / 2 : undefined,
                    right: corner.endsWith("r") ? -handleSize / 2 : undefined,
                    boxShadow: "0 2px 6px rgba(244,114,182,0.5)",
                  }}
                  onMouseDown={(e) => handleMouseDown(e, corner)}
                />
              ))}
            </div>
          )}

          {!imgLoaded && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <i className="ri-loader-4-line text-rose-300 text-2xl animate-spin" />
                <span
                  className="text-xs text-rose-300/60"
                  style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                >
                  图片加载中...
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="px-5 pb-4 shrink-0 text-center">
        <p className="text-xs text-rose-400/50" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
          拖动选框移动位置，拖动四角调整大小，选好后点击「确认裁剪」
        </p>
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
};

const ImageGridItem = ({
  url,
  label,
  isSelected,
  onClick,
}: {
  url: string;
  label?: string;
  isSelected: boolean;
  onClick: () => void;
}) => (
  <button
    type="button"
    className="relative rounded-xl overflow-hidden cursor-pointer transition-all duration-200 group text-left w-full p-0 border-0 bg-transparent"
    style={{
      aspectRatio: "1",
      border: isSelected
        ? "2.5px solid #f472b6"
        : "1.5px solid rgba(253,164,175,0.25)",
      boxShadow: isSelected ? "0 0 0 3px rgba(244,114,182,0.18)" : "none",
    }}
    onClick={onClick}
  >
    <img
      src={url}
      alt={label ?? "图片"}
      className="w-full h-full object-cover object-top transition-transform duration-200 group-hover:scale-105 pointer-events-none"
    />
    {isSelected && (
      <div
        className="absolute inset-0 flex items-start justify-end p-1.5 pointer-events-none"
        style={{ background: "rgba(244,114,182,0.15)" }}
      >
        <div
          className="w-5 h-5 rounded-full flex items-center justify-center text-white text-xs"
          style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
        >
          <i className="ri-check-line text-xs" />
        </div>
      </div>
    )}
    {label && (
      <div
        className="absolute bottom-0 left-0 right-0 px-1.5 py-1 text-center pointer-events-none"
        style={{ background: "rgba(0,0,0,0.45)" }}
      >
        <span className="text-white text-xs" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
          {label}
        </span>
      </div>
    )}
  </button>
);

const AvatarPickerModal = ({ isOpen, chara, onConfirm, onCancel }: AvatarPickerModalProps) => {
  const [activeTab, setActiveTab] = useState<SourceTab>("official");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [cropMode, setCropMode] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setActiveTab("official");
      setSelectedKey(null);
      setCropMode(false);
    }
  }, [isOpen]);

  const officialImages = chara.rawImages.filter((img) => img.type === "official");
  const fanartImages = chara.rawImages.filter((img) => img.type === "fanart");
  const standardPhotos = chara.standardPhotos;

  const currentRows: GridRow[] = (() => {
    if (activeTab === "official") {
      return officialImages.map((img) => ({
        key: `raw-${img.id}`,
        url: img.url,
      }));
    }
    if (activeTab === "fanart") {
      return fanartImages.map((img) => ({
        key: `raw-${img.id}`,
        url: img.url,
      }));
    }
    return standardPhotos.map((p) => ({
      key: `std-${p.id}`,
      url: p.url,
      label: STANDARD_PHOTO_LABELS[p.type],
    }));
  })();

  const selectedUrl = currentRows.find((r) => r.key === selectedKey)?.url ?? null;

  const handleNextStep = () => {
    if (!selectedUrl) return;
    setCropMode(true);
  };

  const handleCropConfirm = (croppedUrl: string) => {
    onConfirm(croppedUrl);
  };

  const handleCropBack = () => {
    setCropMode(false);
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3"
      style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !cropMode) onCancel();
      }}
    >
      <div
        className="relative flex flex-col rounded-3xl overflow-hidden shadow-2xl"
        style={{
          width: cropMode ? "min(96vw, 920px)" : "min(680px, 95vw)",
          height: cropMode ? "min(92vh, 900px)" : "min(560px, 90vh)",
          maxWidth: "100%",
          background: "linear-gradient(145deg, #fff5f7 0%, #fffaf5 60%, #fef2f8 100%)",
          border: "1px solid rgba(253,164,175,0.3)",
          boxShadow: "0 24px 60px rgba(244,114,182,0.18)",
        }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="h-[3px] w-full shrink-0 bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300 opacity-70" />

        {cropMode && selectedUrl ? (
          <ImageCropper
            imageUrl={selectedUrl}
            onConfirm={handleCropConfirm}
            onBack={handleCropBack}
          />
        ) : (
          <>
            <div className="flex items-center justify-between px-5 py-4 shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                <div
                  className="w-7 h-7 flex items-center justify-center rounded-xl shrink-0"
                  style={{ background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)" }}
                >
                  <i className="ri-user-heart-line text-white text-sm" />
                </div>
                <div className="min-w-0">
                  <h2
                    className="text-base font-bold text-rose-700 leading-tight"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    修改角色头像
                  </h2>
                  <p className="text-xs text-rose-400/60 truncate">从图库中选一张，然后裁剪出头像区域</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onCancel}
                className="w-8 h-8 flex items-center justify-center rounded-xl cursor-pointer transition-all hover:bg-rose-100/60 shrink-0"
                style={{ color: "#f472b6" }}
                aria-label="关闭"
              >
                <i className="ri-close-line text-lg" />
              </button>
            </div>

            <div className="px-5 shrink-0">
              <div
                className="flex items-center gap-1 p-1 rounded-2xl flex-wrap"
                style={{
                  background: "rgba(253,164,175,0.1)",
                  border: "1px solid rgba(253,164,175,0.2)",
                  display: "inline-flex",
                }}
              >
                {SOURCE_TABS.map((tab) => {
                  const isActive = activeTab === tab.id;
                  const count =
                    tab.id === "official"
                      ? officialImages.length
                      : tab.id === "fanart"
                        ? fanartImages.length
                        : standardPhotos.length;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => {
                        setActiveTab(tab.id);
                        setSelectedKey(null);
                      }}
                      className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
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
                        <i className={`${tab.icon} text-sm`} />
                      </div>
                      {tab.label}
                      <span
                        className="text-xs px-1.5 py-0.5 rounded-full"
                        style={{
                          background: isActive ? "rgba(255,255,255,0.25)" : "rgba(244,114,182,0.12)",
                          color: isActive ? "white" : "#f472b6",
                        }}
                      >
                        {count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mx-5 mt-3 h-px bg-rose-100/40 shrink-0" />

            <div className="flex-1 min-h-0 overflow-y-auto px-5 py-3">
              {currentRows.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full py-10 text-center">
                  <div
                    className="w-14 h-14 flex items-center justify-center rounded-2xl mb-3"
                    style={{
                      background: "rgba(253,164,175,0.1)",
                      border: "1.5px dashed rgba(253,164,175,0.3)",
                    }}
                  >
                    <i className="ri-image-line text-rose-300 text-2xl" />
                  </div>
                  <p
                    className="text-sm text-rose-400/60"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    {activeTab === "official"
                      ? "还没有官方形象图，先去「原始资料」上传吧～"
                      : activeTab === "fanart"
                        ? "还没有同人立绘，先去「原始资料」上传吧～"
                        : "还没有角色标准照，先去「加工任务」拍摄吧～"}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-4 sm:grid-cols-5 gap-3">
                  {currentRows.map((row) => (
                    <ImageGridItem
                      key={row.key}
                      url={row.url}
                      label={row.label}
                      isSelected={selectedKey === row.key}
                      onClick={() => setSelectedKey(row.key)}
                    />
                  ))}
                </div>
              )}
            </div>

            <div
              className="flex items-center justify-between px-5 py-3.5 shrink-0 gap-2 flex-wrap"
              style={{ borderTop: "1px solid rgba(253,164,175,0.15)" }}
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                {selectedUrl ? (
                  <>
                    <div
                      className="w-9 h-9 rounded-xl overflow-hidden border-2 shrink-0"
                      style={{ borderColor: "rgba(244,114,182,0.4)" }}
                    >
                      <img
                        src={selectedUrl}
                        alt="预览"
                        className="w-full h-full object-cover object-top"
                      />
                    </div>
                    <span
                      className="text-xs text-rose-500"
                      style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                    >
                      已选择，点击「下一步」裁剪头像区域
                    </span>
                  </>
                ) : (
                  <span
                    className="text-xs text-rose-400/50"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    点击图片选择，然后裁剪出头像区域
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={onCancel}
                  className="px-4 py-2 rounded-xl text-sm cursor-pointer transition-all hover:bg-rose-50 whitespace-nowrap"
                  style={{
                    color: "#f472b6",
                    border: "1px solid rgba(244,114,182,0.2)",
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                  }}
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleNextStep}
                  disabled={!selectedUrl}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-xl text-sm font-bold text-white cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{
                    background: selectedUrl
                      ? "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)"
                      : "rgba(253,164,175,0.3)",
                    fontFamily: "'ZCOOL KuaiLe', cursive",
                    boxShadow: selectedUrl ? "0 4px 14px rgba(244,114,182,0.35)" : "none",
                  }}
                >
                  <i className="ri-crop-line text-sm" />
                  下一步：裁剪头像
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AvatarPickerModal;
