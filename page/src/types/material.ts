/** 角色加工流程四态 */
export type CharaStatus = "idle" | "draft" | "processing" | "done";

export const STATUS_LABEL: Record<CharaStatus, string> = {
  idle: "还没开始",
  draft: "资料待补充",
  processing: "加工进行中",
  done: "资料已完善",
};

export const STATUS_STYLE: Record<
  CharaStatus,
  { dot: string; text: string; badgeBg: string; badgeText: string }
> = {
  idle: {
    dot: "bg-slate-300",
    text: "text-slate-400",
    badgeBg: "bg-slate-100/90",
    badgeText: "text-slate-500",
  },
  draft: {
    dot: "bg-amber-400",
    text: "text-amber-600",
    badgeBg: "bg-amber-50",
    badgeText: "text-amber-700",
  },
  processing: {
    dot: "bg-pink-400 animate-pulse",
    text: "text-pink-600",
    badgeBg: "bg-pink-50",
    badgeText: "text-pink-700",
  },
  done: {
    dot: "bg-emerald-400",
    text: "text-emerald-600",
    badgeBg: "bg-emerald-50",
    badgeText: "text-emerald-700",
  },
};

export interface CharaRawImage {
  id: string;
  url: string;
  type: RawImageType;
  tags: string[];
}

export type RawImageType = "official" | "fanart";

export type StandardPhotoType = "full_front" | "full_side" | "half_front" | "half_side" | "face_close";

export const STANDARD_PHOTO_LABELS: Record<StandardPhotoType, string> = {
  full_front: "全身正面",
  full_side: "全身侧面",
  half_front: "半身正面",
  half_side: "半身侧面",
  face_close: "脸部特写",
};

export const ALL_STANDARD_PHOTO_TYPES: StandardPhotoType[] = [
  "full_front",
  "full_side",
  "half_front",
  "half_side",
  "face_close",
];

/** 正式种子提示词单条（与 bio_json.official_seed_prompts 对应） */
export interface SeedPrompt {
  id: string;
  text: string;
  used: boolean;
}

export interface OfficialSeedPrompts {
  characterSpecific: SeedPrompt[];
  general: SeedPrompt[];
}

export interface CharaBio {
  displayName: string;
  age: string;
  height: string;
  personality: string;
  ability: string;
  appearance: string;
  charaProfile?: string;
  creativeAdvice?: string;
  /** 已保存至正式内容的种子提示词；未保存过为 null */
  officialSeedPrompts?: OfficialSeedPrompts | null;
}

export interface CharaStandardPhoto {
  id: string;
  type: StandardPhotoType;
  url: string;
  createdAt: string;
}

export interface CharaProfile {
  id: string;
  name: string;
  avatarUrl: string;
  status: CharaStatus;
  updatedAt: string;
  settingText: string;
  /** 最近一次通过 .txt/.md 导入的源文件名；仅前端会话内展示，后端未持久化时可丢失 */
  settingFileName: string;
  rawImages: CharaRawImage[];
  officialPhotos: [string | null, string | null, string | null, string | null, string | null];
  standardPhotos: CharaStandardPhoto[];
  bio: CharaBio;
}

export const RAW_IMAGE_TAG_PRESETS = ["立绘", "三视图", "表情", "服装", "场景", "其他"] as const;
export type RawImageTagPreset = (typeof RAW_IMAGE_TAG_PRESETS)[number];

/** 新建弹窗用：无头像时的占位图（SVG data URL） */
export const DEFAULT_CHARA_AVATAR_PLACEHOLDER =
  "data:image/svg+xml," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
      <defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style="stop-color:#fce7f3"/><stop offset="100%" style="stop-color:#fbcfe8"/>
      </linearGradient></defs>
      <rect fill="url(#g)" width="200" height="200" rx="24"/>
      <text x="100" y="108" text-anchor="middle" fill="#f472b6" font-size="48" font-family="system-ui">?</text>
    </svg>`
  );

function asCharaStatus(s: string): CharaStatus {
  if (s === "idle" || s === "draft" || s === "processing" || s === "done") return s;
  return "idle";
}

function emptyBio(displayName: string): CharaBio {
  return {
    displayName,
    age: "—",
    height: "—",
    personality: "待补充",
    ability: "待补充",
    appearance: "待补充",
    officialSeedPrompts: null,
  };
}

function parseSeedPromptItem(x: unknown, index: number): SeedPrompt | null {
  if (!x || typeof x !== "object") return null;
  const o = x as Record<string, unknown>;
  const id = typeof o.id === "string" && o.id.length > 0 ? o.id : `seed-${index}`;
  const text = typeof o.text === "string" ? o.text : "";
  const used = o.used === true;
  return { id, text, used };
}

function parseSeedPromptArray(raw: unknown): SeedPrompt[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(parseSeedPromptItem).filter((x): x is SeedPrompt => x !== null);
}

/** 从 API bio 字典解析 official_seed_prompts */
export function parseOfficialSeedPromptsFromBio(bio: Record<string, unknown>): OfficialSeedPrompts | null {
  const raw =
    bio.official_seed_prompts ??
    (bio as { officialSeedPrompts?: unknown }).officialSeedPrompts;
  if (raw === null || raw === undefined) return null;
  if (typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const characterSpecific = parseSeedPromptArray(
    o.character_specific ?? o.characterSpecific
  );
  const general = parseSeedPromptArray(o.general);
  if (characterSpecific.length === 0 && general.length === 0) return null;
  return { characterSpecific, general };
}

/** 写入 PATCH 请求体用的 snake_case 结构 */
export function officialSeedPromptsToApiPayload(p: OfficialSeedPrompts): Record<string, unknown> {
  const row = (s: SeedPrompt) => ({ id: s.id, text: s.text, used: s.used });
  return {
    character_specific: p.characterSpecific.map(row),
    general: p.general.map(row),
  };
}

export function emptyOfficialSeedPrompts(): OfficialSeedPrompts {
  return { characterSpecific: [], general: [] };
}

export function cloneOfficialSeedPrompts(p: OfficialSeedPrompts): OfficialSeedPrompts {
  return {
    characterSpecific: p.characterSpecific.map((s) => ({ ...s })),
    general: p.general.map((s) => ({ ...s })),
  };
}

/**
 * 角色小档案正文：仅取自 bio_json 中加工任务写入的 `chara_profile`（及兼容 camelCase）。
 * 不使用年龄/性格等占位字段冒充小档案正文。
 */
export function extractCharaProfileMarkdown(bio: Record<string, unknown>): string {
  const raw = bio.chara_profile ?? bio.charaProfile;
  if (typeof raw !== "string") return "";
  return raw;
}

/**
 * 后端角色详情只保证 `official_photos` 五槽位（顺序与 ALL_STANDARD_PHOTO_TYPES 一致），
 * 不一定返回 `standard_photos`。从小档案解锁等逻辑需要按「类型」识别已完成槽位，故从槽位 URL 推导。
 */
export function standardPhotosFromOfficialSlots(
  officialPhotos: [string | null, string | null, string | null, string | null, string | null]
): CharaStandardPhoto[] {
  const result: CharaStandardPhoto[] = [];
  for (let i = 0; i < ALL_STANDARD_PHOTO_TYPES.length; i++) {
    const url = officialPhotos[i];
    const type = ALL_STANDARD_PHOTO_TYPES[i];
    if (typeof url === "string" && url.trim().length > 0) {
      result.push({
        id: `official-slot-${i}-${type}`,
        type,
        url,
        createdAt: "",
      });
    }
  }
  return result;
}

/** 后端角色详情（snake_case JSON） */
export interface ApiCharacterDetail {
  id: string;
  name: string;
  display_name: string;
  avatar_url: string;
  status: string;
  updated_at: string;
  setting_text: string;
  /** 后端持久化的设定文件来源名（.txt/.md 上传）；缺省或空表示无 */
  setting_source_filename?: string;
  raw_images: { id: string; url: string; type: RawImageType; tags: string[] }[];
  official_photos: (string | null)[];
  standard_photos?: { id: string; type: StandardPhotoType; url: string; created_at: string }[];
  bio: Record<string, unknown>;
}

export interface ApiCharacterSummary {
  id: string;
  name: string;
  display_name: string;
  status: string;
  updated_at: string;
  raw_image_count: number;
  setting_preview: string;
  avatar_url: string;
}

export function toCharaProfile(d: ApiCharacterDetail): CharaProfile {
  const b = d.bio || {};
  const str = (v: unknown, fallback: string) =>
    typeof v === "string" && v.length > 0 ? v : fallback;

  const bioRecord: Record<string, unknown> =
    b && typeof b === "object" && !Array.isArray(b) ? (b as Record<string, unknown>) : {};
  const seeds = parseOfficialSeedPromptsFromBio(bioRecord);

  const bio: CharaBio = {
    displayName: str(
      b.display_name ?? (b as { displayName?: unknown }).displayName,
      d.display_name
    ),
    age: str(b.age, "—"),
    height: str(b.height, "—"),
    personality: str(b.personality, "待补充"),
    ability: str(b.ability, "待补充"),
    appearance: str(b.appearance, "待补充"),
    charaProfile: extractCharaProfileMarkdown(bioRecord),
    creativeAdvice: str(b.creativeAdvice ?? (b as { creative_advice?: unknown }).creative_advice, ""),
    officialSeedPrompts: seeds,
  };

  const photos = d.official_photos || [];
  const officialPhotos: [string | null, string | null, string | null, string | null, string | null] = [
    (photos[0] as string | null | undefined) ?? null,
    (photos[1] as string | null | undefined) ?? null,
    (photos[2] as string | null | undefined) ?? null,
    (photos[3] as string | null | undefined) ?? null,
    (photos[4] as string | null | undefined) ?? null,
  ];

  const fromApiStandard = (d.standard_photos || []).map((sp) => ({
    id: sp.id,
    type: sp.type,
    url: sp.url,
    createdAt: sp.created_at,
  }));
  const fromSlots = standardPhotosFromOfficialSlots(officialPhotos);
  const byType = new Map<StandardPhotoType, CharaStandardPhoto>();
  for (const p of fromSlots) {
    byType.set(p.type, p);
  }
  for (const p of fromApiStandard) {
    byType.set(p.type, p);
  }
  const standardPhotos: CharaStandardPhoto[] = ALL_STANDARD_PHOTO_TYPES.map((t) => byType.get(t)).filter(
    (x): x is CharaStandardPhoto => x != null
  );

  const avatarUrl =
    d.avatar_url && d.avatar_url.length > 0 ? d.avatar_url : DEFAULT_CHARA_AVATAR_PLACEHOLDER;

  return {
    id: d.id,
    name: d.name,
    avatarUrl,
    status: asCharaStatus(d.status),
    updatedAt: d.updated_at,
    settingText: d.setting_text ?? "",
    settingFileName:
      typeof d.setting_source_filename === "string" && d.setting_source_filename.length > 0
        ? d.setting_source_filename
        : "",
    rawImages: (d.raw_images || []).map((r) => ({
      id: r.id,
      url: r.url,
      type: r.type,
      tags: Array.isArray(r.tags) ? r.tags : [],
    })),
    officialPhotos,
    standardPhotos,
    bio,
  };
}

/** 列表摘要 → 可渲染的轻量档案（选中后需再拉详情） */
export function summaryToListProfile(s: ApiCharacterSummary): CharaProfile {
  const avatarUrl =
    s.avatar_url && s.avatar_url.length > 0 ? s.avatar_url : DEFAULT_CHARA_AVATAR_PLACEHOLDER;
  return {
    id: s.id,
    name: s.name,
    avatarUrl,
    status: asCharaStatus(s.status),
    updatedAt:
      typeof s.updated_at === "string" ? s.updated_at : new Date(s.updated_at).toISOString(),
    settingText: "",
    settingFileName: "",
    rawImages: [],
    officialPhotos: [null, null, null, null, null],
    standardPhotos: [],
    bio: emptyBio(s.display_name),
  };
}
