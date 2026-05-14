import type { PromptCard, PromptHistoryRecord } from "@/types/creation";

/** 历史 demo 列表已迁至真实 API；保留空导出以兼容旧 import。 */
export const MOCK_PROMPT_HISTORY: PromptHistoryRecord[] = [];

export const MOCK_PROMPT_CARDS: PromptCard[] = [
  {
    id: "p001",
    title: "樱花飘落的午后",
    preview: "1girl, pink twin tails, white lace dress, cherry blossom petals falling...",
    fullPrompt:
      "masterpiece, best quality, 1girl, pink twin tails, blue eyes, white lace dress, pink ribbon bow, cherry blossom petals falling, soft afternoon sunlight, sitting under sakura tree, gentle smile, dreamy atmosphere, pastel color palette, watercolor style, kawaii, magical girl aesthetic",
    tags: ["日常", "樱花", "温柔"],
    createdAt: "2026-04-09",
  },
  {
    id: "p002",
    title: "月光下的歌声",
    preview: "1girl, singing pose, moonlight, magical aura, music notes floating...",
    fullPrompt:
      "masterpiece, best quality, 1girl, pink twin tails, blue eyes, white lace dress, singing with eyes closed, moonlight streaming down, magical music notes floating around, soft glowing aura, cherry blossom petals, night sky with stars, ethereal atmosphere, pastel purple and pink tones",
    tags: ["魔法", "夜晚", "歌唱"],
    createdAt: "2026-04-09",
  },
];
