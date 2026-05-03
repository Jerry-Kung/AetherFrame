import * as creationApi from "@/services/creationApi";
import type { AiComment, QuickCreateGroup, QuickCreateImage } from "@/types/quickCreate";

function normalizePath(p: string): string {
  return String(p ?? "").trim().replace(/\\/g, "/");
}

/** 后端 `QuickCreateImageReview` → 前端 AI 评论弹框使用的 `AiComment` */
export function mapReviewToAiComment(review: creationApi.QuickCreateImageReview, imageId: string): AiComment {
  const overallRating = review.status === "usable" ? "good" : "needsFix";
  return {
    id: `ac-${imageId}`,
    imageId,
    overallRating,
    score: review.overall_quality,
    summary: review.summary,
    issues: [...review.major_issues],
    fixSuggestions: [...review.optimization_suggestions],
  };
}

/** 单条 API 图片条目（兼容历史纯字符串 path） */
export function quickCreateImageFromApiEntry(
  taskId: string,
  promptId: string,
  index: number,
  entry: string | creationApi.QuickCreateGeneratedImage
): QuickCreateImage {
  const id = `${taskId}-${promptId}-${index}`;
  if (typeof entry === "string") {
    const path = normalizePath(entry);
    return {
      id,
      promptId,
      url: creationApi.buildQuickCreateResultImageUrl(taskId, path),
    };
  }
  const path = normalizePath(entry.path);
  const review = entry.review ?? null;
  const base: QuickCreateImage = {
    id,
    promptId,
    url: creationApi.buildQuickCreateResultImageUrl(taskId, path),
  };
  if (review) {
    return { ...base, aiComment: mapReviewToAiComment(review, id) };
  }
  return base;
}

/** 轮询兜底：无历史详情 meta 时按接口结果直接拼组 */
export function mapQuickCreateResultsToGroups(
  taskId: string,
  results: creationApi.QuickCreatePromptResultItem[]
): QuickCreateGroup[] {
  return results.map((r) => ({
    promptId: r.prompt_id,
    promptTitle: r.prompt_id,
    promptPreview: r.full_prompt.slice(0, 80),
    images: (r.generated_images ?? []).map((img, i) => quickCreateImageFromApiEntry(taskId, r.prompt_id, i, img)),
  }));
}
