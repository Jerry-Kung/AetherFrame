import repairApi from "@/services/repairApi";
import type { BackendTask } from "@/types/repair";

/** 与修补页配合：避免 Strict Mode 二次挂载时丢失路由 state 中的待选任务 ID */
export const OPEN_REPAIR_TASK_SESSION_KEY = "aetherframe.repair.openTaskId.v1";

export async function fetchImageBlobFromUrl(imageUrl: string): Promise<Blob> {
  const res = await fetch(imageUrl, { credentials: "include" });
  if (!res.ok) {
    throw new Error(`图片加载失败（HTTP ${res.status}）`);
  }
  return res.blob();
}

export function suggestedDownloadFilename(imageUrl: string): string {
  try {
    const base =
      typeof window !== "undefined" ? window.location.origin : "http://localhost";
    const u = new URL(imageUrl, base);
    const last = u.pathname.split("/").filter(Boolean).pop();
    if (last && /\.(png|jpe?g|webp|gif)$/i.test(last)) {
      return decodeURIComponent(last);
    }
  } catch {
    // ignore
  }
  return "aetherframe-image.png";
}

export async function downloadImageFromUrl(
  imageUrl: string,
  filename?: string
): Promise<void> {
  const blob = await fetchImageBlobFromUrl(imageUrl);
  const name = filename ?? suggestedDownloadFilename(imageUrl);
  const objectUrl = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = name;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function extensionForBlob(blob: Blob): string {
  const t = blob.type || "";
  if (t.includes("jpeg")) return "jpg";
  if (t.includes("webp")) return "webp";
  if (t.includes("gif")) return "gif";
  return "png";
}

/**
 * 创建空修补任务并将远程图片拉取后上传为主图；不启动修补。
 */
export async function createRepairDraftFromImageUrl(imageUrl: string): Promise<string> {
  const name = `待修补图片 · ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
  const task = await repairApi.createTask({ name, prompt: "", output_count: 1 });
  const taskId = String((task as BackendTask).id ?? "").trim();
  if (!taskId) {
    throw new Error("创建修补任务失败");
  }

  const blob = await fetchImageBlobFromUrl(imageUrl);
  const ext = extensionForBlob(blob);
  const file = new File([blob], `source.${ext}`, {
    type: blob.type || "image/png",
  });
  await repairApi.uploadMainImage(taskId, file);
  return taskId;
}
