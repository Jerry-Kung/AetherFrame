/** 新正式种子条目 id（合入 bio 时使用） */
export function newSeedId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `seed-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
