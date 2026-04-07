/** 角色加工流程四态 */
export type CharaStatus = "idle" | "draft" | "processing" | "done";

export const STATUS_LABEL: Record<CharaStatus, string> = {
  idle: "还没开始",
  draft: "资料待补充",
  processing: "加工进行中",
  done: "已整理完成",
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
  tags: string[];
}

export interface CharaBio {
  displayName: string;
  age: string;
  height: string;
  personality: string;
  ability: string;
  appearance: string;
}

export interface CharaProfile {
  id: string;
  name: string;
  avatarUrl: string;
  status: CharaStatus;
  updatedAt: string;
  settingText: string;
  rawImages: CharaRawImage[];
  officialPhotos: [string | null, string | null, string | null];
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
  };
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
  raw_images: { id: string; url: string; tags: string[] }[];
  official_photos: (string | null)[];
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
  };

  const photos = d.official_photos || [];
  const officialPhotos: [string | null, string | null, string | null] = [
    (photos[0] as string | null | undefined) ?? null,
    (photos[1] as string | null | undefined) ?? null,
    (photos[2] as string | null | undefined) ?? null,
  ];

  const avatarUrl =
    d.avatar_url && d.avatar_url.length > 0 ? d.avatar_url : DEFAULT_CHARA_AVATAR_PLACEHOLDER;

  return {
    id: d.id,
    name: d.name,
    avatarUrl,
    status: asCharaStatus(d.status),
    updatedAt: d.updated_at,
    settingText: d.setting_text ?? "",
    rawImages: (d.raw_images || []).map((r) => ({
      id: r.id,
      url: r.url,
      tags: Array.isArray(r.tags) ? r.tags : [],
    })),
    officialPhotos,
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
    rawImages: [],
    officialPhotos: [null, null, null],
    bio: emptyBio(s.display_name),
  };
}
