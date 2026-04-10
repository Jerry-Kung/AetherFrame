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
  charaId: string;
  charaName: string;
  charaAvatar: string;
  promptCount: number;
  imagesPerPrompt: number;
  createdAt: string;
  groups: QuickCreateGroup[];
}
