/**
 * 修补模块：模板列表 enrich（description 兜底）与历史 localStorage 描述读写。
 */

import type { PromptTemplate as ApiPromptTemplate } from "@/types/repair";

const CUSTOM_DESC_STORAGE_KEY = "aetherframe_repair_tpl_desc_v1";

/** 与 API 一致；enrich 在 description 为空时用 localStorage 兜底（兼容旧数据） */
export interface PromptTemplate extends ApiPromptTemplate {
  description: string;
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
    /* ignore quota / private mode */
  }
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

/** 将接口返回的模板转为带 description 的展示结构（优先 API，再 localStorage） */
export function enrichPromptTemplate(t: ApiPromptTemplate): PromptTemplate {
  let description = (t.description ?? "").trim();
  if (!description) {
    description = getCustomTemplateDescription(t.id);
  }
  return { ...t, description };
}

export function enrichPromptTemplates(list: ApiPromptTemplate[]): PromptTemplate[] {
  return list.map(enrichPromptTemplate);
}
