export type TaskStatus = "pending" | "processing" | "completed" | "failed";

export interface RepairTask {
  id: string;
  name: string;
  status: TaskStatus;
  createdAt: string;
  mainImage: string;
  prompt: string;
  referenceImages: string[];
  outputCount: 1 | 2 | 4;
  results: string[];
}

export const PROMPT_TEMPLATES = [
  { id: "t1", label: "皮肤瑕疵修补", text: "修补人物皮肤上的瑕疵，保持原有的动漫风格和色调，使皮肤光滑自然，细节真实。" },
  { id: "t2", label: "水印去除", text: "完整去除图片中的水印、文字标记及logo，自然填充背景，不留痕迹。" },
  { id: "t3", label: "背景噪点修复", text: "修复背景区域的噪点、模糊和色差问题，使背景干净清晰，与前景融合自然。" },
  { id: "t4", label: "角色轮廓补全", text: "补全残缺或被遮挡的动漫角色轮廓，风格保持一致，线条流畅自然。" },
  { id: "t5", label: "服装细节修复", text: "修复衣物皱褶、配饰残损等细节问题，保持角色整体风格统一，细节精致。" },
  { id: "t6", label: "眼睛高光补绘", text: "为角色眼睛添加或修复高光点，增强眼神灵动感，符合二次元美图风格。" },
];

export const mockRepairTasks: RepairTask[] = [
  {
    id: "task-001",
    name: "樱花少女服装修补",
    status: "completed",
    createdAt: "2026-04-01",
    mainImage: "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20in%20pink%20sakura%20dress%2C%20soft%20pastel%20watercolor%20style%2C%20kawaii%20character%20illustration%2C%20simple%20white%20background%2C%20high%20quality%20digital%20art%2C%20beautiful%20details&width=512&height=512&seq=rt001&orientation=squarish",
    prompt: "修复衣物皱褶、配饰残损等细节问题，保持角色整体风格统一，细节精致。",
    referenceImages: [],
    outputCount: 2,
    results: [
      "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20in%20pink%20sakura%20dress%20repaired%2C%20soft%20pastel%20watercolor%20style%2C%20kawaii%20character%20illustration%2C%20perfect%20smooth%20fabric%20details%2C%20high%20quality%20digital%20art&width=512&height=512&seq=rr001&orientation=squarish",
      "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20in%20pink%20floral%20dress%2C%20soft%20pastel%20watercolor%20style%2C%20kawaii%20character%20illustration%2C%20beautiful%20clothing%20details%2C%20high%20quality%20digital%20art&width=512&height=512&seq=rr002&orientation=squarish",
    ],
  },
  {
    id: "task-002",
    name: "背景噪点清除",
    status: "processing",
    createdAt: "2026-04-01",
    mainImage: "https://readdy.ai/api/search-image?query=anime%20scene%20with%20soft%20pastel%20background%2C%20dreamy%20bokeh%20lights%2C%20cherry%20blossom%20garden%2C%20delicate%20and%20ethereal%20atmosphere%2C%20kawaii%20aesthetic%20digital%20art&width=512&height=512&seq=rt002&orientation=squarish",
    prompt: "修复背景区域的噪点、模糊和色差问题，使背景干净清晰，与前景融合自然。",
    referenceImages: [],
    outputCount: 1,
    results: [],
  },
  {
    id: "task-003",
    name: "角色水印去除",
    status: "pending",
    createdAt: "2026-04-02",
    mainImage: "",
    prompt: "",
    referenceImages: [],
    outputCount: 1,
    results: [],
  },
  {
    id: "task-004",
    name: "眼睛高光补绘",
    status: "failed",
    createdAt: "2026-04-02",
    mainImage: "https://readdy.ai/api/search-image?query=close%20up%20anime%20eye%20illustration%2C%20pastel%20pink%20iris%2C%20sparkling%20highlights%2C%20kawaii%20magical%20girl%20eye%20art%2C%20soft%20watercolor%20style&width=512&height=512&seq=rt004&orientation=squarish",
    prompt: "为角色眼睛添加或修复高光点，增强眼神灵动感，符合二次元美图风格。",
    referenceImages: [],
    outputCount: 4,
    results: [],
  },
];
