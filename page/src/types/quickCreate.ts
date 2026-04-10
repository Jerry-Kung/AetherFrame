export interface QuickCreateImage {
  id: string;
  url: string;
  promptId: string;
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
