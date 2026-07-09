import { useState, useCallback, useEffect } from "react";
import { getFeedbackTags } from "@/services/creationApi";
import type { FeedbackTagDef, FeedbackSeverity, SelectedFeedbackTag } from "@/services/creationApi";
import type { QuickCreateImage } from "@/types/quickCreate";

interface ImageFeedbackModalProps {
  image: QuickCreateImage;
  promptTitle: string;
  onSave: (
    feedbackText: string,
    legFootBad: boolean,
    selectedTags: SelectedFeedbackTag[]
  ) => Promise<void>;
  onClose: () => void;
}

/** 负面标签点击循环：未选 → 轻微 → 中等 → 严重 → 取消 */
const SEVERITY_CYCLE: (FeedbackSeverity | null)[] = ["minor", "moderate", "severe", null];
const SEVERITY_SHORT: Record<FeedbackSeverity, string> = {
  minor: "轻",
  moderate: "中",
  severe: "重",
};
/** 负面胶囊底色随等级加深 */
const SEVERITY_BG: Record<FeedbackSeverity, string> = {
  minor: "rgba(253,164,175,0.25)",
  moderate: "rgba(244,114,182,0.45)",
  severe: "rgba(225,29,72,0.75)",
};

function TagPill({
  tag,
  selected,
  onClick,
}: {
  tag: FeedbackTagDef;
  selected: SelectedFeedbackTag | undefined;
  onClick: () => void;
}) {
  const isOn = selected !== undefined;
  let bg = "rgba(0,0,0,0.04)";
  let color = "#9ca3af";
  let border = "1px solid rgba(0,0,0,0.08)";
  let suffix = "";
  if (isOn) {
    if (tag.polarity === "negative" && selected?.severity) {
      bg = SEVERITY_BG[selected.severity];
      color = selected.severity === "severe" ? "white" : "#be123c";
      border = "1px solid rgba(225,29,72,0.35)";
      suffix = `·${SEVERITY_SHORT[selected.severity]}`;
    } else if (tag.polarity === "positive") {
      bg = "rgba(74,222,128,0.35)";
      color = "#15803d";
      border = "1px solid rgba(34,197,94,0.4)";
    } else {
      bg = "rgba(148,163,184,0.35)";
      color = "#475569";
      border = "1px solid rgba(100,116,139,0.4)";
    }
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-2.5 py-1 rounded-full text-xs cursor-pointer transition-all duration-150 whitespace-nowrap"
      style={{ background: bg, color, border, fontFamily: "'ZCOOL KuaiLe', cursive" }}
    >
      {tag.label}
      {suffix}
    </button>
  );
}

/** 单张产线出图的人工 feedback 弹窗：标签点选（负面带等级）+ 自由文本 + 兜底勾选 */
export default function ImageFeedbackModal({
  image,
  promptTitle,
  onSave,
  onClose,
}: ImageFeedbackModalProps) {
  const [tagDefs, setTagDefs] = useState<FeedbackTagDef[]>([]);
  const [selected, setSelected] = useState<SelectedFeedbackTag[]>(
    image.userFeedback?.selectedTags ?? []
  );
  const [text, setText] = useState(image.userFeedback?.feedbackText ?? "");
  const [manualBad, setManualBad] = useState(image.userFeedback?.legFootBad ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void getFeedbackTags().then((cfg) => {
      if (alive) setTagDefs(cfg.tags);
    });
    return () => {
      alive = false;
    };
  }, []);

  const defByKey = new Map(tagDefs.map((t) => [t.key, t] as const));
  const derivedBad = selected.some((s) => defByKey.get(s.key)?.leg_foot_bad);
  const effectiveBad = derivedBad || manualBad;

  const toggleTag = useCallback((tag: FeedbackTagDef) => {
    setSelected((prev) => {
      const idx = prev.findIndex((s) => s.key === tag.key);
      if (tag.polarity !== "negative") {
        return idx >= 0
          ? prev.filter((s) => s.key !== tag.key)
          : [...prev, { key: tag.key }];
      }
      const cur = idx >= 0 ? (prev[idx].severity ?? "moderate") : null;
      const next = SEVERITY_CYCLE[(SEVERITY_CYCLE.indexOf(cur) + 1) % SEVERITY_CYCLE.length];
      if (next === null) return prev.filter((s) => s.key !== tag.key);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { key: tag.key, severity: next };
        return copy;
      }
      return [...prev, { key: tag.key, severity: next }];
    });
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(text, manualBad, selected);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }, [onSave, onClose, text, manualBad, selected]);

  const negatives = tagDefs.filter((t) => t.polarity === "negative");
  const positives = tagDefs.filter((t) => t.polarity === "positive");
  const neutrals = tagDefs.filter((t) => t.polarity === "neutral");
  const groups: Array<{ title: string; items: FeedbackTagDef[] }> = [
    { title: "问题标签（点击切换 轻/中/重）", items: negatives },
    { title: "亮点标签", items: positives },
    { title: "中立", items: neutrals },
  ];

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
        onClick={saving ? undefined : onClose}
      />
      <div
        className="relative w-[30rem] max-w-[calc(100vw-2rem)] max-h-[calc(100vh-4rem)] overflow-y-auto rounded-3xl mx-4"
        style={{ background: "rgba(255,255,255,0.97)", border: "1px solid rgba(253,164,175,0.3)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pt-6 pb-4 px-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-14 h-14 rounded-xl overflow-hidden shrink-0 border border-rose-100">
              <img src={image.url} alt="" className="w-full h-full object-cover object-top" />
            </div>
            <div className="min-w-0">
              <h3
                className="text-base font-bold text-rose-600"
                style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
              >
                填写人工 Feedback
              </h3>
              <p className="text-xs text-rose-400/60 truncate">{promptTitle}</p>
            </div>
          </div>

          {tagDefs.length > 0 && (
            <div className="mb-3 space-y-2">
              {groups.map(
                (g) =>
                  g.items.length > 0 && (
                    <div key={g.title}>
                      <p className="text-xs text-rose-400/70 mb-1">{g.title}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {g.items.map((t) => (
                          <TagPill
                            key={t.key}
                            tag={t}
                            selected={selected.find((s) => s.key === t.key)}
                            onClick={() => toggleTag(t)}
                          />
                        ))}
                      </div>
                    </div>
                  )
              )}
            </div>
          )}

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={2}
            placeholder="标签覆盖不了的新问题写这里…"
            className="w-full rounded-xl p-3 text-sm text-rose-700/80 resize-none focus:outline-none"
            style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.25)" }}
          />

          <label
            className="flex items-center gap-2 mt-3 select-none"
            style={{ cursor: derivedBad ? "not-allowed" : "pointer" }}
          >
            <input
              type="checkbox"
              checked={effectiveBad}
              disabled={derivedBad}
              onChange={(e) => setManualBad(e.target.checked)}
              className="w-4 h-4 accent-rose-400"
            />
            <span
              className="text-sm font-medium text-rose-600"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              腿脚崩坏
            </span>
            <span className="text-xs text-rose-300/60">
              {derivedBad ? "（已由标签推导）" : "（计入 Case 的 bad 计数）"}
            </span>
          </label>

          {error && (
            <p className="mt-2 text-xs text-rose-600" role="alert">
              {error}
            </p>
          )}
        </div>

        <div className="h-px mx-5" style={{ background: "rgba(253,164,175,0.2)" }} />
        <div className="flex gap-3 p-4">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="flex-1 py-2.5 rounded-xl text-sm cursor-pointer transition-all duration-200 whitespace-nowrap"
            style={{
              background: "rgba(253,164,175,0.08)",
              color: "#f472b6",
              border: "1px solid rgba(244,114,182,0.2)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              opacity: saving ? 0.5 : 1,
            }}
          >
            取消
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 whitespace-nowrap text-white"
            style={{
              background: "linear-gradient(135deg, #fda4af 0%, #f472b6 100%)",
              fontFamily: "'ZCOOL KuaiLe', cursive",
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
