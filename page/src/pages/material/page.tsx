import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { CharaProfile } from "@/types/material";
import { DEFAULT_CHARA_AVATAR_PLACEHOLDER, toCharaProfile, summaryToListProfile } from "@/types/material";
import * as materialApi from "@/services/materialApi";
import { ApiError } from "@/services/api";
import CuteConfirmModal from "@/pages/repair/components/CuteConfirmModal";
import ImagePreviewModal from "@/pages/repair/components/ImagePreviewModal";
import CreateCharaModal from "./components/CreateCharaModal";
import CharaList from "./components/CharaList";
import CharaSidebar from "./components/CharaSidebar";
import RawMaterialTab from "./components/RawMaterialTab";
import ProcessTaskTab, { type ProcessSubTaskId } from "./components/ProcessTaskTab";
import OfficialContentTab from "./components/OfficialContentTab";

const decorations = [
  { size: 280, top: "-6%", left: "-5%", opacity: 0.15, delay: "0s" },
  { size: 180, top: "65%", left: "-3%", opacity: 0.1, delay: "1.4s" },
  { size: 220, top: "-4%", right: "-5%", opacity: 0.13, delay: "0.7s" },
  { size: 140, top: "72%", right: "-3%", opacity: 0.09, delay: "2s" },
];

const sparkles = [
  { top: "8%", left: "14%", size: 12, delay: "0s" },
  { top: "20%", right: "18%", size: 9, delay: "0.9s" },
  { top: "72%", left: "9%", size: 7, delay: "1.6s" },
  { top: "82%", right: "14%", size: 11, delay: "2.3s" },
];

type MainTabId = "raw" | "process" | "official";

const MAIN_TABS: { id: MainTabId; label: string; icon: string }[] = [
  { id: "raw", label: "原始资料", icon: "ri-folder-user-line" },
  { id: "process", label: "加工任务", icon: "ri-hammer-line" },
  { id: "official", label: "正式内容", icon: "ri-trophy-line" },
];

const SETTING_DEBOUNCE_MS = 600;

function downloadDataUrl(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export default function MaterialPage() {
  const navigate = useNavigate();
  const [charas, setCharas] = useState<CharaProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [mainTab, setMainTab] = useState<MainTabId>("raw");
  const [processSubTask, setProcessSubTask] = useState<ProcessSubTaskId>("standard");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDisplayName, setEditDisplayName] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ urls: string[]; index: number; altPrefix: string } | null>(
    null
  );

  const settingDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3200);
  }, []);

  const mergeChara = useCallback((profile: CharaProfile) => {
    setCharas((prev) => {
      const i = prev.findIndex((c) => c.id === profile.id);
      if (i < 0) return [...prev, profile];
      const next = [...prev];
      next[i] = profile;
      return next;
    });
  }, []);

  const patchCharaFields = useCallback((id: string, patch: Partial<CharaProfile>) => {
    setCharas((prev) =>
      prev.map((c) =>
        c.id === id ? { ...c, ...patch, updatedAt: new Date().toISOString() } : c
      )
    );
  }, []);

  const loadCharacterList = useCallback(async () => {
    setListLoading(true);
    try {
      const { characters } = await materialApi.listCharacters(0, 100);
      const stubs = characters.map(summaryToListProfile);
      setCharas(stubs);
      setSelectedId((prev) => {
        if (stubs.length === 0) return null;
        if (prev && stubs.some((s) => s.id === prev)) return prev;
        return stubs[0].id;
      });
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "加载角色列表失败");
      setCharas([]);
      setSelectedId(null);
    } finally {
      setListLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    void loadCharacterList();
  }, [loadCharacterList]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    (async () => {
      try {
        const d = await materialApi.getCharacter(selectedId);
        if (cancelled) return;
        mergeChara(toCharaProfile(d));
      } catch (e) {
        if (!cancelled) {
          showToast(e instanceof ApiError ? e.message : "加载角色详情失败");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId, mergeChara, showToast]);

  useEffect(() => {
    if (settingDebounceRef.current) {
      clearTimeout(settingDebounceRef.current);
      settingDebounceRef.current = null;
    }
  }, [selectedId]);

  const selected = useMemo(
    () => charas.find((c) => c.id === selectedId) ?? null,
    [charas, selectedId]
  );

  useEffect(() => {
    if (selectedId && !charas.some((c) => c.id === selectedId)) {
      setSelectedId(charas[0]?.id ?? null);
    }
  }, [charas, selectedId]);

  const handleSelect = useCallback((id: string) => setSelectedId(id), []);

  const handleNew = useCallback(() => {
    setCreateModalOpen(true);
  }, []);

  const handleCreateConfirm = useCallback(
    async (name: string, avatarFile: File | null) => {
      try {
        const d = await materialApi.createCharacter({ name, display_name: name });
        let p = toCharaProfile(d);
        if (avatarFile) {
          await materialApi.postRawImages(p.id, [avatarFile], [["立绘"]]);
          const d2 = await materialApi.getCharacter(p.id);
          p = toCharaProfile(d2);
        }
        mergeChara(p);
        setSelectedId(p.id);
        setCreateModalOpen(false);
        showToast(`已创建「${p.name}」`);
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "创建角色失败");
      }
    },
    [mergeChara, showToast]
  );

  const handleDeleteRequest = useCallback(
    (id: string) => {
      const c = charas.find((x) => x.id === id);
      setDeleteTarget({ id, name: c?.name ?? id });
    },
    [charas]
  );

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    const { id } = deleteTarget;
    try {
      await materialApi.deleteCharacter(id);
      const nextList = charas.filter((c) => c.id !== id);
      setCharas(nextList);
      setDeleteTarget(null);
      setSelectedId((sel) => (sel === id ? nextList[0]?.id ?? null : sel));
      showToast("已删除角色");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "删除失败");
    }
  }, [deleteTarget, charas, showToast]);

  const openEdit = useCallback(() => {
    if (!selected) return;
    setEditName(selected.name);
    setEditDisplayName(selected.bio.displayName);
    setEditOpen(true);
  }, [selected]);

  const saveEdit = useCallback(async () => {
    if (!selected) return;
    const name = editName.trim() || selected.name;
    const displayName = editDisplayName.trim() || selected.bio.displayName;
    try {
      const d = await materialApi.patchCharacter(selected.id, {
        name,
        display_name: displayName,
      });
      mergeChara(toCharaProfile(d));
      setEditOpen(false);
      showToast("角色信息已更新");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "更新失败");
    }
  }, [selected, editName, editDisplayName, mergeChara, showToast]);

  const handleStartProcess = useCallback(() => {
    showToast("加工流程将接入后端后在此展开，敬请期待");
    setMainTab("process");
  }, [showToast]);

  const handleExport = useCallback(() => {
    if (!selected) return;
    const blob = new Blob([JSON.stringify(selected, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    downloadDataUrl(url, `${selected.name}-档案.json`);
    URL.revokeObjectURL(url);
    showToast("已导出 JSON 档案（本地预览用）");
  }, [selected, showToast]);

  const handleSettingTextChange = useCallback(
    (v: string) => {
      if (!selected) return;
      const id = selected.id;
      patchCharaFields(id, { settingText: v });
      if (settingDebounceRef.current) clearTimeout(settingDebounceRef.current);
      settingDebounceRef.current = setTimeout(() => {
        settingDebounceRef.current = null;
        void (async () => {
          try {
            const d = await materialApi.putSettingText(id, v);
            mergeChara(toCharaProfile(d));
          } catch (e) {
            showToast(e instanceof ApiError ? e.message : "保存设定失败");
          }
        })();
      }, SETTING_DEBOUNCE_MS);
    },
    [selected, patchCharaFields, mergeChara, showToast]
  );

  const handleImportSettingFile = useCallback(
    async (file: File) => {
      if (!selected) return;
      try {
        const d = await materialApi.putSettingFile(selected.id, file);
        mergeChara(toCharaProfile(d));
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "上传设定文件失败");
      }
    },
    [selected, mergeChara, showToast]
  );

  const handleUploadRawFiles = useCallback(
    async (files: File[]) => {
      if (!selected || files.length === 0) return;
      const tags = files.map(() => ["其他"] as string[]);
      try {
        await materialApi.postRawImages(selected.id, files, tags);
        const d = await materialApi.getCharacter(selected.id);
        mergeChara(toCharaProfile(d));
        showToast(`已上传 ${files.length} 张参考图`);
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "上传参考图失败");
      }
    },
    [selected, mergeChara, showToast]
  );

  const handleRemoveRawImage = useCallback(
    async (imageId: string) => {
      if (!selected) return;
      try {
        await materialApi.deleteRawImage(selected.id, imageId);
        const d = await materialApi.getCharacter(selected.id);
        mergeChara(toCharaProfile(d));
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "删除图片失败");
      }
    },
    [selected, mergeChara, showToast]
  );

  const handleUpdateRawImageTags = useCallback(
    async (imageId: string, tags: string[]) => {
      if (!selected) return;
      try {
        const d = await materialApi.patchRawImageTags(selected.id, imageId, tags);
        mergeChara(toCharaProfile(d));
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "更新标签失败");
      }
    },
    [selected, mergeChara, showToast]
  );

  const handleRawImageClick = useCallback(
    (imageId: string) => {
      if (!selected) return;
      const urls = selected.rawImages.map((r) => r.url);
      const idx = selected.rawImages.findIndex((r) => r.id === imageId);
      if (idx < 0) return;
      setPreview({ urls, index: idx, altPrefix: "参考图" });
    },
    [selected]
  );

  const handleOfficialPhotoClick = useCallback(
    (slotIndex: number) => {
      if (!selected) return;
      const url = selected.officialPhotos[slotIndex];
      if (!url) return;
      const urls = selected.officialPhotos.filter((x): x is string => !!x);
      const index = urls.indexOf(url);
      setPreview({ urls, index: Math.max(0, index), altPrefix: "标准参考照" });
    },
    [selected]
  );

  const onPreviewDownload = useCallback((url: string, idx: number) => {
    const name = `image-${idx + 1}.png`;
    try {
      downloadDataUrl(url, name);
    } catch {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  }, []);

  return (
    <div
      className="relative h-screen w-full overflow-hidden flex flex-col"
      style={{
        background:
          "linear-gradient(145deg, #fff5f7 0%, #fffaf5 45%, #fef2f8 80%, #fff8f0 100%)",
      }}
    >
      <div
        className="absolute inset-0 z-0 pointer-events-none"
        style={{
          backgroundImage:
            'url("https://readdy.ai/api/search-image?query=soft%20dreamy%20anime%20aesthetic%20background%20art%20with%20delicate%20cherry%20blossom%20sakura%20petals%20floating%20in%20gentle%20breeze%2C%20warm%20pastel%20pink%20and%20creamy%20white%20watercolor%20illustration%20style%2C%20kawaii%20japanese%20aesthetic%2C%20soft%20bokeh%20circular%20lights%2C%20no%20people%20no%20characters%2C%20light%20and%20airy%20misty%20atmosphere%2C%20subtle%20floral%20pattern%20elements%2C%20beautiful%20pastel%20digital%20painting%20art%20with%20pink%20rose%20tones&width=1920&height=1080&seq=2001&orientation=landscape")',
          backgroundSize: "cover",
          backgroundPosition: "center",
          opacity: 0.1,
        }}
      />

      {decorations.map((d, i) => (
        <div
          key={i}
          className="absolute rounded-full pointer-events-none"
          style={{
            width: d.size,
            height: d.size,
            top: d.top,
            left: (d as { left?: string }).left,
            right: (d as { right?: string }).right,
            opacity: d.opacity,
            background:
              i % 2 === 0
                ? "radial-gradient(circle, #fda4af 0%, #fecdd3 60%, transparent 100%)"
                : "radial-gradient(circle, #fbcfe8 0%, #fce7f3 60%, transparent 100%)",
            animation: "floatUp 8s ease-in-out infinite",
            animationDelay: d.delay,
          }}
        />
      ))}

      {sparkles.map((s, i) => (
        <div
          key={i}
          className="absolute pointer-events-none text-rose-300/40 select-none"
          style={{
            top: s.top,
            left: (s as { left?: string }).left,
            right: (s as { right?: string }).right,
            fontSize: s.size,
            animation: "twinkle 3s ease-in-out infinite",
            animationDelay: s.delay,
          }}
        >
          <i className="ri-star-fill" />
        </div>
      ))}

      {toast && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl bg-white/95 border border-rose-100 shadow-lg">
          <span className="text-sm text-rose-600">{toast}</span>
        </div>
      )}

      <div className="relative z-10 flex flex-col h-full">
        <div className="flex items-center justify-between px-7 pt-5 pb-4 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => navigate("/")}
              className="flex items-center justify-center w-8 h-8 rounded-full cursor-pointer transition-all hover:bg-rose-100/60 text-rose-400/70 hover:text-rose-500 shrink-0"
            >
              <i className="ri-arrow-left-s-line text-lg" />
            </button>
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="flex items-center justify-center w-7 h-7 rounded-xl text-white text-sm shrink-0"
                style={{ background: "linear-gradient(135deg, #f472b6, #ec4899)" }}
              >
                <i className="ri-scissors-cut-line text-xs" />
              </span>
              <h1
                className="text-lg font-semibold text-transparent bg-clip-text truncate"
                style={{
                  backgroundImage: "linear-gradient(135deg, #f472b6 0%, #ec4899 60%, #db2777 100%)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                素材加工
              </h1>
            </div>
          </div>
          <span
            className="text-xs tracking-wide hidden md:block truncate max-w-[40%] text-right"
            style={{ color: "rgba(244,114,182,0.45)", fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            以角色为中心，整理设定与参考，生成标准档案
          </span>
          <div className="w-8 shrink-0" />
        </div>

        <div className="flex-1 flex flex-col px-6 pb-6 min-h-0">
          <div
            className="relative flex-1 flex flex-row min-h-0 overflow-hidden rounded-3xl border border-rose-100/80"
            style={{
              background: "rgba(255,255,255,0.55)",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
            }}
          >
            <div className="absolute left-0 right-0 top-0 h-[3px] rounded-b-full bg-gradient-to-r from-rose-300 via-pink-400 to-rose-300 opacity-70 pointer-events-none z-10" />

            <div
              className="w-[13.5rem] shrink-0 border-r border-rose-100/60 flex flex-col min-h-0 pt-1 relative z-0"
              style={{ background: "rgba(255,250,252,0.6)" }}
            >
              {listLoading ? (
                <div className="flex-1 flex items-center justify-center text-xs text-rose-300/70">
                  加载中…
                </div>
              ) : (
                <CharaList
                  charas={charas}
                  selectedId={selectedId}
                  onSelect={handleSelect}
                  onDeleteRequest={handleDeleteRequest}
                  onNew={handleNew}
                />
              )}
            </div>

            <div className="flex-1 flex flex-col min-h-0 border-r border-rose-100/60 pt-1 relative z-0" style={{ minWidth: 0 }}>
              <div className="px-5 pt-3 pb-2 shrink-0 flex flex-col gap-2 min-w-0">
                <nav className="flex items-center gap-1.5 text-xs text-rose-400/70 min-w-0 flex-wrap">
                  <span className="shrink-0">素材加工</span>
                  <i className="ri-arrow-right-s-line shrink-0 opacity-50" />
                  <span className="font-medium text-rose-600/80 truncate" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
                    {selected ? selected.name : "未选择角色"}
                  </span>
                </nav>
                <div className="flex gap-1 p-1 rounded-2xl bg-rose-50/60 border border-rose-100/50 w-full max-w-xl">
                  {MAIN_TABS.map((t) => {
                    const on = mainTab === t.id;
                    return (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setMainTab(t.id)}
                        className={[
                          "flex-1 flex items-center justify-center gap-1.5 py-2 px-2 rounded-xl text-xs sm:text-sm transition-all cursor-pointer min-w-0",
                          on
                            ? "bg-white text-rose-600 shadow-sm border border-rose-100 font-semibold"
                            : "text-rose-400/70 hover:text-rose-500 hover:bg-white/40",
                        ].join(" ")}
                        style={on ? { fontFamily: "'ZCOOL KuaiLe', cursive" } : undefined}
                      >
                        <i className={`${t.icon} shrink-0`} />
                        <span className="truncate">{t.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="mx-5 h-px bg-rose-100/60 shrink-0" />

              <div className="flex-1 min-h-0 overflow-hidden px-5 py-4">
                {!selected ? (
                  <div className="h-full flex items-center justify-center text-rose-300/50 text-sm select-none">
                    ← 请先选择或新建一位角色
                  </div>
                ) : mainTab === "raw" ? (
                  <RawMaterialTab
                    characterId={selected.id}
                    settingText={selected.settingText}
                    onSettingTextChange={handleSettingTextChange}
                    onImportSettingFile={handleImportSettingFile}
                    rawImages={selected.rawImages}
                    onUploadRawFiles={handleUploadRawFiles}
                    onRemoveRawImage={handleRemoveRawImage}
                    onUpdateRawImageTags={handleUpdateRawImageTags}
                    onRawImageClick={handleRawImageClick}
                  />
                ) : mainTab === "process" ? (
                  <ProcessTaskTab
                    subTask={processSubTask}
                    onSubTaskChange={setProcessSubTask}
                    charaName={selected.name}
                  />
                ) : (
                  <OfficialContentTab
                    officialPhotos={selected.officialPhotos}
                    bio={selected.bio}
                    onPhotoClick={handleOfficialPhotoClick}
                  />
                )}
              </div>
            </div>

            <div
              className="w-72 shrink-0 flex flex-col min-h-0 pt-1 relative z-0"
              style={{ background: "rgba(255,252,253,0.5)" }}
            >
              <CharaSidebar
                chara={selected}
                onEdit={openEdit}
                onStartProcess={handleStartProcess}
                onExport={handleExport}
              />
            </div>
          </div>
        </div>
      </div>

      <CreateCharaModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onConfirm={handleCreateConfirm}
        defaultAvatarUrl={DEFAULT_CHARA_AVATAR_PLACEHOLDER}
      />

      <CuteConfirmModal
        isOpen={deleteTarget !== null}
        title="确认删除角色？"
        message={
          deleteTarget ? `将删除「${deleteTarget.name}」及服务器上的角色资料与文件。` : ""
        }
        icon="delete"
        confirmText="确认删除"
        cancelText="再想想"
        titleId="material-delete-confirm-title"
        onConfirm={() => void handleDeleteConfirm()}
        onCancel={() => setDeleteTarget(null)}
      />

      {editOpen && selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.4)", backdropFilter: "blur(6px)" }}
          onClick={() => setEditOpen(false)}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-rose-100 bg-white shadow-xl p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-rose-800 mb-4" style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}>
              编辑角色信息
            </h3>
            <label className="block text-xs text-rose-400 mb-1">列表名称</label>
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="w-full mb-3 px-3 py-2 rounded-xl border border-rose-100 text-sm text-rose-900 focus:outline-none focus:ring-2 focus:ring-pink-200/80"
            />
            <label className="block text-xs text-rose-400 mb-1">档案显示名</label>
            <input
              value={editDisplayName}
              onChange={(e) => setEditDisplayName(e.target.value)}
              className="w-full mb-4 px-3 py-2 rounded-xl border border-rose-100 text-sm text-rose-900 focus:outline-none focus:ring-2 focus:ring-pink-200/80"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditOpen(false)}
                className="px-4 py-2 rounded-xl text-sm text-rose-400 hover:bg-rose-50 cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void saveEdit()}
                className="px-4 py-2 rounded-xl text-sm text-white cursor-pointer"
                style={{ background: "linear-gradient(135deg, #f472b6, #ec4899)" }}
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {preview && (
        <ImagePreviewModal
          images={preview.urls}
          currentIndex={preview.index}
          onClose={() => setPreview(null)}
          onIndexChange={(idx) => setPreview((p) => (p ? { ...p, index: idx } : null))}
          onDownload={onPreviewDownload}
          showContinueRepair={false}
          imageAltPrefix={preview.altPrefix}
        />
      )}

      <style>{`
        @keyframes floatUp {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-16px) scale(1.03); }
        }
        @keyframes twinkle {
          0%, 100% { opacity: 0.25; transform: scale(1) rotate(0deg); }
          50% { opacity: 0.6; transform: scale(1.3) rotate(20deg); }
        }
      `}</style>
    </div>
  );
}
