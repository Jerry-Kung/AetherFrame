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

export const MOCK_QUICK_CREATE_RECORDS: QuickCreateRecord[] = [
  {
    id: "qc001",
    charaId: "c001",
    charaName: "星野爱莉",
    charaAvatar:
      "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20avatar%20with%20pink%20twin%20tails%2C%20blue%20eyes%2C%20white%20dress%2C%20kawaii%20style%2C%20soft%20pastel%20colors%2C%20chibi%20portrait%2C%20simple%20clean%20background&width=80&height=80&seq=qca001&orientation=squarish",
    promptCount: 3,
    imagesPerPrompt: 2,
    createdAt: "2026-04-09 14:32",
    groups: [
      {
        promptId: "p001",
        promptTitle: "樱花飘落的午后",
        promptPreview: "1girl, pink twin tails, white lace dress, cherry blossom petals falling...",
        images: [
          {
            id: "img001",
            promptId: "p001",
            url: "https://readdy.ai/api/search-image?query=beautiful%20anime%20girl%20with%20pink%20twin%20tails%20sitting%20under%20cherry%20blossom%20tree%2C%20white%20lace%20dress%2C%20soft%20afternoon%20sunlight%2C%20sakura%20petals%20falling%2C%20dreamy%20pastel%20watercolor%20illustration%2C%20kawaii%20magical%20girl%20aesthetic%2C%20high%20quality%20anime%20art&width=512&height=512&seq=qci001&orientation=squarish",
          },
          {
            id: "img002",
            promptId: "p001",
            url: "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20pink%20hair%20twin%20tails%20cherry%20blossom%20garden%2C%20white%20dress%20with%20pink%20ribbons%2C%20gentle%20smile%2C%20soft%20bokeh%20background%2C%20pastel%20pink%20and%20white%20color%20palette%2C%20spring%20atmosphere%2C%20anime%20illustration%20style&width=512&height=512&seq=qci002&orientation=squarish",
          },
        ],
      },
      {
        promptId: "p002",
        promptTitle: "月光下的歌声",
        promptPreview: "1girl, singing pose, moonlight, magical aura, music notes floating...",
        images: [
          {
            id: "img003",
            promptId: "p002",
            url: "https://readdy.ai/api/search-image?query=anime%20girl%20singing%20under%20moonlight%2C%20pink%20twin%20tails%2C%20white%20dress%2C%20magical%20music%20notes%20floating%20around%2C%20ethereal%20glow%2C%20night%20sky%20with%20stars%2C%20pastel%20purple%20and%20pink%20tones%2C%20kawaii%20magical%20girl%2C%20sparkle%20effects%2C%20anime%20art%20style&width=512&height=512&seq=qci003&orientation=squarish",
          },
          {
            id: "img004",
            promptId: "p002",
            url: "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20with%20pink%20hair%20performing%20magical%20song%2C%20moonlight%20streaming%2C%20cherry%20blossom%20petals%2C%20soft%20glowing%20aura%2C%20dreamy%20night%20atmosphere%2C%20pastel%20colors%2C%20high%20quality%20anime%20illustration&width=512&height=512&seq=qci004&orientation=squarish",
          },
        ],
      },
      {
        promptId: "p003",
        promptTitle: "少女与小动物",
        promptPreview: "1girl, surrounded by cute animals, meadow, playful expression...",
        images: [
          {
            id: "img005",
            promptId: "p003",
            url: "https://readdy.ai/api/search-image?query=anime%20girl%20with%20pink%20twin%20tails%20surrounded%20by%20cute%20rabbits%20and%20cats%20in%20flower%20meadow%2C%20white%20lace%20dress%2C%20playful%20happy%20expression%2C%20warm%20sunlight%2C%20soft%20pastel%20colors%2C%20kawaii%20illustration%20style%2C%20spring%20vibes&width=512&height=512&seq=qci005&orientation=squarish",
          },
          {
            id: "img006",
            promptId: "p003",
            url: "https://readdy.ai/api/search-image?query=cute%20kawaii%20anime%20girl%20pink%20hair%20with%20small%20animals%20birds%20and%20bunnies%2C%20green%20meadow%20wildflowers%2C%20cheerful%20atmosphere%2C%20reaching%20out%20hand%20to%20small%20bird%2C%20warm%20sunlight%2C%20pastel%20anime%20art%20style&width=512&height=512&seq=qci006&orientation=squarish",
          },
        ],
      },
    ],
  },
  {
    id: "qc002",
    charaId: "c001",
    charaName: "星野爱莉",
    charaAvatar:
      "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20avatar%20with%20pink%20twin%20tails%2C%20blue%20eyes%2C%20white%20dress%2C%20kawaii%20style%2C%20soft%20pastel%20colors%2C%20chibi%20portrait%2C%20simple%20clean%20background&width=80&height=80&seq=qca001&orientation=squarish",
    promptCount: 2,
    imagesPerPrompt: 3,
    createdAt: "2026-04-08 20:15",
    groups: [
      {
        promptId: "p001",
        promptTitle: "樱花飘落的午后",
        promptPreview: "1girl, pink twin tails, white lace dress, cherry blossom petals falling...",
        images: [
          {
            id: "img007",
            promptId: "p001",
            url: "https://readdy.ai/api/search-image?query=anime%20girl%20pink%20twin%20tails%20sakura%20tree%20afternoon%2C%20white%20dress%2C%20soft%20light%2C%20dreamy%20pastel%20watercolor%2C%20kawaii%20aesthetic&width=512&height=512&seq=qci007&orientation=squarish",
          },
          {
            id: "img008",
            promptId: "p001",
            url: "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20cherry%20blossom%20garden%20pink%20hair%2C%20lace%20dress%2C%20gentle%20breeze%2C%20petals%20falling%2C%20soft%20bokeh%2C%20pastel%20illustration&width=512&height=512&seq=qci008&orientation=squarish",
          },
          {
            id: "img009",
            promptId: "p001",
            url: "https://readdy.ai/api/search-image?query=kawaii%20anime%20girl%20under%20sakura%20tree%20pink%20twin%20tails%2C%20white%20lace%20outfit%2C%20spring%20afternoon%2C%20warm%20golden%20light%2C%20dreamy%20atmosphere%2C%20anime%20art&width=512&height=512&seq=qci009&orientation=squarish",
          },
        ],
      },
      {
        promptId: "p002",
        promptTitle: "月光下的歌声",
        promptPreview: "1girl, singing pose, moonlight, magical aura, music notes floating...",
        images: [
          {
            id: "img010",
            promptId: "p002",
            url: "https://readdy.ai/api/search-image?query=anime%20magical%20girl%20singing%20moonlight%20night%2C%20pink%20hair%2C%20white%20dress%2C%20music%20notes%20sparkle%2C%20ethereal%20glow%2C%20stars%2C%20pastel%20purple%20pink%20tones&width=512&height=512&seq=qci010&orientation=squarish",
          },
          {
            id: "img011",
            promptId: "p002",
            url: "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20performing%20under%20moonlight%2C%20pink%20twin%20tails%2C%20magical%20aura%2C%20cherry%20blossom%20night%2C%20soft%20glowing%2C%20dreamy%20pastel%20colors&width=512&height=512&seq=qci011&orientation=squarish",
          },
          {
            id: "img012",
            promptId: "p002",
            url: "https://readdy.ai/api/search-image?query=kawaii%20anime%20girl%20singing%20magical%20song%20night%20sky%2C%20pink%20hair%2C%20white%20dress%2C%20music%20magic%20sparkles%2C%20moonlight%2C%20pastel%20illustration%20style&width=512&height=512&seq=qci012&orientation=squarish",
          },
        ],
      },
    ],
  },
];

/** 占位出图 URL 池（按 promptId 哈希取值，适配动态 id） */
export const QUICK_CREATE_IMAGE_POOL: string[] = [
  "https://readdy.ai/api/search-image?query=beautiful%20anime%20girl%20with%20pink%20twin%20tails%20sitting%20under%20cherry%20blossom%20tree%2C%20white%20lace%20dress%2C%20soft%20afternoon%20sunlight%2C%20sakura%20petals%20falling%2C%20dreamy%20pastel%20watercolor%20illustration%2C%20kawaii%20magical%20girl%20aesthetic%2C%20high%20quality%20anime%20art&width=512&height=512&seq=qcg001&orientation=squarish",
  "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20pink%20hair%20twin%20tails%20cherry%20blossom%20garden%2C%20white%20dress%20with%20pink%20ribbons%2C%20gentle%20smile%2C%20soft%20bokeh%20background%2C%20pastel%20pink%20and%20white%20color%20palette%2C%20spring%20atmosphere%2C%20anime%20illustration%20style&width=512&height=512&seq=qcg002&orientation=squarish",
  "https://readdy.ai/api/search-image?query=kawaii%20anime%20girl%20under%20sakura%20tree%20pink%20twin%20tails%2C%20white%20lace%20outfit%2C%20spring%20afternoon%2C%20warm%20golden%20light%2C%20dreamy%20atmosphere%2C%20anime%20art&width=512&height=512&seq=qcg003&orientation=squarish",
  "https://readdy.ai/api/search-image?query=anime%20girl%20pink%20twin%20tails%20sakura%20petals%20falling%2C%20white%20dress%2C%20soft%20light%2C%20dreamy%20pastel%20watercolor%2C%20kawaii%20aesthetic%2C%20high%20detail&width=512&height=512&seq=qcg004&orientation=squarish",
  "https://readdy.ai/api/search-image?query=anime%20girl%20singing%20under%20moonlight%2C%20pink%20twin%20tails%2C%20white%20dress%2C%20magical%20music%20notes%20floating%20around%2C%20ethereal%20glow%2C%20night%20sky%20with%20stars%2C%20pastel%20purple%20and%20pink%20tones%2C%20kawaii%20magical%20girl%2C%20sparkle%20effects%2C%20anime%20art%20style&width=512&height=512&seq=qcg005&orientation=squarish",
  "https://readdy.ai/api/search-image?query=cute%20anime%20girl%20with%20pink%20hair%20performing%20magical%20song%2C%20moonlight%20streaming%2C%20cherry%20blossom%20petals%2C%20soft%20glowing%20aura%2C%20dreamy%20night%20atmosphere%2C%20pastel%20colors%2C%20high%20quality%20anime%20illustration&width=512&height=512&seq=qcg006&orientation=squarish",
  "https://readdy.ai/api/search-image?query=kawaii%20anime%20girl%20singing%20magical%20song%20night%20sky%2C%20pink%20hair%2C%20white%20dress%2C%20music%20magic%20sparkles%2C%20moonlight%2C%20pastel%20illustration%20style&width=512&height=512&seq=qcg007&orientation=squarish",
  "https://readdy.ai/api/search-image?query=anime%20magical%20girl%20singing%20moonlight%20night%2C%20pink%20hair%2C%20white%20dress%2C%20music%20notes%20sparkle%2C%20ethereal%20glow%2C%20stars%2C%20pastel%20purple%20pink%20tones&width=512&height=512&seq=qcg008&orientation=squarish",
  "https://readdy.ai/api/search-image?query=anime%20girl%20with%20pink%20twin%20tails%20surrounded%20by%20cute%20rabbits%20and%20cats%20in%20flower%20meadow%2C%20white%20lace%20dress%2C%20playful%20happy%20expression%2C%20warm%20sunlight%2C%20soft%20pastel%20colors%2C%20kawaii%20illustration%20style%2C%20spring%20vibes&width=512&height=512&seq=qcg009&orientation=squarish",
  "https://readdy.ai/api/search-image?query=cute%20kawaii%20anime%20girl%20pink%20hair%20with%20small%20animals%20birds%20and%20bunnies%2C%20green%20meadow%20wildflowers%2C%20cheerful%20atmosphere%2C%20reaching%20out%20hand%20to%20small%20bird%2C%20warm%20sunlight%2C%20pastel%20anime%20art%20style&width=512&height=512&seq=qcg010&orientation=squarish",
  "https://readdy.ai/api/search-image?query=kawaii%20anime%20girl%20surrounded%20by%20cute%20animals%20in%20spring%20meadow%2C%20pink%20twin%20tails%2C%20white%20dress%2C%20flowers%2C%20warm%20light%2C%20pastel%20colors%2C%20anime%20illustration&width=512&height=512&seq=qcg011&orientation=squarish",
  "https://readdy.ai/api/search-image?query=anime%20girl%20pink%20hair%20with%20rabbits%20cats%20birds%20in%20flower%20field%2C%20white%20lace%20dress%2C%20happy%20smile%2C%20soft%20sunlight%2C%20pastel%20spring%20atmosphere%2C%20kawaii%20art%20style&width=512&height=512&seq=qcg012&orientation=squarish",
];

export function pickQuickCreateMockUrls(promptId: string, count: number): string[] {
  let h = 0;
  for (let i = 0; i < promptId.length; i++) {
    h = (h * 31 + promptId.charCodeAt(i)) >>> 0;
  }
  const pool = QUICK_CREATE_IMAGE_POOL;
  return Array.from({ length: count }, (_, i) => pool[(h + i) % pool.length]!);
}
