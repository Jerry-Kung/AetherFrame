/**
 * 图片美化 /api/beautify
 */
import { ApiError, parseResponseBodyAsJson } from "@/services/api";

const API_BASE = "/api/beautify";
const DEFAULT_TIMEOUT = 30000;
const STATUS_POLL_TIMEOUT = 60000;

interface ApiEnvelope<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  detail?: unknown;
}

export type BeautifyStatus = "pending" | "processing" | "completed" | "failed";

export interface BeautifyStartResponse {
  task_id: string;
  status: BeautifyStatus;
  source_kind: string;
  source_task_id: string;
  source_image_path: string;
}

export interface BeautifyStatusResponse {
  task_id: string;
  source_kind: string;
  source_task_id: string;
  source_image_path: string;
  status: BeautifyStatus;
  current_step?: string | null;
  error_message?: string | null;
  beautified_filename?: string | null;
  beautified_url?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
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
  return parseResponseBodyAsJson<ApiEnvelope<T>>(response);
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
      response.status
    );
  }
  if (!data.success) {
    throw new ApiError(data.message || "请求失败", response.status);
  }
}

function rethrow(e: unknown): never {
  if (e instanceof ApiError) throw e;
  if (e instanceof Error && e.name === "AbortError") {
    throw new ApiError("请求超时", 408);
  }
  throw new ApiError(e instanceof Error ? e.message : "网络错误", 0);
}

export async function startBeautify(body: {
  source_kind: "quick_create" | "repair";
  source_task_id: string;
  source_image_path: string;
}): Promise<BeautifyStartResponse> {
  const url = `${API_BASE}/start`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJson<BeautifyStartResponse>(response);
    throwIfError(response, data);
    return data.data;
  } catch (e) {
    rethrow(e);
  }
}

export async function getBeautifyTaskStatus(taskId: string): Promise<BeautifyStatusResponse> {
  const tid = String(taskId ?? "").trim();
  if (!tid) throw new ApiError("美化任务 ID 无效", 400);
  const url = `${API_BASE}/tasks/${encodeURIComponent(tid)}/status`;
  try {
    const response = await fetchWithTimeout(url, { timeout: STATUS_POLL_TIMEOUT });
    const data = await parseJson<BeautifyStatusResponse>(response);
    throwIfError(response, data);
    return data.data;
  } catch (e) {
    rethrow(e);
  }
}

export async function deleteBeautifyTask(taskId: string): Promise<{ deleted_id: string }> {
  const tid = String(taskId ?? "").trim();
  if (!tid) throw new ApiError("美化任务 ID 无效", 400);
  const url = `${API_BASE}/tasks/${encodeURIComponent(tid)}`;
  try {
    const response = await fetchWithTimeout(url, { method: "DELETE" });
    const data = await parseJson<{ deleted_id: string }>(response);
    throwIfError(response, data);
    return data.data;
  } catch (e) {
    rethrow(e);
  }
}
