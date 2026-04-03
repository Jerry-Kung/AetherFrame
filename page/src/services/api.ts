/**
 * API基础服务
 */

import type { ApiResponse } from "@/types/repair";

// API基础配置
const API_BASE_URL = "/api/repair";
const DEFAULT_TIMEOUT = 30000; // 30秒

// API错误类
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

// 请求配置
interface RequestConfig extends RequestInit {
  timeout?: number;
}

// 带超时的fetch
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

// 统一请求处理
async function request<T = any>(
  endpoint: string,
  options: RequestConfig = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  try {
    const response = await fetchWithTimeout(url, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    // 解析响应
    let data: ApiResponse<T>;
    try {
      data = await response.json();
    } catch (e) {
      throw new ApiError("响应解析失败", response.status);
    }

    // 检查HTTP状态（FastAPI HTTPException 为 { detail: string | array }）
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

    // 检查业务状态
    if (!data.success) {
      throw new ApiError(data.message || "操作失败", response.status, data);
    }

    return data.data;
  } catch (error) {
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
}

// 文件上传请求（不设置Content-Type，让浏览器自动设置）
async function uploadRequest<T = any>(
  endpoint: string,
  formData: FormData,
  options: RequestConfig = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      body: formData,
      ...options,
    });

    let data: ApiResponse<T>;
    try {
      data = await response.json();
    } catch (e) {
      throw new ApiError("响应解析失败", response.status);
    }

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

    return data.data;
  } catch (error) {
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
}

// 导出HTTP方法
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
