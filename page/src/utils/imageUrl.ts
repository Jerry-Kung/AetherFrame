/**
 * 后端图片 URL 的缩略图变体。
 *
 * 列表/网格/卡片等小尺寸展示场景使用,后端返回 ~512px WebP(原图够小或生成失败时
 * 自动回退原图)。大图预览、裁剪、质检(feedback)场景必须继续用原始 URL。
 */
export function thumbUrl(url: string | null | undefined): string {
  if (!url) return "";
  // data:/blob: 本地资源、非本站 API 的 URL 原样返回
  if (!url.startsWith("/api/")) return url;
  return url.includes("?") ? `${url}&variant=thumb` : `${url}?variant=thumb`;
}
