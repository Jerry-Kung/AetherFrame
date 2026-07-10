import { useState, useCallback, useEffect } from "react";
import { getFeedbackTags } from "@/services/creationApi";
import type { FeedbackTagDef, FeedbackSeverity, SelectedFeedbackTag } from "@/services/creationApi";
import type { QuickCreateImage } from "@/types/quickCreate";

interface ImageFeedbackModalProps {
  image: QuickCreateImage;
  promptTitle: string;
  onSave: (feedbackText: string, selectedTags: SelectedFeedbackTag[]) => Promise<void>;
  onClose: () => void;
}

const SEVERITY_ORDER: FeedbackSeverity[] = ["minor", "moderate", "severe"];
const SEVERITY_SHORT: Record<FeedbackSeverity, string> = {
  minor: "轻",
  moderate: "中",
  severe: "重",
};
/** 选中后整个胶囊底色随等级加深 */
const SEVERITY_BG: Record<FeedbackSeverity, string> = {
  minor: "rgba(253,164,175,0.25)",
  moderate: "rgba(244,114,182,0.45)",
  severe: "rgba(225,29,72,0.75)",
};
const OTHER_GROUP = "其他";

/** 负面标签：常显分段式「标签名│轻│中│重」，任意等级一次点选；点标签名按「中等」快捷选中/取消 */
function NegativeTagPill({
  tag,
  severity,
  onPick,
}: {
  tag: FeedbackTagDef;
  severity: FeedbackSeverity | null;
  onPick: (next: FeedbackSeverity | null) => void;
}) {
  const isOn = severity !== null;
  return (
    <div
      className="inline-flex items-center rounded-full text-xs transition-all duration-150"
      style={{
        background: isOn ? SEVERITY_BG[severity] : "rgba(0,0,0,0.04)",
        border: isOn ? "1px solid rgba(225,29,72,0.35)" : "1px solid rgba(0,0,0,0.08)",
      }}
    >
      <button
        type="button"
        onClick={() => onPick(isOn ? null : "moderate")}
        title={isOn ? "取消选中" : "按「中等」选中"}
        className="pl-2.5 pr-1 py-1 cursor-pointer whitespace-nowrap"
        style={{
          color: isOn ? (severity === "severe" ? "white" : "#be123c") : "#9ca3af",
          fontFamily: "'ZCOOL KuaiLe', cursive",
        }}
      >
        {tag.label}
      </button>
      <div className="flex items-center gap-0.5 pr-1.5">
        {SEVERITY_ORDER.map((s) => {
          const active = severity === s;
          return (
            <button
              key={s}
              type="button"
              onClick={() => onPick(active ? null : s)}
              title={active ? "取消选中" : `按「${SEVERITY_SHORT[s]}」选中`}
              className="px-1.5 py-0.5 rounded-full cursor-pointer leading-none transition-all duration-150"
              style={{
                background: active ? "rgba(255,255,255,0.9)" : "transparent",
                color: active
                  ? "#be123c"
                  : isOn
                    ? severity === "severe"
                      ? "rgba(255,255,255,0.7)"
                      : "rgba(190,18,60,0.5)"
                    : "rgba(0,0,0,0.22)",
                fontWeight: active ? 700 : 400,
              }}
            >
              {SEVERITY_SHORT[s]}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** 正面/中立标签：开关式胶囊 */
function SimpleTagPill({
  tag,
  isOn,
  onClick,
}: {
  tag: FeedbackTagDef;
  isOn: boolean;
  onClick: () => void;
}) {
  let bg = "rgba(0,0,0,0.04)";
  let color = "#9ca3af";
  let border = "1px solid rgba(0,0,0,0.08)";
  if (isOn) {
    if (tag.polarity === "positive") {
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
    </button>
  );
}

/** 单张产线出图的人工 feedback 弹窗：分组标签点选（负面等级一次点选）+ 自由文本；bad 由标签推导 */
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
  const severityOf = (key: string): FeedbackSeverity | null => {
    const item = selected.find((s) => s.key === key);
    if (!item) return null;
    return item.severity ?? "moderate";
  };
  const isSelected = (key: string) => selected.some((s) => s.key === key);

  const pickNegative = useCallback((tag: FeedbackTagDef, next: FeedbackSeverity | null) => {
    setSelected((prev) => {
      const idx = prev.findIndex((s) => s.key === tag.key);
      if (next === null) return idx >= 0 ? prev.filter((s) => s.key !== tag.key) : prev;
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { key: tag.key, severity: next };
        return copy;
      }
      return [...prev, { key: tag.key, severity: next }];
    });
  }, []);

  const toggleSimple = useCallback((tag: FeedbackTagDef) => {
    setSelected((prev) =>
      prev.some((s) => s.key === tag.key)
        ? prev.filter((s) => s.key !== tag.key)
        : [...prev, { key: tag.key }]
    );
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(text, selected);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }, [onSave, onClose, text, selected]);

  // 负面标签按 group 分组：组间顺序 = 该组首个标签在配置中的出现顺序；「其他」固定排最后
  const negativeGroups: Array<{ name: string; items: FeedbackTagDef[] }> = [];
  for (const t of tagDefs) {
    if (t.polarity !== "negative") continue;
    const name = t.group ?? OTHER_GROUP;
    const g = negativeGroups.find((x) => x.name === name);
    if (g) g.items.push(t);
    else negativeGroups.push({ name, items: [t] });
  }
  const otherIdx = negativeGroups.findIndex((g) => g.name === OTHER_GROUP);
  if (otherIdx >= 0) negativeGroups.push(...negativeGroups.splice(otherIdx, 1));
  const positives = tagDefs.filter((t) => t.polarity === "positive");
  const neutrals = tagDefs.filter((t) => t.polarity === "neutral");

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(6px)" }}
        onClick={saving ? undefined : onClose}
      />
      <div
        className="relative w-[52rem] max-w-[calc(100vw-2rem)] max-h-[calc(100vh-4rem)] overflow-y-auto rounded-3xl mx-4"
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
            <div className="mb-3 space-y-2.5">
              <p className="text-xs text-rose-400/70">
                问题标签（点「轻/中/重」一次选中；点标签名按「中等」快捷选中/取消）
              </p>
              {negativeGroups.map((g) => (
                <div key={g.name} className="flex items-start gap-2">
                  <span
                    className="shrink-0 w-20 pt-1.5 text-right text-xs text-rose-300/80"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    {g.name}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {g.items.map((t) => (
                      <NegativeTagPill
                        key={t.key}
                        tag={t}
                        severity={severityOf(t.key)}
                        onPick={(next) => pickNegative(t, next)}
                      />
                    ))}
                  </div>
                </div>
              ))}
              {(positives.length > 0 || neutrals.length > 0) && (
                <div className="flex items-start gap-2 pt-2 border-t border-rose-100/60">
                  <span
                    className="shrink-0 w-20 pt-1.5 text-right text-xs text-rose-300/80"
                    style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
                  >
                    亮点/中立
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {[...positives, ...neutrals].map((t) => (
                      <SimpleTagPill
                        key={t.key}
                        tag={t}
                        isOn={isSelected(t.key)}
                        onClick={() => toggleSimple(t)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {derivedBad && (
            <p
              className="mb-2 text-xs text-rose-500/90"
              style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
            >
              已判定：腿脚崩坏（由标签自动推导，计入 Case 的 bad 计数）
            </p>
          )}

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={2}
            placeholder="标签覆盖不了的新问题写这里…"
            className="w-full rounded-xl p-3 text-sm text-rose-700/80 resize-none focus:outline-none"
            style={{ background: "rgba(253,164,175,0.06)", border: "1px solid rgba(253,164,175,0.25)" }}
          />

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
