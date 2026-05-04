import type { PromptCard } from "@/types/creation";
import type { QuickCreateGroup, QuickCreateImage } from "@/types/quickCreate";

/** 任务配置弹窗与提交 API 共用 */
export interface BatchTaskConfig {
  /** 产出批次数量（每批对应一条产线记录） */
  batchCount: number;
  promptCount: number;
  imagesPerPrompt: number;
  aspectRatio: string;
}

export const DEFAULT_BATCH_CONFIG: BatchTaskConfig = {
  batchCount: 5,
  promptCount: 2,
  imagesPerPrompt: 2,
  aspectRatio: "1:1",
};

/** 与素材模块 `SeedPromptSection` 一致，用于标记「已使用」 */
export type BatchSeedSection = "characterSpecific" | "general" | "fixed";

export function apiSeedSectionToUi(section: string): BatchSeedSection {
  if (section === "general") return "general";
  if (section === "fixed") return "fixed";
  return "characterSpecific";
}

/** 首页单条批量创作展示（含拉取后的 Prompt / 图片） */
export interface BatchTask {
  id: string;
  runId: string;
  runStatus: string;
  itemStatus: string;
  charaId: string;
  charaName: string;
  charaAvatar: string;
  seedPromptId: string;
  seedPromptSection: BatchSeedSection;
  seedPromptText: string;
  promptRecordId: string;
  quickCreateRecordId: string;
  config: BatchTaskConfig;
  promptCards: PromptCard[];
  images: QuickCreateImage[];
  groups: QuickCreateGroup[];
  createdAt: string;
  errorMessage?: string | null;
}
