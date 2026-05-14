import { useState } from "react";
import type { SeedPrompt } from "@/types/material";

export interface SeedPromptSectionProps {
  title: string;
  icon: string;
  accentColor: string;
  prompts: SeedPrompt[];
  busyId?: string | null;
  onToggle: (id: string) => void | Promise<void>;
  onDelete: (id: string) => void | Promise<void>;
  onAdd: (text: string) => void | Promise<void>;
  onEdit: (id: string, text: string) => void | Promise<void>;
}

function SeedRow({
  prompt,
  busyId,
  onToggle,
  onDelete,
  onEdit,
  accentColor,
}: {
  prompt: SeedPrompt;
  busyId: string | null;
  onToggle: () => void | Promise<void>;
  onDelete: () => void | Promise<void>;
  onEdit: (text: string) => void | Promise<void>;
  accentColor: string;
}) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(prompt.text);
  const busy = busyId === prompt.id;

  const handleSave = () => {
    const t = editText.trim();
    if (t && t !== prompt.text) {
      void onEdit(t);
    }
    setEditing(false);
  };

  const handleCancel = () => {
    setEditText(prompt.text);
    setEditing(false);
  };

  return (
    <div
      className="flex items-start gap-2.5 px-3 py-2.5 rounded-xl transition-all duration-200"
      style={{
        background: prompt.used ? `${accentColor}0d` : "rgba(253,164,175,0.04)",
        border: `1px solid ${prompt.used ? `${accentColor}33` : "rgba(253,164,175,0.12)"}`,
      }}
    >
      <div className="flex-1 min-w-0">
        {editing ? (
          <div className="flex flex-col gap-1.5">
            <input
              type="text"
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave();
                if (e.key === "Escape") handleCancel();
              }}
              className="w-full text-xs rounded-lg px-2.5 py-1.5 outline-none"
              style={{
                background: "rgba(255,255,255,0.9)",
                border: "1.5px solid rgba(244,114,182,0.35)",
                color: "#7c3f5e",
              }}
              autoFocus
            />
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleSave}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
                style={{
                  background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
                  color: "white",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                <i className="ri-check-line text-xs" />
                保存
              </button>
              <button
                type="button"
                onClick={handleCancel}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
                style={{
                  background: "rgba(253,164,175,0.08)",
                  color: "#f472b6",
                  border: "1px solid rgba(244,114,182,0.2)",
                  fontFamily: "'ZCOOL KuaiLe', cursive",
                }}
              >
                <i className="ri-close-line text-xs" />
                取消
              </button>
            </div>
          </div>
        ) : (
          <p className="text-xs leading-relaxed text-rose-700/80 break-words">{prompt.text}</p>
        )}
      </div>

      {!editing && (
        <div className="shrink-0 flex items-center gap-1 mt-0.5">
          <button
            type="button"
            disabled={busy}
            onClick={() => void onToggle()}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50"
            style={{
              background: prompt.used ? `${accentColor}18` : "rgba(253,164,175,0.08)",
              color: prompt.used ? accentColor : "#fda4af",
              border: `1px solid ${prompt.used ? `${accentColor}40` : "rgba(253,164,175,0.2)"}`,
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
            title={prompt.used ? "取消已使用标记" : "标记为已使用"}
          >
            {prompt.used ? (
              <>
                <i className="ri-check-line text-xs" />
                已使用
              </>
            ) : (
              <>
                <i className="ri-circle-line text-xs" />
                标记使用
              </>
            )}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setEditText(prompt.text);
              setEditing(true);
            }}
            className="w-6 h-6 flex items-center justify-center rounded-lg cursor-pointer transition-all duration-200 disabled:opacity-50"
            style={{
              background: "rgba(253,164,175,0.06)",
              color: "#fda4af",
              border: "1px solid rgba(253,164,175,0.15)",
            }}
            title="修改提示词"
          >
            <i className="ri-edit-line text-xs" />
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void onDelete()}
            className="w-6 h-6 flex items-center justify-center rounded-lg cursor-pointer transition-all duration-200 disabled:opacity-50"
            style={{
              background: "rgba(253,164,175,0.06)",
              color: "#fda4af",
              border: "1px solid rgba(253,164,175,0.15)",
            }}
            title="删除此提示词"
          >
            <i className="ri-delete-bin-line text-xs" />
          </button>
        </div>
      )}
    </div>
  );
}

function AddSeedRow({
  onAdd,
  accentColor,
}: {
  onAdd: (text: string) => void | Promise<void>;
  accentColor: string;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");

  const handleAdd = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    void onAdd(trimmed);
    setText("");
    setOpen(false);
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 whitespace-nowrap"
        style={{
          background: "rgba(253,164,175,0.04)",
          border: "1.5px dashed rgba(253,164,175,0.3)",
          color: "#fda4af",
          fontFamily: "'ZCOOL KuaiLe', cursive",
        }}
      >
        <i className="ri-add-line text-sm" />
        添加提示词
      </button>
    );
  }

  return (
    <div
      className="flex flex-col gap-1.5 px-3 py-2.5 rounded-xl"
      style={{
        background: "rgba(253,164,175,0.06)",
        border: `1.5px dashed ${accentColor}40`,
      }}
    >
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleAdd();
          if (e.key === "Escape") {
            setText("");
            setOpen(false);
          }
        }}
        placeholder="输入新的种子提示词..."
        className="w-full text-xs rounded-lg px-2.5 py-1.5 outline-none"
        style={{
          background: "rgba(255,255,255,0.9)",
          border: "1.5px solid rgba(244,114,182,0.3)",
          color: "#7c3f5e",
        }}
        autoFocus
      />
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={handleAdd}
          disabled={!text.trim()}
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs cursor-pointer transition-all duration-200 whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
            color: "white",
            fontFamily: "'ZCOOL KuaiLe', cursive",
          }}
        >
          <i className="ri-check-line text-xs" />
          确认添加
        </button>
        <button
          type="button"
          onClick={() => {
            setText("");
            setOpen(false);
          }}
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs cursor-pointer transition-all duration-200 whitespace-nowrap"
          style={{
            background: "rgba(253,164,175,0.08)",
            color: "#f472b6",
            border: "1px solid rgba(244,114,182,0.2)",
            fontFamily: "'ZCOOL KuaiLe', cursive",
          }}
        >
          <i className="ri-close-line text-xs" />
          取消
        </button>
      </div>
    </div>
  );
}

export default function SeedPromptSection({
  title,
  icon,
  accentColor,
  prompts,
  busyId = null,
  onToggle,
  onDelete,
  onAdd,
  onEdit,
}: SeedPromptSectionProps) {
  const usedCount = prompts.filter((p) => p.used).length;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ border: `1px solid ${accentColor}33`, background: "rgba(255,255,255,0.7)" }}
    >
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: `${accentColor}22` }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="w-5 h-5 flex items-center justify-center rounded-lg text-white text-xs shrink-0"
            style={{ background: `linear-gradient(135deg, ${accentColor}cc 0%, ${accentColor} 100%)` }}
          >
            <i className={`${icon} text-xs`} />
          </div>
          <span
            className="text-sm font-bold truncate"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive", color: accentColor }}
          >
            {title}
          </span>
          <span
            className="text-xs px-2 py-0.5 rounded-full shrink-0"
            style={{ background: `${accentColor}15`, color: accentColor }}
          >
            {prompts.length} 条
          </span>
        </div>
        {usedCount > 0 && (
          <span
            className="text-xs px-2 py-0.5 rounded-full shrink-0"
            style={{
              background: "rgba(110,231,183,0.15)",
              color: "#059669",
              border: "1px solid rgba(110,231,183,0.3)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
            }}
          >
            已用 {usedCount}/{prompts.length}
          </span>
        )}
      </div>
      <div className="p-3 flex flex-col gap-2">
        {prompts.length === 0 ? (
          <p
            className="text-xs text-center text-rose-300/50 py-3"
            style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
          >
            该分类下暂无提示词
          </p>
        ) : (
          prompts.map((p) => (
            <SeedRow
              key={p.id}
              prompt={p}
              busyId={busyId}
              onToggle={() => onToggle(p.id)}
              onDelete={() => onDelete(p.id)}
              onEdit={(text) => onEdit(p.id, text)}
              accentColor={accentColor}
            />
          ))
        )}
        <AddSeedRow onAdd={onAdd} accentColor={accentColor} />
      </div>
    </div>
  );
}
