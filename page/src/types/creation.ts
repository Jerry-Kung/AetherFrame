export interface PromptCard {
  id: string;
  title: string;
  preview: string;
  fullPrompt: string;
  tags: string[];
  createdAt: string;
}

/** 供「美图创作」承接的上一轮预生成结果（由 Creation 页持有） */
export interface CreationPromptSession {
  charaId: string;
  cards: PromptCard[];
  updatedAt: number;
}

export interface PromptHistoryRecord {
  id: string;
  taskId: string;
  charaId: string;
  charaName: string;
  charaAvatar: string;
  seedPrompt: string;
  promptCount: number;
  status: "pending" | "running" | "completed" | "failed";
  errorMessage?: string | null;
  cards: PromptCard[];
  createdAt: string;
  updatedAt: string;
}
