import * as creationApi from "@/services/creationApi";
import type { PromptCard } from "@/types/creation";
import type { QuickCreateGroup, QuickCreateImage } from "@/types/quickCreate";
import { apiSeedSectionToUi, type BatchTask, type BatchTaskConfig } from "@/types/batchAutomation";
import { quickCreateImageFromApiEntry } from "@/utils/quickCreateReview";
import type { CharaProfile } from "@/types/material";

function fmtShortTime(iso: string): string {
  const d = Date.parse(iso);
  if (Number.isNaN(d)) return iso;
  return new Date(d).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function mapPromptCards(cards: creationApi.PromptPrecreationHistoryDetailResponse["cards"]): PromptCard[] {
  return (cards ?? []).map((c) => {
    const row = c as PromptCard & { created_at?: string };
    return {
      id: row.id,
      title: row.title,
      preview: row.preview,
      fullPrompt: row.fullPrompt,
      tags: row.tags ?? [],
      createdAt:
        typeof row.createdAt === "string"
          ? row.createdAt
          : typeof row.created_at === "string"
            ? row.created_at
            : "",
    };
  });
}

function buildGroupsFromQuickCreateDetail(
  detail: creationApi.QuickCreateHistoryDetailResponse
): { groups: QuickCreateGroup[]; flat: QuickCreateImage[] } {
  const promptMetaMap = new Map((detail.selected_prompts ?? []).map((p) => [p.id, p.fullPrompt] as const));
  const groups: QuickCreateGroup[] = [];
  const flat: QuickCreateImage[] = [];
  for (const r of detail.results ?? []) {
    const imgs: QuickCreateImage[] = (r.generated_images ?? []).map((img, i) =>
      quickCreateImageFromApiEntry(detail.task_id, r.prompt_id, i, img)
    );
    for (const im of imgs) flat.push(im);
    groups.push({
      promptId: r.prompt_id,
      promptTitle: r.prompt_id,
      promptPreview: promptMetaMap.get(r.prompt_id)?.slice(0, 80) || r.full_prompt.slice(0, 80),
      images: imgs,
    });
  }
  return { groups, flat };
}

export interface BatchAutomationListItemApi {
  id: string;
  run_id: string;
  run_status: string;
  step_index: number;
  character_id: string;
  chara_name: string;
  chara_avatar: string;
  seed_prompt_id: string;
  seed_section: string;
  seed_prompt_text: string;
  prompt_precreation_task_id?: string | null;
  quick_create_task_id?: string | null;
  status: string;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export function buildSkeletonBatchTask(
  row: BatchAutomationListItemApi,
  charas: CharaProfile[],
  config: BatchTaskConfig
): BatchTask {
  const chara = charas.find((c) => c.id === row.character_id);
  return {
    id: row.id,
    runId: row.run_id,
    runStatus: row.run_status,
    itemStatus: row.status,
    charaId: row.character_id,
    charaName: row.chara_name || chara?.name || "未知角色",
    charaAvatar: chara?.avatarUrl || row.chara_avatar || "",
    seedPromptId: row.seed_prompt_id,
    seedPromptSection: apiSeedSectionToUi(row.seed_section),
    seedPromptText: row.seed_prompt_text,
    promptRecordId: row.prompt_precreation_task_id ?? "",
    quickCreateRecordId: row.quick_create_task_id ?? "",
    config: { ...config },
    promptCards: [],
    images: [],
    groups: [],
    createdAt: fmtShortTime(row.created_at),
    errorMessage: row.error_message ?? null,
  };
}

export async function hydrateBatchTask(task: BatchTask): Promise<BatchTask> {
  const ppc = task.promptRecordId;
  const qc = task.quickCreateRecordId;
  if (!ppc || !qc || task.itemStatus !== "completed") {
    return task;
  }
  try {
    const [pDetail, qDetail] = await Promise.all([
      creationApi.getPromptPrecreationHistory(ppc),
      creationApi.getQuickCreateHistory(qc),
    ]);
    const promptCards = mapPromptCards(pDetail.cards);
    const { groups, flat } = buildGroupsFromQuickCreateDetail(qDetail);
    return {
      ...task,
      promptCards,
      groups,
      images: flat,
      charaName: pDetail.chara_name || task.charaName,
    };
  } catch {
    return task;
  }
}
