export interface PromptCard {
  id: string;
  title: string;
  preview: string;
  fullPrompt: string;
  tags: string[];
  createdAt: string;
}

export interface PromptGenSession {
  charaId: string;
  seedPrompt: string;
  count: number;
  cards: PromptCard[];
}

/** 供「美图创作 → 一键创作」承接的上一轮预生成结果（由 Creation 页持有） */
export interface CreationPromptSession {
  charaId: string;
  cards: PromptCard[];
  updatedAt: number;
}

export const MOCK_PROMPT_CARDS: PromptCard[] = [
  {
    id: "p001",
    title: "樱花飘落的午后",
    preview: "1girl, pink twin tails, white lace dress, cherry blossom petals falling...",
    fullPrompt:
      "masterpiece, best quality, 1girl, pink twin tails, blue eyes, white lace dress, pink ribbon bow, cherry blossom petals falling, soft afternoon sunlight, sitting under sakura tree, gentle smile, dreamy atmosphere, pastel color palette, watercolor style, kawaii, magical girl aesthetic, delicate features, sparkling eyes, flower petals in hair, warm bokeh background, soft focus, high detail, anime illustration style, (pink sakura:1.3), (soft light:1.2), (dreamy:1.1)",
    tags: ["日常", "樱花", "温柔"],
    createdAt: "2026-04-09",
  },
  {
    id: "p002",
    title: "月光下的歌声",
    preview: "1girl, singing pose, moonlight, magical aura, music notes floating...",
    fullPrompt:
      "masterpiece, best quality, 1girl, pink twin tails, blue eyes, white lace dress, singing with eyes closed, moonlight streaming down, magical music notes floating around, soft glowing aura, cherry blossom petals, night sky with stars, ethereal atmosphere, pastel purple and pink tones, kawaii magical girl, sparkle effects, (moonlight:1.3), (music magic:1.2), (ethereal glow:1.2), soft watercolor background, anime style, high quality illustration",
    tags: ["魔法", "夜晚", "歌唱"],
    createdAt: "2026-04-09",
  },
  {
    id: "p003",
    title: "少女与小动物",
    preview: "1girl, surrounded by cute animals, meadow, playful expression...",
    fullPrompt:
      "masterpiece, best quality, 1girl, pink twin tails, blue eyes, white lace dress, surrounded by cute small animals (rabbits, cats, birds), green meadow, wildflowers, playful happy expression, reaching out hand to small bird, warm sunlight, soft pastel colors, kawaii illustration style, (cute animals:1.3), (meadow flowers:1.2), (warm sunlight:1.1), cheerful atmosphere, spring vibes, anime art style, high detail",
    tags: ["可爱", "动物", "春天"],
    createdAt: "2026-04-09",
  },
];
