import { useCallback, useMemo, useRef, useState } from "react";
import type { CharaRawImage } from "@/types/material";
import { RAW_IMAGE_TAG_PRESETS } from "@/types/material";

interface RawMaterialTabProps {
  characterId: string;
  settingText: string;
  onSettingTextChange: (v: string) => void;
  /** 用户选择 .txt/.md 后由父组件上传并刷新 */
  onImportSettingFile: (file: File) => void | Promise<void>;
  rawImages: CharaRawImage[];
  onUploadRawFiles: (files: File[]) => void | Promise<void>;
  onRemoveRawImage: (imageId: string) => void | Promise<void>;
  onUpdateRawImageTags: (imageId: string, tags: string[]) => void | Promise<void>;
  onRawImageClick: (imageId: string) => void;
}

const RawMaterialTab = ({
  characterId: _characterId,
  settingText,
  onSettingTextChange,
  onImportSettingFile,
  rawImages,
  onUploadRawFiles,
  onRemoveRawImage,
  onUpdateRawImageTags,
  onRawImageClick,
}: RawMaterialTabProps) => {
  const txtInputRef = useRef<HTMLInputElement>(null);
  const imgInputRef = useRef<HTMLInputElement>(null);
  const [filterTag, setFilterTag] = useState<string | "all">("all");
  const [hoverPreview, setHoverPreview] = useState<{ url: string; x: number; y: number } | null>(null);

  const ready = settingText.trim().length > 0 && rawImages.length > 0;

  const filteredImages = useMemo(() => {
    if (filterTag === "all") return rawImages;
    return rawImages.filter((im) => im.tags.includes(filterTag));
  }, [rawImages, filterTag]);

  const toggleTagOnImage = useCallback(
    (imageId: string, tag: string) => {
      const im = rawImages.find((x) => x.id === imageId);
      if (!im) return;
      const has = im.tags.includes(tag);
      const nextTags = has ? im.tags.filter((t) => t !== tag) : [...im.tags, tag];
      const ensured = nextTags.length === 0 ? ["其他"] : nextTags;
      void onUpdateRawImageTags(imageId, ensured);
    },
    [rawImages, onUpdateRawImageTags]
  );

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
        onSettingTextChange(text);
        void onImportSettingFile(f);
      };
      reader.readAsText(f, "UTF-8");
      if (txtInputRef.current) txtInputRef.current.value = "";
    },
    [onSettingTextChange, onImportSettingFile]
  );

  const handleImgFiles = useCallback(
    (files: FileList | null) => {
      if (!files?.length) return;
      const list = Array.from(files).filter((f) => f.type.startsWith("image/"));
      if (!list.length) {
        if (imgInputRef.current) imgInputRef.current.value = "";
        return;
      }
      void onUploadRawFiles(list);
      if (imgInputRef.current) imgInputRef.current.value = "";
    },
    [onUploadRawFiles]
  );

  const removeImage = useCallback(
    (id: string) => {
      void onRemoveRawImage(id);
    },
    [onRemoveRawImage]
  );

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
          <p className="text-xs mt-0.5 opacity-85 leading-relaxed">
            {ready
              ? "设定说明与参考图均已具备，可以前往「加工任务」开始流程。"
              : "请至少填写一段设定说明，并上传一张参考图，便于后续加工。"}
          </p>
        </div>
      </div>

      <section className="shrink-0">
        <div className="flex items-center justify-between gap-2 mb-2">
          <h3
            className="text-sm font-semibold text-rose-700/80 flex items-center gap-1.5"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <i className="ri-file-text-line text-rose-400" />
            角色设定说明
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
              className="text-xs px-3 py-1.5 rounded-full border border-rose-200/80 text-rose-500 hover:bg-rose-50 cursor-pointer transition-colors whitespace-nowrap"
            >
              <i className="ri-upload-2-line mr-1" />
              上传 .txt / .md
            </button>
          </div>
        </div>
        <textarea
          value={settingText}
          onChange={(e) => onSettingTextChange(e.target.value)}
          placeholder="在此直接编辑设定，或使用上方按钮导入文本文件（导入会替换当前内容）…"
          className="w-full min-h-[140px] rounded-xl border border-rose-100/80 bg-white/70 px-3 py-2.5 text-sm text-rose-900/80 placeholder:text-rose-300/60 resize-y focus:outline-none focus:ring-2 focus:ring-pink-200/80"
        />
      </section>

      <section className="flex-1 min-h-0 flex flex-col">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h3
            className="text-sm font-semibold text-rose-700/80 flex items-center gap-1.5"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <i className="ri-image-2-line text-rose-400" />
            原始参考图
          </h3>
          <input
            ref={imgInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => handleImgFiles(e.target.files)}
          />
          <button
            type="button"
            onClick={() => imgInputRef.current?.click()}
            className="text-xs px-3 py-1.5 rounded-full text-white cursor-pointer transition-all hover:opacity-95"
            style={{ background: "linear-gradient(135deg, #f472b6, #ec4899)" }}
          >
            <i className="ri-add-line mr-1" />
            多图上传
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          <button
            type="button"
            onClick={() => setFilterTag("all")}
            className={[
              "text-[11px] px-2.5 py-1 rounded-full border transition-colors cursor-pointer",
              filterTag === "all"
                ? "bg-rose-500 text-white border-rose-500"
                : "bg-white/60 text-rose-400 border-rose-100 hover:border-rose-200",
            ].join(" ")}
          >
            全部
          </button>
          {RAW_IMAGE_TAG_PRESETS.map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => setFilterTag(tag)}
              className={[
                "text-[11px] px-2.5 py-1 rounded-full border transition-colors cursor-pointer",
                filterTag === tag
                  ? "bg-rose-500 text-white border-rose-500"
                  : "bg-white/60 text-rose-400 border-rose-100 hover:border-rose-200",
              ].join(" ")}
            >
              {tag}
            </button>
          ))}
        </div>

        {filteredImages.length === 0 ? (
          <div className="flex-1 min-h-[120px] rounded-xl border border-dashed border-rose-200/70 flex items-center justify-center text-xs text-rose-300/80">
            {rawImages.length === 0 ? "暂无图片，点击「多图上传」添加" : "当前标签下没有图片，换个标签试试"}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {filteredImages.map((im) => (
              <div
                key={im.id}
                className="relative group rounded-xl overflow-hidden border border-rose-100/80 bg-rose-50/30 shadow-sm"
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
                <button
                  type="button"
                  title="删除"
                  onClick={() => removeImage(im.id)}
                  className="absolute top-1.5 right-1.5 w-7 h-7 flex items-center justify-center rounded-lg bg-black/40 text-white opacity-0 group-hover:opacity-100 hover:bg-black/55 transition-opacity cursor-pointer"
                >
                  <i className="ri-close-line" />
                </button>
                <div className="p-1.5 flex flex-wrap gap-0.5 border-t border-rose-100/60 bg-white/80">
                  {RAW_IMAGE_TAG_PRESETS.map((tag) => {
                    const on = im.tags.includes(tag);
                    return (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => toggleTagOnImage(im.id, tag)}
                        className={[
                          "text-[9px] px-1 py-0.5 rounded cursor-pointer transition-colors",
                          on ? "bg-pink-400 text-white" : "bg-rose-50 text-rose-300 hover:bg-rose-100",
                        ].join(" ")}
                      >
                        {tag}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
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
