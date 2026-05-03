/**
 * API基础服务（修补模块 /api/repair）
 */

import type { ApiResponse } from "@/types/repair";

const API_BASE_URL = "/api/repair";
const DEFAULT_TIMEOUT = 30000; // 30秒

export class ApiError extends Error {
  status?: number;
  details?: any;

  constructor(message: string, status?: number, details?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
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
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

/** 读取 body 后解析 JSON，避免 response.json() 失败时无法区分空响应 / HTML 网关页 */
export async function parseResponseBodyAsJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text.trim()) {
    throw new ApiError(`服务器返回空响应（HTTP ${response.status}）`, response.status);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    const preview = text.slice(0, 160).replace(/\s+/g, " ");
    throw new ApiError(
      `响应不是合法 JSON（HTTP ${response.status}）: ${preview}${text.length > 160 ? "…" : ""}`,
      response.status
    );
  }
}

async function parseJsonApiResponse<T>(response: Response): Promise<ApiResponse<T>> {
  return parseResponseBodyAsJson<ApiResponse<T>>(response);
}

function throwIfHttpOrBusinessError<T>(
  response: Response,
  data: ApiResponse<T>
): void {
  if (!response.ok) {
    const detail = (data as { detail?: unknown }).detail;
    const detailStr =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0] && typeof (detail[0] as { msg?: string }).msg === "string"
          ? (detail as { msg: string }[]).map((x) => x.msg).join("; ")
          : undefined;
    throw new ApiError(
      (data as { message?: string }).message || detailStr || `请求失败: ${response.status}`,
      response.status,
      data
    );
  }

  if (!data.success) {
    throw new ApiError(data.message || "操作失败", response.status, data);
  }
}

function rethrowAsApiError(error: unknown): never {
  if (error instanceof ApiError) {
    throw error;
  }
  if (error instanceof Error) {
    if (error.name === "AbortError") {
      throw new ApiError("请求超时", 408);
    }
    throw new ApiError(`网络错误: ${error.message}`, 0, error);
  }
  throw new ApiError("未知错误", 0, error);
}

async function sendRepairRequest<T>(
  endpoint: string,
  fetchOptions: RequestConfig,
  withJsonContentType: boolean
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const baseHeaders = withJsonContentType
    ? { "Content-Type": "application/json" }
    : {};
  const mergedHeaders = {
    ...baseHeaders,
    ...(fetchOptions.headers as Record<string, string> | undefined),
  };

  try {
    const response = await fetchWithTimeout(url, {
      ...fetchOptions,
      headers: mergedHeaders,
    });
    const data = await parseJsonApiResponse<T>(response);
    throwIfHttpOrBusinessError(response, data);
    return data.data;
  } catch (error) {
    rethrowAsApiError(error);
  }
}

async function request<T = any>(
  endpoint: string,
  options: RequestConfig = {}
): Promise<T> {
  return sendRepairRequest<T>(endpoint, options, true);
}

async function uploadRequest<T = any>(
  endpoint: string,
  formData: FormData,
  options: RequestConfig = {}
): Promise<T> {
  return sendRepairRequest<T>(
    endpoint,
    { method: "POST", body: formData, ...options },
    false
  );
}

export const http = {
  get: <T = any>(endpoint: string, options?: RequestConfig) =>
    request<T>(endpoint, { method: "GET", ...options }),

  post: <T = any>(endpoint: string, data?: any, options?: RequestConfig) =>
    request<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
      ...options,
    }),

  put: <T = any>(endpoint: string, data?: any, options?: RequestConfig) =>
    request<T>(endpoint, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
      ...options,
    }),

  delete: <T = any>(endpoint: string, options?: RequestConfig) =>
    request<T>(endpoint, { method: "DELETE", ...options }),

  upload: <T = any>(endpoint: string, formData: FormData, options?: RequestConfig) =>
    uploadRequest<T>(endpoint, formData, options),
};

export default http;
