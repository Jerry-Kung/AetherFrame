export interface AiComment {
  id: string;
  imageId: string;
  overallRating: "good" | "needsFix";
  score: number;
  summary: string;
  issues: string[];
  fixSuggestions: string[];
}

export type BeautifyStatus = "pending" | "processing" | "completed" | "failed";

export interface QuickCreateImage {
  id: string;
  url: string;
  promptId: string;
  /** 组内序号（generated_images 下标），人工 feedback 定位用 */
  imageIndex?: number;
  aiComment?: AiComment | null;
  /** 已填的人工 feedback（null/undefined = 未填） */
  userFeedback?: { feedbackText: string; legFootBad: boolean } | null;
  beautifiedUrl?: string | null;
  beautifyTaskId?: string | null;
  beautifyStatus?: BeautifyStatus | null;
}

export interface QuickCreateGroup {
  promptId: string;
  promptTitle: string;
  promptPreview: string;
  images: QuickCreateImage[];
}

export interface QuickCreateRecord {
  id: string;
  taskId: string;
  charaId: string;
  charaName: string;
  charaAvatar: string;
  promptCount: number;
  imageCount: number;
  imagesPerPrompt: number;
  status: "pending" | "running" | "completed" | "failed";
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
  groups: QuickCreateGroup[];
}
