import { ApiError, parseResponseBodyAsJson } from "@/services/api";
import type { ImageRole, VideoTask } from "@/types/video";

const API_BASE = "/api/video";
const DEFAULT_TIMEOUT = 30000;

interface ApiEnvelope<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  detail?: unknown;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), DEFAULT_TIMEOUT);
  try {
    const resp = await fetch(`${API_BASE}${path}`, { ...init, signal: ctrl.signal });
    const body = (await parseResponseBodyAsJson(resp)) as ApiEnvelope<T>;
    if (!resp.ok || !body.success) {
      throw new ApiError(body.message || `请求失败 (${resp.status})`, resp.status);
    }
    return body.data as T;
  } finally {
    clearTimeout(timer);
  }
}

export function importFromQuickCreate(payload: {
  source_task_id: string;
  source_image_path: string;
  ref_prompt_text?: string | null;
}): Promise<VideoTask> {
  return call<VideoTask>("/tasks/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_kind: "quick_create", ...payload }),
  });
}

export function uploadImage(file: File): Promise<VideoTask> {
  const form = new FormData();
  form.append("file", file);
  return call<VideoTask>("/tasks/upload", { method: "POST", body: form });
}

export function startPromptJob(
  taskId: string, mode: "recommend" | "optimize", manualPrompt?: string,
): Promise<{ task_id: string; prompt_job_status: string }> {
  return call("/tasks/" + taskId + "/prompt-job/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, manual_prompt: manualPrompt ?? null }),
  });
}

export function getPromptJobStatus(taskId: string): Promise<VideoTask> {
  return call<VideoTask>(`/tasks/${taskId}/prompt-job/status`);
}

export function submitVideo(taskId: string, payload: {
  video_prompt_text: string; image_role: ImageRole;
  duration: number; generate_audio: boolean; ratio: string;
}): Promise<VideoTask> {
  return call<VideoTask>(`/tasks/${taskId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getStatus(taskId: string): Promise<VideoTask> {
  return call<VideoTask>(`/tasks/${taskId}/status`);
}

export function listTasks(): Promise<VideoTask[]> {
  return call<VideoTask[]>("/tasks");
}

export function deleteTask(taskId: string): Promise<{ deleted_id: string }> {
  return call(`/tasks/${taskId}`, { method: "DELETE" });
}

export const videoUrl = (taskId: string) => `${API_BASE}/tasks/${taskId}/video`;
export const imageUrl = (taskId: string) => `${API_BASE}/tasks/${taskId}/image`;
