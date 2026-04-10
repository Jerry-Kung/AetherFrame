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
