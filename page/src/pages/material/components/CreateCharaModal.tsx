import { useCallback, useEffect, useRef, useState } from "react";

type ValidationState = "idle" | "error";

const MAX_NAME_LENGTH = 20;
const VALID_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"];
const VALID_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

function isValidFileType(file: File): boolean {
  if (VALID_MIME_TYPES.includes(file.type)) return true;
  const lower = file.name.toLowerCase();
  return VALID_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

interface CreateCharaModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (name: string, avatarFile: File | null) => void | Promise<void>;
  defaultAvatarUrl: string;
}

const CreateCharaModal = ({
  isOpen,
  onClose,
  onConfirm,
  defaultAvatarUrl,
}: CreateCharaModalProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreviewUrl, setAvatarPreviewUrl] = useState<string>("");
  const [validation, setValidation] = useState<ValidationState>("idle");
  const [dragActive, setDragActive] = useState(false);

  // 重置状态
  useEffect(() => {
    if (isOpen) {
      setName("");
      setAvatarFile(null);
      setValidation("idle");
      setDragActive(false);
      setTimeout(() => inputRef.current?.focus(), 80);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!avatarFile) {
      setAvatarPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(avatarFile);
    setAvatarPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [avatarFile]);

  // ESC 关闭
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (!isOpen) return;
    document.addEventListener("keydown", handleKeyDown);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = prev;
    };
  }, [isOpen, handleKeyDown]);

  const applyFile = useCallback((file: File) => {
    if (!isValidFileType(file)) {
      return;
    }
    setAvatarFile(file);
  }, []);

  const onFileChange = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (file) applyFile(file);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [applyFile]
  );

  const removeAvatar = useCallback(() => setAvatarFile(null), []);

  // 拖拽
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      const file = e.dataTransfer.files?.[0];
      if (file) applyFile(file);
    },
    [applyFile]
  );

  // 提交
  const handleSubmit = useCallback(() => {
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > MAX_NAME_LENGTH) {
      setValidation("error");
      return;
    }
    void onConfirm(trimmed, avatarFile);
  }, [name, avatarFile, onConfirm]);

  const onInputKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  if (!isOpen) return null;

  const showError = validation === "error";
  const nameLength = name.length;
  const overLength = nameLength > MAX_NAME_LENGTH;
  const avatarUrl = avatarPreviewUrl || defaultAvatarUrl;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-chara-title"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-rose-900/20 backdrop-blur-sm" />

      <div
        className="relative w-full max-w-sm rounded-3xl border border-rose-100/70 shadow-2xl overflow-hidden"
        style={{
          background: "rgba(255,255,255,0.72)",
          WebkitBackdropFilter: "blur(16px)",
          backdropFilter: "blur(16px)",
          boxShadow:
            "0 25px 50px -12px rgba(244,114,182,0.22), 0 0 0 1px rgba(255,255,255,0.6) inset",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 顶部装饰线 */}
        <div className="absolute top-0 left-5 right-5 h-1 rounded-b-full bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300" />

        {/* 浮动星星装饰 */}
        <div className="absolute top-3 right-4 w-5 h-5 flex items-center justify-center text-rose-300/55 pointer-events-none">
          <i className="ri-star-fill text-sm animate-pulse" />
        </div>
        <div
          className="absolute bottom-3 left-4 w-4 h-4 flex items-center justify-center text-pink-300/45 pointer-events-none"
          style={{ animation: "cuteModalTwinkle 2.2s ease-in-out infinite" }}
        >
          <i className="ri-sparkling-fill text-xs" />
        </div>
        <div
          className="absolute top-10 left-5 w-3 h-3 flex items-center justify-center text-amber-200/50 pointer-events-none"
          style={{ animation: "cuteModalTwinkle 2.8s ease-in-out infinite 0.5s" }}
        >
          <i className="ri-star-fill text-[10px]" />
        </div>

        <div className="px-6 pt-8 pb-6">
          {/* 标题 */}
          <h3
            id="create-chara-title"
            className="text-center text-lg font-semibold text-rose-700 mb-5"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <span className="inline-flex items-center gap-1.5">
              <i className="ri-heart-add-line text-pink-400" />
              新建小女友
            </span>
          </h3>

          {/* 头像上传区 */}
          <div className="mb-5">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => onFileChange(e.target.files)}
            />

            <div
              className={[
                "relative mx-auto w-28 h-28 rounded-2xl overflow-hidden cursor-pointer border-2 transition-all duration-200",
                dragActive
                  ? "border-pink-400 bg-pink-50/80"
                  : "border-rose-200 hover:border-pink-300",
              ].join(" ")}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
            >
              <img src={avatarUrl} alt="" className="w-full h-full object-cover" draggable={false} />

              {/* 悬停/拖拽遮罩 */}
              <div
                className={[
                  "absolute inset-0 flex flex-col items-center justify-center transition-opacity duration-200",
                  dragActive ? "opacity-100 bg-pink-50/80" : "opacity-0 hover:opacity-100 bg-rose-900/20",
                ].join(" ")}
              >
                <span className="text-white/90 text-2xl mb-1">
                  <i className={dragActive ? "ri-add-box-fill" : "ri-camera-line"} />
                </span>
                <span className="text-white/90 text-[11px]">
                  {dragActive ? "松开上传" : avatarFile ? "更换头像" : "点击/拖拽上传"}
                </span>
              </div>

              {/* 移除按钮 */}
              {avatarFile && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeAvatar();
                  }}
                  className="absolute top-1.5 right-1.5 w-7 h-7 flex items-center justify-center rounded-lg bg-black/40 text-white hover:bg-black/60 transition-colors"
                >
                  <i className="ri-close-line" />
                </button>
              )}
            </div>

            <p className="mt-2 text-center text-[11px] text-rose-300/80">
              支持 JPG / PNG / WEBP，可选
            </p>
          </div>

          {/* 名称输入 */}
          <div className="mb-1">
            <label htmlFor="chara-name" className="block text-xs text-rose-400/80 mb-1.5">
              角色名称
            </label>
            <div className="relative">
              <input
                ref={inputRef}
                id="chara-name"
                type="text"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (validation !== "idle") setValidation("idle");
                }}
                onKeyDown={onInputKeyDown}
                maxLength={50}
                className={[
                  "w-full px-3 py-2.5 rounded-xl text-sm text-rose-900/80 placeholder:text-rose-300/60 outline-none transition-all",
                  showError
                    ? "border-2 border-rose-300 bg-rose-50/70 ring-2 ring-rose-200/80"
                    : "border border-rose-200 bg-white/70 focus:border-pink-300 focus:ring-2 focus:ring-pink-200/80",
                ].join(" ")}
                placeholder="给她起个可爱的名字吧"
              />
              <div
                className={[
                  "absolute right-3 top-1/2 -translate-y-1/2 text-[10px] tabular-nums",
                  overLength ? "text-rose-400" : "text-rose-300/70",
                ].join(" ")}
              >
                {nameLength} / {MAX_NAME_LENGTH}
              </div>
            </div>

            {showError && (
              <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-rose-400">
                <i className="ri-error-warning-line" />
                <span>{!name.trim() ? "请输入角色名称" : `最多 ${MAX_NAME_LENGTH} 个字哦`}</span>
              </div>
            )}
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="px-6 pb-6 flex items-center gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium text-rose-500/80 bg-rose-50/90 border border-rose-100/70 hover:bg-rose-100/70 hover:text-rose-600 cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            <span className="flex items-center justify-center gap-1">
              <i className="ri-close-line" />
              取消
            </span>
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium text-white bg-gradient-to-r from-pink-400 to-rose-400 hover:opacity-92 active:scale-[0.98] cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              fontFamily: "'ZCOOL KuaiLe', cursive",
              boxShadow: "0 4px 16px rgba(244,114,182,0.35)",
            }}
          >
            <span className="flex items-center justify-center gap-1">
              <i className="ri-check-line" />
              确认创建
            </span>
          </button>
        </div>
      </div>

      <style>{`
        @keyframes cuteModalTwinkle {
          0%, 100% { opacity: 0.35; transform: scale(1) rotate(0deg); }
          50% { opacity: 0.85; transform: scale(1.15) rotate(12deg); }
        }
      `}</style>
    </div>
  );
};

export default CreateCharaModal;
