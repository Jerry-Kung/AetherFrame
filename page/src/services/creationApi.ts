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

export interface PromptPrecreationHistoryItem {
  id: string;
  task_id: string;
  character_id: string;
  chara_name: string;
  chara_avatar: string;
  seed_prompt: string;
  prompt_count: number;
  status: "pending" | "running" | "completed" | "failed";
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PromptPrecreationHistoryDetailResponse extends PromptPrecreationHistoryItem {
  cards: PromptCard[];
}

export interface PromptPrecreationHistoryListResponse {
  items: PromptPrecreationHistoryItem[];
  total: number;
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

export interface QuickCreateHistoryItem {
  id: string;
  task_id: string;
  character_id: string;
  chara_name: string;
  chara_avatar: string;
  prompt_count: number;
  image_count: number;
  n: number;
  aspect_ratio: string;
  status: "pending" | "running" | "completed" | "failed";
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuickCreateHistoryDetailResponse extends QuickCreateHistoryItem {
  selected_prompts: QuickCreatePromptInput[];
  results: QuickCreatePromptResultItem[];
}

export interface QuickCreateHistoryListResponse {
  items: QuickCreateHistoryItem[];
  total: number;
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

export async function listPromptPrecreationHistory(params?: {
  limit?: number;
  offset?: number;
  /** 筛选任务状态，如 completed */
  status?: string;
}): Promise<PromptPrecreationHistoryListResponse> {
  const query = new URLSearchParams();
  if (typeof params?.limit === "number") query.set("limit", String(params.limit));
  if (typeof params?.offset === "number") query.set("offset", String(params.offset));
  if (params?.status && String(params.status).trim()) {
    query.set("status", String(params.status).trim());
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const url = `${API_BASE}/prompt-precreation/history${suffix}`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<PromptPrecreationHistoryListResponse>(response);
    throwIfError(response, data);
    return data.data as PromptPrecreationHistoryListResponse;
  } catch (e) {
    rethrow(e);
  }
}

export async function getLatestPromptPrecreationHistory(): Promise<PromptPrecreationHistoryDetailResponse | null> {
  const url = `${API_BASE}/prompt-precreation/history/latest`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<PromptPrecreationHistoryDetailResponse | null>(response);
    throwIfError(response, data);
    return (data.data ?? null) as PromptPrecreationHistoryDetailResponse | null;
  } catch (e) {
    rethrow(e);
  }
}

/** 全库最近一条已完成的 Prompt 预生成（一键创作默认灵感来源） */
export async function getLatestCompletedPromptPrecreationHistory(): Promise<PromptPrecreationHistoryDetailResponse | null> {
  const url = `${API_BASE}/prompt-precreation/history/latest-completed`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<PromptPrecreationHistoryDetailResponse | null>(response);
    throwIfError(response, data);
    return (data.data ?? null) as PromptPrecreationHistoryDetailResponse | null;
  } catch (e) {
    rethrow(e);
  }
}

export async function getPromptPrecreationHistory(
  historyId: string
): Promise<PromptPrecreationHistoryDetailResponse> {
  const hid = String(historyId ?? "").trim();
  if (!hid) {
    throw new ApiError("历史ID无效", 400);
  }
  const url = `${API_BASE}/prompt-precreation/history/${encodeURIComponent(hid)}`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<PromptPrecreationHistoryDetailResponse>(response);
    throwIfError(response, data);
    return data.data as PromptPrecreationHistoryDetailResponse;
  } catch (e) {
    rethrow(e);
  }
}

export async function deletePromptPrecreationHistory(historyId: string): Promise<{
  deleted_id: string;
  latest: PromptPrecreationHistoryDetailResponse | null;
}> {
  const hid = String(historyId ?? "").trim();
  if (!hid) {
    throw new ApiError("历史ID无效", 400);
  }
  const url = `${API_BASE}/prompt-precreation/history/${encodeURIComponent(hid)}`;
  try {
    const response = await fetchWithTimeout(url, { method: "DELETE" });
    const data = await parseJson<{
      deleted_id: string;
      latest: PromptPrecreationHistoryDetailResponse | null;
    }>(response);
    throwIfError(response, data);
    return data.data as { deleted_id: string; latest: PromptPrecreationHistoryDetailResponse | null };
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

export async function listQuickCreateHistory(params?: {
  limit?: number;
  offset?: number;
}): Promise<QuickCreateHistoryListResponse> {
  const query = new URLSearchParams();
  if (typeof params?.limit === "number") query.set("limit", String(params.limit));
  if (typeof params?.offset === "number") query.set("offset", String(params.offset));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const url = `${API_BASE}/quick-create/history${suffix}`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<QuickCreateHistoryListResponse>(response);
    throwIfError(response, data);
    return data.data as QuickCreateHistoryListResponse;
  } catch (e) {
    rethrow(e);
  }
}

export async function getLatestQuickCreateHistory(): Promise<QuickCreateHistoryDetailResponse | null> {
  const url = `${API_BASE}/quick-create/history/latest`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<QuickCreateHistoryDetailResponse | null>(response);
    throwIfError(response, data);
    return (data.data ?? null) as QuickCreateHistoryDetailResponse | null;
  } catch (e) {
    rethrow(e);
  }
}

export async function getQuickCreateHistory(historyId: string): Promise<QuickCreateHistoryDetailResponse> {
  const hid = String(historyId ?? "").trim();
  if (!hid) throw new ApiError("历史ID无效", 400);
  const url = `${API_BASE}/quick-create/history/${encodeURIComponent(hid)}`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<QuickCreateHistoryDetailResponse>(response);
    throwIfError(response, data);
    return data.data as QuickCreateHistoryDetailResponse;
  } catch (e) {
    rethrow(e);
  }
}

export async function deleteQuickCreateHistory(historyId: string): Promise<{
  deleted_id: string;
  latest: QuickCreateHistoryDetailResponse | null;
}> {
  const hid = String(historyId ?? "").trim();
  if (!hid) throw new ApiError("历史ID无效", 400);
  const url = `${API_BASE}/quick-create/history/${encodeURIComponent(hid)}`;
  try {
    const response = await fetchWithTimeout(url, { method: "DELETE" });
    const data = await parseJson<{
      deleted_id: string;
      latest: QuickCreateHistoryDetailResponse | null;
    }>(response);
    throwIfError(response, data);
    return data.data as { deleted_id: string; latest: QuickCreateHistoryDetailResponse | null };
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
