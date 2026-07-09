import * as creationApi from "@/services/creationApi";
import type { HydratedBatchItem } from "@/services/creationApi";
import type { PromptCard } from "@/types/creation";
import type { QuickCreateGroup, QuickCreateImage } from "@/types/quickCreate";
import { apiSeedSectionToUi, type BatchTask, type BatchTaskConfig } from "@/types/batchAutomation";
import { quickCreateImageFromApiEntry } from "@/utils/quickCreateReview";
import type { CharaProfile, SeedPrompt } from "@/types/material";

function resolveSeedDirectionMeta(
  chara: CharaProfile | undefined,
  seedPromptId: string,
  seedSection: string,
  seedCreativeDirectionId: string | null | undefined
): { creativeDirectionId: string | null; creativeDirectionMeta: SeedPrompt["creativeDirectionMeta"] } {
  if (seedSection === "fixed" || !chara?.bio.officialSeedPrompts) {
    return {
      creativeDirectionId: seedCreativeDirectionId ?? null,
      creativeDirectionMeta: null,
    };
  }
  const section =
    seedSection === "general"
      ? chara.bio.officialSeedPrompts.general
      : chara.bio.officialSeedPrompts.characterSpecific;
  const seed = section.find((s) => s.id === seedPromptId);
  return {
    creativeDirectionId: seed?.creativeDirectionId ?? seedCreativeDirectionId ?? null,
    creativeDirectionMeta: seed?.creativeDirectionMeta ?? null,
  };
}

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
  detail: creationApi.QuickCreateHistoryDetailResponse,
  promptTitleById?: Map<string, string>
): { groups: QuickCreateGroup[]; flat: QuickCreateImage[] } {
  const promptMetaMap = new Map((detail.selected_prompts ?? []).map((p) => [p.id, p.fullPrompt] as const));
  const groups: QuickCreateGroup[] = [];
  const flat: QuickCreateImage[] = [];
  for (const r of detail.results ?? []) {
    const imgs: QuickCreateImage[] = (r.generated_images ?? []).map((img, i) =>
      quickCreateImageFromApiEntry(detail.task_id, r.prompt_id, i, img)
    );
    for (const im of imgs) flat.push(im);
    const titleFromCards = promptTitleById?.get(r.prompt_id)?.trim();
    groups.push({
      promptId: r.prompt_id,
      promptTitle: titleFromCards || r.prompt_id,
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
  seed_creative_direction_id?: string | null;
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
  const sectionUi = apiSeedSectionToUi(row.seed_section);
  const dir = resolveSeedDirectionMeta(
    chara,
    row.seed_prompt_id,
    row.seed_section,
    row.seed_creative_direction_id
  );
  return {
    id: row.id,
    runId: row.run_id,
    runStatus: row.run_status,
    itemStatus: row.status,
    charaId: row.character_id,
    charaName: row.chara_name || chara?.name || "未知角色",
    charaAvatar: chara?.avatarUrl || row.chara_avatar || "",
    seedPromptId: row.seed_prompt_id,
    seedPromptSection: sectionUi,
    seedPromptText: row.seed_prompt_text,
    creativeDirectionId: dir.creativeDirectionId,
    creativeDirectionMeta: dir.creativeDirectionMeta,
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
    const promptTitleById = new Map(promptCards.map((c) => [c.id, c.title] as const));
    const { groups, flat } = buildGroupsFromQuickCreateDetail(qDetail, promptTitleById);
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

/**
 * 从后端聚合 API 返回的 hydrated item 直接构建完整的 BatchTask，
 * 无需额外网络请求。
 */
export function buildBatchTaskFromHydrated(
  row: HydratedBatchItem,
  charas: CharaProfile[],
  config: BatchTaskConfig
): BatchTask {
  const chara = charas.find((c) => c.id === row.character_id);
  const sectionUi = apiSeedSectionToUi(row.seed_section);
  const dir = resolveSeedDirectionMeta(
    chara,
    row.seed_prompt_id,
    row.seed_section,
    row.seed_creative_direction_id
  );

  const promptCards: PromptCard[] = (row.prompt_cards ?? []).map((c) => ({
    id: c.id ?? "",
    title: c.title ?? "",
    preview: c.preview ?? "",
    fullPrompt: c.fullPrompt ?? (c as { full_prompt?: string }).full_prompt ?? "",
    tags: c.tags ?? [],
    createdAt: c.createdAt ?? (c as { created_at?: string }).created_at ?? "",
  }));

  const promptTitleById = new Map(promptCards.map((c) => [c.id, c.title] as const));

  const groups: QuickCreateGroup[] = [];
  const flat: QuickCreateImage[] = [];

  if (row.quick_create_results && row.quick_create_task_id) {
    const taskId = row.quick_create_task_id;
    const fbMap = new Map(
      (row.feedbacks ?? []).map((f) => [`${f.prompt_id}#${f.image_index}`, f] as const)
    );
    const selectedPromptMap = new Map(
      (row.quick_create_selected_prompts ?? []).map((p) => [p.id, p.fullPrompt] as const)
    );

    for (const r of row.quick_create_results) {
      const imgs: QuickCreateImage[] = (r.generated_images ?? []).map((img, i) => {
        const base = quickCreateImageFromApiEntry(taskId, r.prompt_id, i, img);
        const fb = fbMap.get(`${r.prompt_id}#${i}`);
        return fb
          ? {
              ...base,
              userFeedback: {
                feedbackText: fb.feedback_text,
                legFootBad: fb.leg_foot_bad,
                selectedTags: fb.selected_tags ?? [],
              },
            }
          : base;
      });
      for (const im of imgs) flat.push(im);

      const titleFromCards = promptTitleById.get(r.prompt_id)?.trim();
      groups.push({
        promptId: r.prompt_id,
        promptTitle: titleFromCards || r.prompt_id,
        promptPreview: selectedPromptMap.get(r.prompt_id)?.slice(0, 80) || r.full_prompt.slice(0, 80),
        images: imgs,
      });
    }
  }

  return {
    id: row.id,
    runId: row.run_id,
    runStatus: row.run_status,
    itemStatus: row.status,
    charaId: row.character_id,
    charaName: row.chara_name || chara?.name || "未知角色",
    charaAvatar: chara?.avatarUrl || row.chara_avatar || "",
    seedPromptId: row.seed_prompt_id,
    seedPromptSection: sectionUi,
    seedPromptText: row.seed_prompt_text,
    creativeDirectionId: dir.creativeDirectionId,
    creativeDirectionMeta: dir.creativeDirectionMeta,
    promptRecordId: row.prompt_precreation_task_id ?? "",
    quickCreateRecordId: row.quick_create_task_id ?? "",
    config: { ...config },
    promptCards,
    images: flat,
    groups,
    createdAt: fmtShortTime(row.created_at),
    errorMessage: row.error_message ?? null,
  };
}
