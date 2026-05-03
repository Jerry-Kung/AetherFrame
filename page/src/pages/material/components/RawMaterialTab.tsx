import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import type { CharaRawImage, RawImageType } from "@/types/material";

interface RawMaterialTabProps {
  characterId: string;
  settingText: string;
  settingFileName: string;
  /** 仅点击「完成」时调用；成功后再收起编辑区；失败时应 reject 以便保留展开态与草稿 */
  onSettingCommit: (text: string) => Promise<void>;
  /** FileReader 读出文本后由父组件上传并更新状态 */
  onSettingImportedFromFile: (text: string, file: File) => void | Promise<void>;
  rawImages: CharaRawImage[];
  onUploadRawFiles: (files: File[], type: RawImageType) => void | Promise<void>;
  onRemoveRawImage: (imageId: string) => void | Promise<void>;
  onUpdateRawImageTags: (imageId: string, tags: string[]) => void | Promise<void>;
  onRawImageClick: (imageId: string) => void;
}

const RAW_TYPE_CONFIG: Record<
  RawImageType,
  {
    label: string;
    icon: string;
    emptyHint: string;
    countBg: string;
    countText: string;
    border: string;
    uploadBg: string;
    hoverOverlay: string;
    cardBorder: string;
  }
> = {
  official: {
    label: "官方形象",
    icon: "ri-award-line",
    emptyHint: "暂无官方形象，点击上传添加",
    countBg: "rgba(253,164,175,0.14)",
    countText: "#f472b6",
    border: "border-rose-200/70",
    uploadBg: "linear-gradient(135deg, #fda4af, #f472b6)",
    hoverOverlay: "bg-rose-500/15",
    cardBorder: "border-rose-100/80",
  },
  fanart: {
    label: "同人立绘",
    icon: "ri-palette-line",
    emptyHint: "暂无同人立绘，点击上传添加",
    countBg: "rgba(196,181,253,0.2)",
    countText: "#8b5cf6",
    border: "border-violet-200/70",
    uploadBg: "linear-gradient(135deg, #c4b5fd, #8b5cf6)",
    hoverOverlay: "bg-violet-500/15",
    cardBorder: "border-violet-100/90",
  },
};

const RawMaterialTab = ({
  characterId,
  settingText,
  settingFileName,
  onSettingCommit,
  onSettingImportedFromFile,
  rawImages,
  onUploadRawFiles,
  onRemoveRawImage,
  onUpdateRawImageTags: _onUpdateRawImageTags,
  onRawImageClick,
}: RawMaterialTabProps) => {
  const txtInputRef = useRef<HTMLInputElement>(null);
  const officialInputRef = useRef<HTMLInputElement>(null);
  const fanartInputRef = useRef<HTMLInputElement>(null);
  const settingTextareaRef = useRef<HTMLTextAreaElement>(null);
  const settingEditingRef = useRef(false);
  const [hoverPreview, setHoverPreview] = useState<{ url: string; x: number; y: number } | null>(null);
  const [settingExpanded, setSettingExpanded] = useState(false);
  const [settingDraft, setSettingDraft] = useState("");

  const officialImages = useMemo(
    () => rawImages.filter((img) => img.type === "official"),
    [rawImages]
  );
  const fanartImages = useMemo(
    () => rawImages.filter((img) => img.type === "fanart"),
    [rawImages]
  );

  const hasSetting = settingText.trim().length > 0;
  const hasAnyRaw = officialImages.length > 0 || fanartImages.length > 0;
  const ready = hasSetting && hasAnyRaw;

  useEffect(() => {
    settingEditingRef.current = false;
    setSettingExpanded(false);
  }, [characterId]);

  useEffect(() => {
    settingEditingRef.current = settingExpanded;
  }, [settingExpanded]);

  useEffect(() => {
    setSettingDraft(settingText);
  }, [characterId, settingText, settingFileName]);

  useEffect(() => {
    if (settingExpanded) {
      const id = requestAnimationFrame(() => settingTextareaRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
    return undefined;
  }, [settingExpanded]);

  const commitSettingEdit = useCallback(async () => {
    if (!settingEditingRef.current) return;
    try {
      await onSettingCommit(settingDraft);
      settingEditingRef.current = false;
      setSettingExpanded(false);
    } catch {
      /* 父组件已 toast；保持展开与草稿 */
    }
  }, [onSettingCommit, settingDraft]);

  const startSettingEdit = useCallback(() => {
    setSettingDraft(settingText);
    settingEditingRef.current = true;
    setSettingExpanded(true);
  }, [settingText]);

  const handleTxtFiles = useCallback(
    (files: FileList | null) => {
      const f = files?.[0];
      if (!f) return;
      const lower = f.name.toLowerCase();
      if (!lower.endsWith(".txt") && !lower.endsWith(".md")) {
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const text = typeof reader.result === "string" ? reader.result : "";
        void onSettingImportedFromFile(text, f);
      };
      reader.readAsText(f, "UTF-8");
      if (txtInputRef.current) txtInputRef.current.value = "";
    },
    [onSettingImportedFromFile]
  );

  const readinessDetail = useMemo(() => {
    if (ready) {
      return "设定说明与参考图均已具备，可以前往「加工任务」开始流程。";
    }
    const parts: string[] = [];
    if (!hasSetting) parts.push("角色设定说明");
    if (!hasAnyRaw) parts.push("参考图（官方形象或同人立绘至少一张）");
    return `还缺少：${parts.join("；")}。`;
  }, [ready, hasSetting, hasAnyRaw]);

  const handleImgFiles = useCallback(
    (files: FileList | null, type: RawImageType, inputRef: RefObject<HTMLInputElement>) => {
      if (!files?.length) return;
      const list = Array.from(files).filter((f) => f.type.startsWith("image/"));
      if (!list.length) {
        if (inputRef.current) inputRef.current.value = "";
        return;
      }
      void onUploadRawFiles(list, type);
      if (inputRef.current) inputRef.current.value = "";
    },
    [onUploadRawFiles]
  );

  const removeImage = useCallback(
    (id: string) => {
      void onRemoveRawImage(id);
    },
    [onRemoveRawImage]
  );

  const renderImageSection = (type: RawImageType, images: CharaRawImage[], inputRef: RefObject<HTMLInputElement>) => {
    const cfg = RAW_TYPE_CONFIG[type];
    return (
      <section className={`rounded-xl border ${cfg.border} bg-white/60 p-3`}>
        <div className="flex items-center justify-between gap-2 mb-2">
          <h3
            className="text-sm font-semibold flex items-center gap-1.5"
            style={{ color: cfg.countText, fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <i className={`${cfg.icon}`} />
            {cfg.label}
            <span
              className="text-[11px] px-2 py-0.5 rounded-full"
              style={{ background: cfg.countBg, color: cfg.countText }}
            >
              {images.length} 张
            </span>
          </h3>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => handleImgFiles(e.target.files, type, inputRef)}
          />
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="text-xs px-3 py-1.5 rounded-full text-white cursor-pointer transition-all hover:opacity-95"
            style={{ background: cfg.uploadBg }}
          >
            <i className="ri-add-line mr-1" />
            上传图片
          </button>
        </div>

        {images.length === 0 ? (
          <div className="min-h-[96px] rounded-xl border border-dashed flex items-center justify-center text-xs text-slate-400">
            {cfg.emptyHint}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {images.map((im) => (
              <div
                key={im.id}
                className={`relative group rounded-xl overflow-hidden border bg-white/40 shadow-sm ${cfg.cardBorder}`}
              >
                <button
                  type="button"
                  className="block w-full aspect-square cursor-zoom-in"
                  onMouseEnter={(e) => {
                    const r = e.currentTarget.getBoundingClientRect();
                    const vw = window.innerWidth;
                    const previewW = 240;
                    const gap = 8;
                    const x = r.right + gap + previewW > vw ? r.left - gap - previewW : r.right + gap;
                    const y = Math.max(8, Math.min(r.top, window.innerHeight - 248));
                    setHoverPreview({ url: im.url, x, y });
                  }}
                  onMouseLeave={() => setHoverPreview(null)}
                  onClick={() => onRawImageClick(im.id)}
                >
                  <img src={im.url} alt="" className="w-full h-full object-cover" draggable={false} />
                </button>
                <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none ${cfg.hoverOverlay}`} />
                <button
                  type="button"
                  title="删除"
                  onClick={() => removeImage(im.id)}
                  className="absolute top-1.5 right-1.5 w-7 h-7 flex items-center justify-center rounded-lg bg-black/40 text-white opacity-0 group-hover:opacity-100 hover:bg-black/55 transition-opacity cursor-pointer"
                >
                  <i className="ri-close-line" />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    );
  };

  return (
    <div className="flex flex-col gap-4 min-h-0 h-full overflow-y-auto pr-1">
      <div
        className={[
          "rounded-xl px-4 py-3 flex items-start gap-3 shrink-0 border",
          ready
            ? "bg-emerald-50/90 border-emerald-200/60 text-emerald-800"
            : "bg-amber-50/90 border-amber-200/60 text-amber-900",
        ].join(" ")}
      >
        <span className={`shrink-0 mt-0.5 ${ready ? "text-emerald-500" : "text-amber-500"}`}>
          <i className={ready ? "ri-checkbox-circle-line text-lg" : "ri-alarm-warning-line text-lg"} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">{ready ? "资料已就绪" : "资料尚未就绪"}</p>
          <p className="text-xs mt-0.5 opacity-85 leading-relaxed">{readinessDetail}</p>
        </div>
      </div>

      <section
        className="shrink-0 rounded-xl border border-rose-100/80 bg-white/60 backdrop-blur-sm p-3 shadow-sm"
        style={{ boxShadow: "0 1px 12px rgba(244, 114, 182, 0.06)" }}
      >
        <div className={`flex flex-wrap items-center justify-between gap-2 ${settingExpanded ? "mb-2" : ""}`}>
          <h3
            className="text-sm font-semibold text-rose-700/80 flex flex-wrap items-center gap-1.5 min-w-0"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <i className="ri-file-text-line text-rose-400 shrink-0" />
            <span className="shrink-0">角色设定说明</span>
            {settingFileName.trim() ? (
              <span
                className="text-[11px] px-2 py-0.5 rounded-full font-normal max-w-[min(100%,14rem)] truncate"
                style={{ background: "rgba(253,164,175,0.18)", color: "#e11d48" }}
                title={settingFileName}
              >
                <i className="ri-attachment-2 align-middle mr-0.5" />
                {settingFileName}
              </span>
            ) : null}
          </h3>
          <div className="flex items-center gap-2 shrink-0">
            <input
              ref={txtInputRef}
              type="file"
              accept=".txt,.md,text/plain,text/markdown"
              className="hidden"
              onChange={(e) => handleTxtFiles(e.target.files)}
            />
            <button
              type="button"
              onClick={() => txtInputRef.current?.click()}
              className="text-xs px-3 py-1.5 rounded-full border border-rose-200/80 text-rose-600 bg-white/50 hover:bg-rose-50/90 hover:border-rose-300 cursor-pointer transition-all whitespace-nowrap"
            >
              <i className="ri-upload-2-line mr-1" />
              上传 .txt / .md
            </button>
            {settingExpanded ? (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => void commitSettingEdit()}
                className="text-xs px-3 py-1.5 rounded-full text-white cursor-pointer transition-all hover:opacity-95 shadow-sm"
                style={{ background: "linear-gradient(135deg, #fda4af, #f472b6)" }}
              >
                <i className="ri-check-line mr-1" />
                完成
              </button>
            ) : (
              <button
                type="button"
                onClick={startSettingEdit}
                className="text-xs px-3 py-1.5 rounded-full border border-rose-200/80 text-rose-600 bg-white/50 hover:bg-rose-50/90 hover:border-rose-300 cursor-pointer transition-all whitespace-nowrap"
              >
                <i className="ri-edit-line mr-1" />
                编辑
              </button>
            )}
          </div>
        </div>

        {settingExpanded ? (
          <textarea
            ref={settingTextareaRef}
            value={settingDraft}
            onChange={(e) => setSettingDraft(e.target.value)}
            placeholder="编辑完成后请点击右上角「完成」保存到服务器；未点完成则不会保存。"
            className="w-full min-h-[140px] rounded-xl border border-rose-100/90 bg-white/75 px-3 py-2.5 text-sm text-rose-900/85 placeholder:text-rose-300/60 resize-y focus:outline-none focus:ring-2 focus:ring-pink-200/80"
          />
        ) : (
          <div className="rounded-xl border border-rose-100/70 bg-white/40 px-3 py-2 text-sm text-rose-900/80">
            {hasSetting ? (
              <p className="whitespace-pre-wrap line-clamp-3 break-words leading-relaxed">{settingText}</p>
            ) : (
              <p className="italic text-rose-400/80 leading-relaxed">
                尚未填写设定。点击右上角「编辑」输入全文，或使用「上传 .txt / .md」导入。
              </p>
            )}
            {hasSetting ? (
              <p className="text-[11px] text-rose-400/80 mt-1.5">点「编辑」查看与修改全文。</p>
            ) : null}
          </div>
        )}
      </section>

      <section className="flex-1 min-h-0 flex flex-col gap-3">
        {renderImageSection("official", officialImages, officialInputRef)}
        {renderImageSection("fanart", fanartImages, fanartInputRef)}
      </section>

      {hoverPreview && (
        <div
          className="fixed z-40 pointer-events-none rounded-xl overflow-hidden border-2 border-white shadow-2xl bg-black/5"
          style={{
            left: hoverPreview.x,
            top: hoverPreview.y,
            width: 240,
            height: 240,
          }}
        >
          <img src={hoverPreview.url} alt="" className="w-full h-full object-cover" draggable={false} />
        </div>
      )}
    </div>
  );
};

export default RawMaterialTab;
