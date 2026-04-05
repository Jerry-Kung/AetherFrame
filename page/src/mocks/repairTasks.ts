/**
 * 修补模块：模板列表 enrich（description / tags 兜底）与历史 localStorage 读写。
 */

import type { PromptTemplate as ApiPromptTemplate } from "@/types/repair";

const CUSTOM_DESC_STORAGE_KEY = "aetherframe_repair_tpl_desc_v1";
const TPL_TAGS_STORAGE_KEY = "aetherframe_repair_tpl_tags_v1";
const EXTRA_TAGS_STORAGE_KEY = "aetherframe_repair_extra_tags_v1";
const DELETED_CATALOG_TAGS_KEY = "aetherframe_repair_deleted_tags_v1";

/** 预置 10 个标签（展示顺序） */
export const DEFAULT_TAGS = [
  "脸部",
  "眼睛",
  "皮肤",
  "服装",
  "背景",
  "水印",
  "轮廓",
  "配饰",
  "头发",
  "光影",
] as const;

/**
 * 内置模板标题 → 预置标签（与数据库/种子中的 `label` 精确匹配时生效）。
 * 若环境无内置行，此表不影响自定义模板。
 */
export const BUILTIN_TAGS_BY_LABEL: Record<string, string[]> = {
  脸部轮廓优化: ["脸部", "轮廓"],
  眼部精修: ["眼睛"],
  皮肤质感修补: ["皮肤"],
  服装与配饰: ["服装", "配饰"],
  背景与水印处理: ["背景", "水印"],
  头发光影调整: ["头发", "光影"],
};

export interface PromptTemplate extends ApiPromptTemplate {
  description: string;
  tags: string[];
}

function normalizeTagList(tags: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of tags) {
    const t = raw.trim();
    if (!t || seen.has(t)) continue;
    seen.add(t);
    out.push(t);
  }
  return out;
}

function readCustomDescriptionMap(): Record<string, string> {
  try {
    const raw = localStorage.getItem(CUSTOM_DESC_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as Record<string, string>;
  } catch {
    return {};
  }
}

function writeCustomDescriptionMap(map: Record<string, string>) {
  try {
    localStorage.setItem(CUSTOM_DESC_STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

function readTagsMap(): Record<string, string[]> {
  try {
    const raw = localStorage.getItem(TPL_TAGS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    const out: Record<string, string[]> = {};
    for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
      if (Array.isArray(v)) {
        out[k] = normalizeTagList(v.map(String));
      }
    }
    return out;
  } catch {
    return {};
  }
}

function writeTagsMap(map: Record<string, string[]>) {
  try {
    localStorage.setItem(TPL_TAGS_STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

/** 无本地记录时返回 undefined；若键存在（含空数组）表示用户曾显式保存过标签 */
export function getStoredTemplateTags(id: string): string[] | undefined {
  const v = readTagsMap()[id];
  return v !== undefined ? normalizeTagList(v) : undefined;
}

export function setTemplateTags(id: string, tags: string[]) {
  const map = readTagsMap();
  map[id] = normalizeTagList(tags);
  writeTagsMap(map);
}

export function removeTemplateTags(id: string) {
  const map = readTagsMap();
  delete map[id];
  writeTagsMap(map);
}

/** 从所有已存储的模板标签中移除指定标签名（保留空数组以覆盖内置默认） */
export function stripTagFromAllStoredTemplates(tagName: string) {
  const t = tagName.trim();
  if (!t) return;
  const map = readTagsMap();
  let changed = false;
  for (const id of Object.keys(map)) {
    const next = map[id].filter((x) => x !== t);
    if (next.length !== map[id].length) {
      changed = true;
      map[id] = next;
    }
  }
  if (changed) writeTagsMap(map);
}

export function readExtraTags(): string[] {
  try {
    const raw = localStorage.getItem(EXTRA_TAGS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return normalizeTagList(parsed.map(String));
  } catch {
    return [];
  }
}

export function writeExtraTags(tags: string[]) {
  try {
    localStorage.setItem(EXTRA_TAGS_STORAGE_KEY, JSON.stringify(normalizeTagList(tags)));
  } catch {
    /* ignore */
  }
}

export function appendExtraTag(name: string) {
  const t = name.trim();
  if (!t) return;
  const cur = readExtraTags();
  if (cur.includes(t)) return;
  writeExtraTags([...cur, t]);
}

export function removeExtraTag(name: string) {
  const t = name.trim();
  if (!t) return;
  writeExtraTags(readExtraTags().filter((x) => x !== t));
}

export function readDeletedCatalogTags(): string[] {
  try {
    const raw = localStorage.getItem(DELETED_CATALOG_TAGS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return normalizeTagList(parsed.map(String));
  } catch {
    return [];
  }
}

export function writeDeletedCatalogTags(tags: string[]) {
  try {
    localStorage.setItem(DELETED_CATALOG_TAGS_KEY, JSON.stringify(normalizeTagList(tags)));
  } catch {
    /* ignore */
  }
}

export function addDeletedCatalogTag(name: string) {
  const t = name.trim();
  if (!t) return;
  const cur = readDeletedCatalogTags();
  if (cur.includes(t)) return;
  writeDeletedCatalogTags([...cur, t]);
}

export function removeDeletedCatalogTag(name: string) {
  const t = name.trim();
  if (!t) return;
  writeDeletedCatalogTags(readDeletedCatalogTags().filter((x) => x !== t));
}

export function getCustomTemplateDescription(id: string): string {
  return readCustomDescriptionMap()[id] ?? "";
}

export function setCustomTemplateDescription(id: string, description: string) {
  const map = readCustomDescriptionMap();
  if (!description.trim()) {
    delete map[id];
  } else {
    map[id] = description.trim();
  }
  writeCustomDescriptionMap(map);
}

export function removeCustomTemplateDescription(id: string) {
  const map = readCustomDescriptionMap();
  delete map[id];
  writeCustomDescriptionMap(map);
}

function resolveTags(t: ApiPromptTemplate): string[] {
  const apiTags = t.tags;
  if (Array.isArray(apiTags) && apiTags.length > 0) {
    return normalizeTagList(apiTags.map(String));
  }
  const local = getStoredTemplateTags(t.id);
  if (local !== undefined) {
    return local;
  }
  if (t.is_builtin) {
    const preset = BUILTIN_TAGS_BY_LABEL[t.label.trim()];
    if (preset?.length) {
      return [...preset];
    }
  }
  return [];
}

/** 将接口返回的模板转为带 description、tags 的展示结构 */
export function enrichPromptTemplate(t: ApiPromptTemplate): PromptTemplate {
  let description = (t.description ?? "").trim();
  if (!description) {
    description = getCustomTemplateDescription(t.id);
  }
  const tags = resolveTags(t);
  return { ...t, description, tags };
}

export function enrichPromptTemplates(list: ApiPromptTemplate[]): PromptTemplate[] {
  return list.map(enrichPromptTemplate);
}

/**
 * 计算当前应在筛选栏 / 标签管理中展示的标签目录（去重、排序）。
 */
export function computeAllTags(
  templates: Pick<PromptTemplate, "tags">[],
  extraTags: string[],
  deletedCatalog: string[]
): string[] {
  const deleted = new Set(deletedCatalog);
  const set = new Set<string>();
  for (const name of DEFAULT_TAGS) {
    if (!deleted.has(name)) set.add(name);
  }
  for (const x of extraTags) {
    if (!deleted.has(x)) set.add(x);
  }
  for (const tpl of templates) {
    for (const x of tpl.tags) {
      if (!deleted.has(x)) set.add(x);
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));
}
