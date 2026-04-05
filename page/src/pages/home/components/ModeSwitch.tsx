export type ModeId = "material" | "creation" | "repair";

export interface Mode {
  id: ModeId;
  label: string;
  icon: string;
  activeGradient: string;
  accentColor: string;
}

export const MODES: Mode[] = [
  {
    id: "material",
    label: "素材加工",
    icon: "ri-scissors-cut-line",
    activeGradient: "from-pink-400 to-rose-400",
    accentColor: "#f472b6",
  },
  {
    id: "creation",
    label: "美图创作",
    icon: "ri-magic-line",
    activeGradient: "from-rose-400 to-pink-500",
    accentColor: "#ec4899",
  },
  {
    id: "repair",
    label: "图片修补",
    icon: "ri-eraser-line",
    activeGradient: "from-pink-300 to-rose-400",
    accentColor: "#f9a8d4",
  },
];

interface ModeSwitchProps {
  activeMode: ModeId;
  onSwitch: (id: ModeId) => void;
}

const ModeSwitch = ({ activeMode, onSwitch }: ModeSwitchProps) => {
  return (
    <div className="flex items-center">
      {/* Pill segment container */}
      <div
        className="flex items-center gap-1 rounded-full p-1 border border-pink-200/60"
        style={{ 
          background: "rgba(255,255,255,0.7)", 
          backdropFilter: "blur(12px)" 
        }}
      >
        {MODES.map((mode) => {
          const isActive = activeMode === mode.id;
          return (
            <button
              key={mode.id}
              onClick={() => onSwitch(mode.id)}
              className={[
                "relative flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm whitespace-nowrap cursor-pointer transition-all duration-300 select-none",
                isActive
                  ? `bg-gradient-to-r ${mode.activeGradient} text-white font-medium`
                  : "text-pink-400/70 hover:text-pink-500 hover:bg-pink-50/50",
              ].join(" ")}
              style={
                isActive
                  ? { 
                      boxShadow: "0 2px 10px rgba(244,114,182,0.35)",
                      fontFamily: "'ZCOOL KuaiLe', cursive"
                    }
                  : {}
              }
            >
              <span className="w-4 h-4 flex items-center justify-center text-sm leading-none">
                <i className={mode.icon}></i>
              </span>
              <span>{mode.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default ModeSwitch;