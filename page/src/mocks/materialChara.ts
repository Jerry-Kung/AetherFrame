/** 角色加工流程四态（内部枚举） */
export type CharaStatus = "idle" | "draft" | "processing" | "done";

export const STATUS_LABEL: Record<CharaStatus, string> = {
  idle: "还没开始",
  draft: "资料待补充",
  processing: "加工进行中",
  done: "已整理完成",
};

/** 列表/标签用：底色、文字色、小圆点 */
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

/** 结构化小档案（正式内容区展示） */
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
  /** ISO 时间字符串 */
  updatedAt: string;
  /** 角色设定说明（原始资料） */
  settingText: string;
  rawImages: CharaRawImage[];
  /** 标准参考照，固定三槽 */
  officialPhotos: [string | null, string | null, string | null];
  bio: CharaBio;
}

/** 上传参考图时可选的标签（过滤 chips 用） */
export const RAW_IMAGE_TAG_PRESETS = ["立绘", "三视图", "表情", "服装", "场景", "其他"] as const;

export type RawImageTagPreset = (typeof RAW_IMAGE_TAG_PRESETS)[number];

function iso(d: Date): string {
  return d.toISOString();
}

const placeholder = (seed: number, w = 200, h = 200) =>
  `https://picsum.photos/seed/aether-${seed}/${w}/${h}`;

export const MOCK_CHARAS: CharaProfile[] = [
  {
    id: "c1",
    name: "星野小眠",
    avatarUrl: placeholder(101),
    status: "idle",
    updatedAt: iso(new Date(Date.now() - 86400000 * 2)),
    settingText: "",
    rawImages: [],
    officialPhotos: [null, null, null],
    bio: {
      displayName: "星野小眠",
      age: "—",
      height: "—",
      personality: "待补充",
      ability: "待补充",
      appearance: "待补充",
    },
  },
  {
    id: "c2",
    name: "月岛芽衣",
    avatarUrl: placeholder(102),
    status: "draft",
    updatedAt: iso(new Date(Date.now() - 3600000 * 5)),
    settingText: "浅粉双马尾、喜欢草莓牛奶、说话带「呢」尾音。",
    rawImages: [
      { id: "r1", url: placeholder(201, 320, 400), tags: ["立绘"] },
      { id: "r2", url: placeholder(202, 320, 400), tags: ["表情", "其他"] },
    ],
    officialPhotos: [null, null, null],
    bio: {
      displayName: "月岛芽衣",
      age: "16",
      height: "158cm",
      personality: "开朗、略傲娇",
      ability: "（待加工生成）",
      appearance: "浅粉双马尾、琥珀色眼睛",
    },
  },
  {
    id: "c3",
    name: "雾雨凛",
    avatarUrl: placeholder(103),
    status: "processing",
    updatedAt: iso(new Date(Date.now() - 600000)),
    settingText:
      "## 设定\n银灰短发、异色瞳。表面冷淡，对熟悉的人会露出笨拙的温柔。\n\n## 禁忌\n不要画成幼态比例。",
    rawImages: [
      { id: "r3", url: placeholder(301, 400, 400), tags: ["立绘", "三视图"] },
      { id: "r4", url: placeholder(302, 400, 400), tags: ["服装"] },
      { id: "r5", url: placeholder(303, 400, 400), tags: ["场景"] },
    ],
    officialPhotos: [placeholder(401), placeholder(402), null],
    bio: {
      displayName: "雾雨凛",
      age: "19",
      height: "172cm",
      personality: "冷静、寡言、内心细腻",
      ability: "摄影与暗房冲洗",
      appearance: "银灰短发、左蓝右金异色瞳",
    },
  },
  {
    id: "c4",
    name: "夏川柚",
    avatarUrl: placeholder(104),
    status: "done",
    updatedAt: iso(new Date(Date.now() - 120000)),
    settingText: "柑橘系元气少女，短发、雀斑、总背着画板。代表色橙黄。",
    rawImages: [
      { id: "r6", url: placeholder(501, 360, 360), tags: ["立绘"] },
      { id: "r7", url: placeholder(502, 360, 360), tags: ["表情"] },
      { id: "r8", url: placeholder(503, 360, 360), tags: ["服装"] },
    ],
    officialPhotos: [placeholder(601, 480, 640), placeholder(602, 480, 640), placeholder(603, 480, 640)],
    bio: {
      displayName: "夏川柚",
      age: "17",
      height: "162cm",
      personality: "阳光、直率、有点小冒失",
      ability: "水彩插画、街头速写",
      appearance: "浅棕短发、小雀斑、明亮绿瞳",
    },
  },
];

export function createEmptyChara(index: number): CharaProfile {
  const id = `c-new-${Date.now()}-${index}`;
  return {
    id,
    name: `新角色 #${index}`,
    avatarUrl: placeholder(900 + index, 200, 200),
    status: "idle",
    updatedAt: iso(new Date()),
    settingText: "",
    rawImages: [],
    officialPhotos: [null, null, null],
    bio: {
      displayName: "新角色",
      age: "—",
      height: "—",
      personality: "待补充",
      ability: "待补充",
      appearance: "待补充",
    },
  };
}
