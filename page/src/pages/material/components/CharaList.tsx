import type { CharaProfile } from "@/mocks/materialChara";
import { STATUS_LABEL, STATUS_STYLE } from "@/mocks/materialChara";

function formatUpdatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 60000) return "刚刚";
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

interface CharaListProps {
  charas: CharaProfile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDeleteConfirm: (id: string) => void;
  onNew: () => void;
}

const CharaList = ({ charas, selectedId, onSelect, onDeleteConfirm, onNew }: CharaListProps) => {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 pt-4 pb-3 shrink-0 gap-2">
        <h2
          className="text-sm font-semibold text-rose-700/85 tracking-wide min-w-0 truncate"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <span className="w-4 h-4 inline-flex items-center justify-center mr-1 text-rose-400 shrink-0">
            <i className="ri-heart-2-line text-sm" />
          </span>
          你的小女友们
        </h2>
        <button
          type="button"
          onClick={onNew}
          className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap cursor-pointer transition-all duration-200 hover:scale-105 active:scale-95 shrink-0"
          style={{
            background: "linear-gradient(135deg, #f472b6 0%, #ec4899 100%)",
            color: "white",
          }}
        >
          <span className="w-3.5 h-3.5 flex items-center justify-center">
            <i className="ri-add-line" />
          </span>
          新建
        </button>
      </div>

      <div className="mx-4 h-px bg-rose-100/80 shrink-0" />

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 min-h-0">
        {charas.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <span className="text-3xl mb-2 opacity-30 select-none">💗</span>
            <p className="text-xs text-rose-300/70">还没有角色，点「新建」开始</p>
          </div>
        )}

        {charas.map((c) => {
          const st = STATUS_STYLE[c.status];
          const isSelected = selectedId === c.id;
          return (
            <div
              key={c.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(c.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(c.id);
                }
              }}
              className={[
                "group relative flex items-center gap-2.5 pl-3 pr-2 py-2.5 rounded-xl cursor-pointer transition-all duration-200",
                isSelected
                  ? "bg-gradient-to-r from-pink-50 to-rose-50 border border-rose-200/70"
                  : "hover:bg-pink-50/60 border border-transparent",
              ].join(" ")}
            >
              {isSelected && (
                <div
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 rounded-full"
                  style={{
                    background: "linear-gradient(180deg, #f472b6, #ec4899)",
                    boxShadow: "0 0 8px rgba(244,114,182,0.5)",
                  }}
                />
              )}

              <div className="shrink-0 w-11 h-11 rounded-xl overflow-hidden border border-rose-100/80 bg-rose-50/50">
                <img src={c.avatarUrl} alt="" className="w-full h-full object-cover" draggable={false} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span
                    className={`shrink-0 w-1.5 h-1.5 rounded-full ${st.dot}`}
                    title={STATUS_LABEL[c.status]}
                  />
                  <span
                    className="text-sm font-medium text-rose-900/80 truncate"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    {c.name}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 flex-wrap">
                  <span
                    className={`inline-flex text-[10px] px-1.5 py-0.5 rounded-md font-medium ${st.badgeBg} ${st.badgeText}`}
                  >
                    {STATUS_LABEL[c.status]}
                  </span>
                  <span className="text-[10px] text-rose-300/80 tabular-nums">{formatUpdatedAt(c.updatedAt)}</span>
                </div>
              </div>

              <button
                type="button"
                title="删除角色"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteConfirm(c.id);
                }}
                className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg text-rose-300 hover:text-rose-500 hover:bg-rose-100/80 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
              >
                <i className="ri-delete-bin-6-line text-sm" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CharaList;
