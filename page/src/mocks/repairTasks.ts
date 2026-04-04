/**
 * 修补模块 Mock / 展示辅助：内置模板说明文案、自定义模板描述本地缓存。
 * 内置模板 id 与后端 app/scripts/init_db.py 中 BUILTIN_TEMPLATES 保持一致。
 */

import type { PromptTemplate as ApiPromptTemplate } from "@/types/repair";

const CUSTOM_DESC_STORAGE_KEY = "aetherframe_repair_tpl_desc_v1";

/** 与 API 一致；enrich 会为缺省 description 补内置映射或历史 localStorage */
export interface PromptTemplate extends ApiPromptTemplate {
  description: string;
}

/** 内置模板 id → 简短说明（用于列表展示；与数据库内置模板一一对应） */
export const BUILTIN_TEMPLATE_DESCRIPTIONS: Record<string, string> = {
  tpl_skin_repair: "适用于修复人物皮肤痘印、划痕等瑕疵，保持动漫风格与肤色自然。",
  tpl_watermark_remove: "去除水印、文字标记及 logo，并对背景做自然填补。",
  tpl_background_fix: "弱化背景噪点、模糊与色差，使背景更干净并与前景融合。",
  tpl_outline_complete: "补全残缺或被遮挡的角色轮廓，线条与风格与原图一致。",
  tpl_clothing_detail: "修复衣物皱褶、配饰破损等细节，保持整体造型统一。",
  tpl_eye_highlight: "为眼部补充或修正高光，增强神采并符合二次元绘制习惯。",
};

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

/** 将接口返回的模板转为带 description 的展示结构（优先使用接口字段，再回退内置表 / localStorage） */
export function enrichPromptTemplate(t: ApiPromptTemplate): PromptTemplate {
  let description = (t.description ?? "").trim();
  if (!description && t.is_builtin) {
    description = BUILTIN_TEMPLATE_DESCRIPTIONS[t.id] ?? "";
  }
  if (!description && !t.is_builtin) {
    description = getCustomTemplateDescription(t.id);
  }
  return { ...t, description };
}

export function enrichPromptTemplates(list: ApiPromptTemplate[]): PromptTemplate[] {
  return list.map(enrichPromptTemplate);
}
