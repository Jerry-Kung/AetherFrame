/** 与后端 `app/utils/image_generation_timeout.py` 一致：期望张数 × 20 分钟 */

export const IMAGE_GEN_MINUTES_PER_IMAGE = 20;

/** 与后端 `IMAGE_GEN_TIMEOUT_ERROR_MESSAGE` 一致，供前端兜底提示 */
export const IMAGE_GEN_TIMEOUT_USER_MESSAGE =
  "等待超时，已自动终止任务（已超过「本次需生成图片张数 × 20 分钟」的等待上限）。";

export function imageGenerationTimeoutMs(imageCount: number): number {
  const n = Math.max(1, Math.floor(Number(imageCount)) || 1);
  return n * IMAGE_GEN_MINUTES_PER_IMAGE * 60 * 1000;
}

/**
 * @param isoString 服务端时间锚的 ISO 字符串（如 created_at / updated_at）
 */
export function isPastImageGenDeadline(isoString: string | null | undefined, imageCount: number): boolean {
  if (isoString == null || String(isoString).trim() === "") return false;
  const start = Date.parse(String(isoString));
  if (!Number.isFinite(start)) return false;
  return Date.now() - start >= imageGenerationTimeoutMs(imageCount);
}
