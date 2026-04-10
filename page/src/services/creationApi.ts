/**
 * 创作模块 /api/creation — Prompt 预生成
 */
import type { PromptCard } from "@/types/creation";
import { ApiError } from "@/services/api";

const API_BASE = "/api/creation";
const DEFAULT_TIMEOUT = 30000;

interface ApiEnvelope<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  detail?: unknown;
}

type RequestConfig = NonNullable<Parameters<typeof fetch>[1]> & {
  timeout?: number;
};

async function fetchWithTimeout(
  url: string,
  options: RequestConfig = {}
): Promise<Response> {
  const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, { ...fetchOptions, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

async function parseJson<T>(response: Response): Promise<ApiEnvelope<T>> {
  try {
    return await response.json();
  } catch {
    throw new ApiError("响应解析失败", response.status);
  }
}

function throwIfError<T>(
  response: Response,
  data: ApiEnvelope<T>
): asserts data is ApiEnvelope<T> & { success: true; data: T } {
  if (!response.ok) {
    const detail = data.detail;
    const detailStr =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0] && typeof (detail[0] as { msg?: string }).msg === "string"
          ? (detail as { msg: string }[]).map((x) => x.msg).join("; ")
          : undefined;
    throw new ApiError(
      data.message || detailStr || `请求失败: ${response.status}`,
      response.status,
      data
    );
  }
  if (!data.success) {
    throw new ApiError(data.message || "操作失败", response.status, data);
  }
}

function rethrow(error: unknown): never {
  if (error instanceof ApiError) throw error;
  if (error instanceof Error) {
    if (error.name === "AbortError") throw new ApiError("请求超时", 408);
    throw new ApiError(`网络错误: ${error.message}`, 0, error);
  }
  throw new ApiError("未知错误", 0, error);
}

function assertValidCharacterId(characterId: string, action: string): void {
  const id = String(characterId ?? "").trim();
  if (!id || id === "undefined" || id === "null") {
    throw new ApiError(`角色ID无效，无法${action}`, 400);
  }
}

export interface PromptPrecreationStartResponse {
  task_id: string;
  status: string;
}

export interface PromptPrecreationStatusResponse {
  task_id: string;
  character_id: string;
  status: string;
  error_message?: string | null;
  current_step?: string | null;
  created_at: string;
  updated_at: string;
  cards?: PromptCard[] | null;
}

export interface QuickCreatePromptInput {
  id: string;
  fullPrompt: string;
}

export interface QuickCreateStartResponse {
  task_id: string;
  status: string;
}

export interface QuickCreatePromptResultItem {
  prompt_id: string;
  full_prompt: string;
  attempt_count: number;
  success_count: number;
  requested_count: number;
  generated_images: string[];
}

export interface QuickCreateStatusResponse {
  task_id: string;
  character_id: string;
  status: string;
  error_message?: string | null;
  current_step?: string | null;
  n: number;
  aspect_ratio: string;
  created_at: string;
  updated_at: string;
  results?: QuickCreatePromptResultItem[] | null;
}

export async function startPromptPrecreation(
  characterId: string,
  body: { seed_prompt: string; count: 2 | 3 | 4 }
): Promise<PromptPrecreationStartResponse> {
  assertValidCharacterId(characterId, "启动 Prompt 预生成");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/prompt-precreation/start`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seed_prompt: body.seed_prompt,
        count: body.count,
      }),
    });
    const data = await parseJson<PromptPrecreationStartResponse>(response);
    throwIfError(response, data);
    return data.data as PromptPrecreationStartResponse;
  } catch (e) {
    rethrow(e);
  }
}

export async function getPromptPrecreationTaskStatus(
  taskId: string
): Promise<PromptPrecreationStatusResponse> {
  const tid = String(taskId ?? "").trim();
  if (!tid) {
    throw new ApiError("任务ID无效", 400);
  }
  const url = `${API_BASE}/prompt-precreation/tasks/${encodeURIComponent(tid)}/status`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<PromptPrecreationStatusResponse>(response);
    throwIfError(response, data);
    return data.data as PromptPrecreationStatusResponse;
  } catch (e) {
    rethrow(e);
  }
}

export async function startQuickCreate(
  characterId: string,
  body: {
    selected_prompts: QuickCreatePromptInput[];
    n: 1 | 2 | 3 | 4;
    aspect_ratio: "16:9" | "4:3" | "1:1" | "3:4" | "9:16";
  }
): Promise<QuickCreateStartResponse> {
  assertValidCharacterId(characterId, "启动一键创作");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/quick-create/start`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      timeout: 120000,
    });
    const data = await parseJson<QuickCreateStartResponse>(response);
    throwIfError(response, data);
    return data.data as QuickCreateStartResponse;
  } catch (e) {
    rethrow(e);
  }
}

export async function getQuickCreateTaskStatus(taskId: string): Promise<QuickCreateStatusResponse> {
  const tid = String(taskId ?? "").trim();
  if (!tid) {
    throw new ApiError("任务ID无效", 400);
  }
  const url = `${API_BASE}/quick-create/tasks/${encodeURIComponent(tid)}/status`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<QuickCreateStatusResponse>(response);
    throwIfError(response, data);
    return data.data as QuickCreateStatusResponse;
  } catch (e) {
    rethrow(e);
  }
}

export function buildQuickCreateResultImageUrl(taskId: string, imagePath: string): string {
  const tid = encodeURIComponent(String(taskId ?? "").trim());
  const segs = String(imagePath ?? "")
    .split(/[\\/]+/)
    .filter(Boolean)
    .map((x) => encodeURIComponent(x));
  return `${API_BASE}/quick-create/tasks/${tid}/images/${segs.join("/")}`;
}
