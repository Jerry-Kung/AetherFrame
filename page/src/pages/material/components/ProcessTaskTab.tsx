import type { CharaProfile } from "@/types/material";
import PhotoTaskPage from "./PhotoTaskPage";

export type ProcessSubTaskId = "standard" | "profile";

interface ProcessTaskTabProps {
  subTask: ProcessSubTaskId;
  onSubTaskChange: (id: ProcessSubTaskId) => void;
  charaName: string;
  chara?: CharaProfile;
}

const SUB_TASKS: { id: ProcessSubTaskId; label: string; icon: string; desc: string }[] = [
  {
    id: "standard",
    label: "拍摄标准照",
    icon: "ri-camera-lens-line",
    desc: "根据原始资料与参考图，生成三张统一风格的标准参考照（正面 / 半身 / 全身或指定构图）。",
  },
  {
    id: "profile",
    label: "角色小档案",
    icon: "ri-file-list-3-line",
    desc: "从设定文本中抽取或补全结构化字段，生成可在「正式内容」中展示的小档案卡片。",
  },
];

const ProcessTaskTab = ({ subTask, onSubTaskChange, charaName, chara }: ProcessTaskTabProps) => {
  const active = SUB_TASKS.find((s) => s.id === subTask)!;

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex gap-1 p-1 rounded-2xl shrink-0 bg-rose-50/80 border border-rose-100/70">
        {SUB_TASKS.map((s) => {
          const on = subTask === s.id;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => onSubTaskChange(s.id)}
              className={[
                "flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-sm transition-all duration-200 cursor-pointer min-w-0",
                on
                  ? "bg-white text-rose-600 shadow-sm border border-rose-100 font-semibold"
                  : "text-rose-400/70 hover:text-rose-500 hover:bg-white/50",
              ].join(" ")}
              style={on ? { fontFamily: "'ZCOOL KuaiLe', cursive" } : undefined}
            >
              <i className={`${s.icon} shrink-0`} />
              <span className="truncate">{s.label}</span>
            </button>
          );
        })}
      </div>

      <div className="flex-1 min-h-0 mt-4 rounded-2xl border border-dashed border-rose-200/80 bg-gradient-to-br from-white/60 to-pink-50/30 overflow-hidden flex flex-col">
        {subTask === "standard" && chara ? (
          <PhotoTaskPage rawImages={chara.rawImages} />
        ) : (
          <div className="p-6 flex flex-col items-center justify-center flex-1 text-center min-h-[200px]">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4 text-rose-400"
              style={{
                background: "linear-gradient(135deg, rgba(244,114,182,0.12), rgba(251,113,133,0.08))",
                border: "1px solid rgba(251,113,133,0.15)",
              }}
            >
              <i className={`${active.icon} text-2xl`} />
            </div>
            <h3
              className="text-lg font-semibold text-rose-800/80 mb-2"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              {active.label}
            </h3>
            <p className="text-sm text-rose-500/70 max-w-md leading-relaxed mb-2">
              正在为 <span className="font-medium text-rose-600">{charaName}</span> 准备该流程。
              {active.desc}
            </p>
            <p className="text-xs text-rose-300/80 mt-4 px-4 py-2 rounded-full bg-white/50 border border-rose-100/60">
              后续将在此接入具体步骤：参数表单、进度与结果预览等
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProcessTaskTab;
