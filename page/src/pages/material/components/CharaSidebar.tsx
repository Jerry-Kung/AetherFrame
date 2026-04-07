import type { CharaProfile } from "@/types/material";
import { STATUS_LABEL, STATUS_STYLE } from "@/types/material";

interface CharaSidebarProps {
  chara: CharaProfile | null;
  onEdit: () => void;
  onStartProcess: () => void;
  onExport: () => void;
}

function briefSummary(c: CharaProfile): string {
  const t = c.settingText.trim();
  if (!t) return "还没有写入设定说明，去「原始资料」里补充吧。";
  const one = t.replace(/\s+/g, " ").slice(0, 72);
  return one.length < t.length ? `${one}…` : one;
}

const CharaSidebar = ({ chara, onEdit, onStartProcess, onExport }: CharaSidebarProps) => {
  if (!chara) {
    return (
      <div className="flex flex-col h-full items-center justify-center px-4 text-center">
        <span className="text-4xl opacity-25 mb-3 select-none">🌷</span>
        <p className="text-xs text-rose-300/70 leading-relaxed">先选一个角色，右侧会显示档案摘要</p>
      </div>
    );
  }

  const st = STATUS_STYLE[chara.status];

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-4 pt-4 pb-3 shrink-0">
        <h3
          className="text-sm font-semibold text-rose-700/80 tracking-wide"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <span className="w-4 h-4 inline-flex items-center justify-center mr-1 text-rose-400">
            <i className="ri-profile-line text-sm" />
          </span>
          角色档案
        </h3>
      </div>
      <div className="mx-4 h-px bg-rose-100/80 shrink-0" />

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        <div className="flex flex-col items-center text-center">
          <div className="relative w-24 h-24 rounded-2xl overflow-hidden border-2 border-rose-100 shadow-sm">
            <img src={chara.avatarUrl} alt="" className="w-full h-full object-cover" draggable={false} />
          </div>
          <div className="mt-3 flex items-center justify-center gap-2">
            <span className={`w-2 h-2 rounded-full ${st.dot}`} />
            <span
              className="text-base font-semibold text-rose-900/85"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              {chara.name}
            </span>
          </div>
          <p className={`mt-1 text-xs font-medium ${st.text}`}>{STATUS_LABEL[chara.status]}</p>
        </div>

        <div
          className="rounded-xl px-3 py-2.5 text-left"
          style={{ background: "rgba(255,250,252,0.9)", border: "1px solid rgba(251,113,133,0.12)" }}
        >
          <p className="text-[10px] uppercase tracking-wider text-rose-300/80 mb-1">资料小结</p>
          <p className="text-xs text-rose-600/75 leading-relaxed">{briefSummary(chara)}</p>
        </div>

        <div className="grid grid-cols-1 gap-2 text-xs">
          <div className="flex items-center justify-between rounded-lg bg-white/50 px-3 py-2 border border-rose-100/60">
            <span className="text-rose-400/80">参考图</span>
            <span className="font-semibold text-rose-700 tabular-nums">{chara.rawImages.length} 张</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-white/50 px-3 py-2 border border-rose-100/60">
            <span className="text-rose-400/80">标准照</span>
            <span className="font-semibold text-rose-700 tabular-nums">
              {chara.officialPhotos.filter(Boolean).length} / 3
            </span>
          </div>
        </div>
      </div>

      <div className="shrink-0 p-4 pt-2 space-y-2 border-t border-rose-100/60">
        <button
          type="button"
          onClick={onEdit}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all border border-rose-200/80 text-rose-600 hover:bg-rose-50/80"
        >
          <i className="ri-edit-2-line" />
          编辑角色信息
        </button>
        <button
          type="button"
          onClick={onStartProcess}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold cursor-pointer text-white transition-all"
          style={{
            background: "linear-gradient(135deg, #f472b6, #ec4899)",
            fontFamily: "'ZCOOL KuaiLe', cursive",
            boxShadow: "0 4px 14px rgba(244,114,182,0.35)",
          }}
        >
          <i className="ri-magic-line" />
          开始加工任务
        </button>
        <button
          type="button"
          onClick={onExport}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-xs font-medium cursor-pointer text-rose-400/80 hover:text-rose-600 hover:bg-rose-50/50 transition-colors"
        >
          <i className="ri-download-2-line" />
          导出角色档案
        </button>
      </div>
    </div>
  );
};

export default CharaSidebar;
