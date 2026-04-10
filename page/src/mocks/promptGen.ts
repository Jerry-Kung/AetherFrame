import type { PromptCard, PromptHistoryRecord } from "@/types/creation";

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

export const MOCK_PROMPT_HISTORY: PromptHistoryRecord[] = [
  {
    id: "hist-001",
    charaId: "chara-1",
    charaName: "樱花小雪",
    charaAvatar:
      "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20with%20pink%20twin%20tails%2C%20white%20lace%20dress%2C%20soft%20pastel%20colors&width=64&height=64&seq=hist001&orientation=squarish",
    seedPrompt: "少女在樱花树下弹奏钢琴，阳光透过花瓣洒落，温柔而梦幻的氛围",
    promptCount: 3,
    cards: [
      {
        id: "hist-001-p1",
        title: "樱花飘落的午后",
        preview: "1girl, pink twin tails, white lace dress, cherry blossom petals falling...",
        fullPrompt:
          "masterpiece, best quality, 1girl, pink twin tails, blue eyes, white lace dress, pink ribbon bow, cherry blossom petals falling, soft afternoon sunlight, sitting under sakura tree, gentle smile, dreamy atmosphere, pastel color palette, watercolor style",
        tags: ["日常", "樱花", "温柔"],
        createdAt: "2026-04-08",
      },
      {
        id: "hist-001-p2",
        title: "钢琴少女的梦境",
        preview: "1girl, playing piano, flower petals, dreamy light, music notes...",
        fullPrompt:
          "masterpiece, best quality, 1girl, pink twin tails, playing grand piano, cherry blossom petals swirling, dreamy golden light, music notes floating, white lace dress, peaceful expression",
        tags: ["音乐", "梦幻", "春天"],
        createdAt: "2026-04-08",
      },
      {
        id: "hist-001-p3",
        title: "阳光与花瓣",
        preview: "1girl, sunlight through petals, gentle breeze, soft bokeh...",
        fullPrompt:
          "masterpiece, best quality, 1girl, pink twin tails, standing in sunlight, cherry blossom petals in wind, gentle breeze, soft bokeh background, warm afternoon light, serene expression",
        tags: ["阳光", "自然", "宁静"],
        createdAt: "2026-04-08",
      },
    ],
    createdAt: "2026-04-08 14:32",
  },
  {
    id: "hist-002",
    charaId: "chara-2",
    charaName: "星夜琉璃",
    charaAvatar:
      "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20with%20dark%20blue%20hair%2C%20star%20accessories%2C%20night%20sky%20theme&width=64&height=64&seq=hist002&orientation=squarish",
    seedPrompt: "魔法少女在星空下施展魔法，流星划过，神秘而璀璨",
    promptCount: 2,
    cards: [
      {
        id: "hist-002-p1",
        title: "星空魔法阵",
        preview: "1girl, magical circle, starry night, glowing runes, ethereal...",
        fullPrompt:
          "masterpiece, best quality, 1girl, dark blue hair, star hair accessories, magical circle glowing, starry night sky, ethereal runes, sparkle effects, magical girl outfit",
        tags: ["魔法", "星空", "神秘"],
        createdAt: "2026-04-07",
      },
      {
        id: "hist-002-p2",
        title: "流星许愿时刻",
        preview: "1girl, shooting star, wish pose, night sky, glowing...",
        fullPrompt:
          "masterpiece, best quality, 1girl, dark blue hair, looking up at shooting star, hands clasped in wish, night sky full of stars, soft glowing light, magical atmosphere",
        tags: ["流星", "许愿", "夜晚"],
        createdAt: "2026-04-07",
      },
    ],
    createdAt: "2026-04-07 20:15",
  },
];
