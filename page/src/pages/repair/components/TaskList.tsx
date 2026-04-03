import type { RepairTask, TaskStatus } from "@/types/repair";

const STATUS_CONFIG: Record<TaskStatus, { label: string; dot: string; text: string; bg: string }> = {
  pending: {
    label: "未开始",
    dot: "bg-gray-300",
    text: "text-gray-400",
    bg: "bg-gray-50",
  },
  processing: {
    label: "处理中",
    dot: "bg-amber-400 animate-pulse",
    text: "text-amber-500",
    bg: "bg-amber-50/60",
  },
  completed: {
    label: "已完成",
    dot: "bg-rose-400",
    text: "text-rose-500",
    bg: "bg-rose-50/60",
  },
  failed: {
    label: "失败",
    dot: "bg-red-300",
    text: "text-red-400",
    bg: "bg-red-50/40",
  },
};

interface TaskListProps {
  tasks: RepairTask[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
}

const TaskList = ({ tasks, selectedId, onSelect, onDelete, onNew }: TaskListProps) => {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3 shrink-0">
        <h2
          className="text-base font-semibold text-rose-700/80 tracking-wide"
          style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
        >
          <span className="w-4 h-4 inline-flex items-center justify-center mr-1.5 text-rose-400">
            <i className="ri-list-check-2 text-sm"></i>
          </span>
          修补任务
        </h2>
        <button
          onClick={onNew}
          className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap cursor-pointer transition-all duration-200 hover:scale-105 active:scale-95"
          style={{
            background: "linear-gradient(135deg, #f472b6 0%, #ec4899 100%)",
            color: "white",
          }}
        >
          <span className="w-3.5 h-3.5 flex items-center justify-center">
            <i className="ri-add-line"></i>
          </span>
          新建
        </button>
      </div>

      {/* Divider */}
      <div className="mx-4 h-px bg-rose-100/80 shrink-0" />

      {/* Task list */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 min-h-0">
        {tasks.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <span className="text-3xl mb-2 opacity-30 select-none">🌸</span>
            <p className="text-xs text-rose-300/60">暂无任务，点击新建开始</p>
          </div>
        )}

        {tasks.map((task) => {
          const cfg = STATUS_CONFIG[task.status];
          const isSelected = selectedId === task.id;
          return (
            <div
              key={task.id}
              onClick={() => onSelect(task.id)}
              className={[
                "group relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200",
                isSelected
                  ? "bg-gradient-to-r from-pink-50 to-rose-50 border border-rose-200/70"
                  : "hover:bg-pink-50/60 border border-transparent",
              ].join(" ")}
            >
              {/* Selected indicator */}
              {isSelected && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full bg-gradient-to-b from-pink-400 to-rose-400" />
              )}

              {/* Status dot */}
              <span className={`shrink-0 w-2 h-2 rounded-full ${cfg.dot}`} />

              {/* Task name */}
              <div className="flex-1 min-w-0">
                <p
                  className={`text-sm truncate ${isSelected ? "text-rose-700 font-medium" : "text-rose-900/60"}`}
                >
                  {task.name}
                </p>
                <span
                  className={`inline-block mt-0.5 text-xs px-1.5 py-px rounded-full ${cfg.text} ${cfg.bg}`}
                >
                  {cfg.label}
                </span>
              </div>

              {/* Delete task：触屏设备始终可见；桌面端悬停行时显示 */}
              <button
                type="button"
                title="删除任务"
                aria-label={`删除任务 ${task.name}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(task.id);
                }}
                className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity duration-150 hover:bg-rose-100 cursor-pointer text-rose-300 hover:text-rose-500"
              >
                <i className="ri-delete-bin-6-line text-sm"></i>
              </button>
            </div>
          );
        })}
      </div>

      {/* Footer decoration */}
      <div className="px-4 pb-3 shrink-0">
        <p className="text-xs text-rose-300/40 text-center">
          共 {tasks.length} 个任务
        </p>
      </div>
    </div>
  );
};

export default TaskList;
