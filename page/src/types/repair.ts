/**
 * 修补模块类型定义
 */

// 任务状态类型
export type TaskStatus = "pending" | "processing" | "completed" | "failed";

/** 修补输出图片长宽比（与后端 aspect_ratio 字符串一致） */
export type AspectRatio = "16:9" | "4:3" | "1:1" | "3:4" | "9:16";

const ASPECT_RATIO_VALUES: readonly AspectRatio[] = ["16:9", "4:3", "1:1", "3:4", "9:16"];

export function normalizeAspectRatio(raw: unknown): AspectRatio {
  const s = String(raw ?? "").trim();
  return (ASPECT_RATIO_VALUES as readonly string[]).includes(s) ? (s as AspectRatio) : "16:9";
}

/** 后端图片字段（任务详情 GET /tasks/:id） */
export interface BackendImageInfo {
  filename: string;
  url: string;
}

/**
 * 后端任务 JSON：创建/列表/更新/状态 为简要结构；详情含图片列表。
 * 与 Pydantic TaskSimple / TaskDetail 的 model_dump 一致。
 */
export interface BackendTask {
  id: string;
  name: string;
  status: TaskStatus;
  prompt: string;
  output_count: number;
  /** 后端上线后返回；缺省时前端用 normalizeAspectRatio */
  aspect_ratio?: string | null;
  created_at: string;
  updated_at: string;
  has_main_image: boolean;
  reference_image_count: number;
  result_image_count: number;
  error_message?: string | null;
  main_image?: BackendImageInfo | null;
  reference_images?: BackendImageInfo[];
  result_images?: BackendImageInfo[];
}

// 前端任务数据（camelCase）
export interface RepairTask {
  id: string;
  name: string;
  status: TaskStatus;
  createdAt: string;
  updatedAt: string;
  mainImage: string;
  prompt: string;
  referenceImages: string[];
  outputCount: 1 | 2 | 4;
  aspectRatio: AspectRatio;
  results: string[];
  errorMessage: string | null;
}

// 任务列表响应
export interface TaskListResponse {
  tasks: BackendTask[];
  total: number;
  skip: number;
  limit: number;
}

// 任务创建请求
export interface TaskCreateRequest {
  name: string;
  prompt?: string;
  output_count?: number;
}

// 任务更新请求
export interface TaskUpdateRequest {
  name?: string;
  prompt?: string;
  output_count?: number;
  aspect_ratio?: string;
}

// Prompt 模板类型（与后端 PromptTemplateResponse 一致，字段名为 text）
export interface PromptTemplate {
  id: string;
  label: string;
  description: string;
  text: string;
  is_builtin: boolean;
  sort_order: number;
  created_at: string;
  /** 后端未上线时可选缺失，前端 enrich 会兜底为 [] */
  tags?: string[];
}

// 模板创建请求
export interface PromptTemplateCreateRequest {
  label: string;
  text: string;
  description?: string;
  tags?: string[];
}

// 模板更新请求
export interface PromptTemplateUpdateRequest {
  label?: string;
  text?: string;
  description?: string;
  tags?: string[];
}

/** 列表接口 data 包裹层 */
export interface PromptTemplateListData {
  templates: PromptTemplate[];
  total: number;
}

// 文件上传响应
export interface MainImageUploadResponse {
  filename: string;
  url: string;
  task_id: string;
}

export interface UploadedImageInfo {
  filename: string;
  url: string;
}

export interface FailedUploadInfo {
  /** 与后端 `FailedUploadInfo.original_filename` 一致 */
  original_filename: string;
  error: string;
}

export interface ReferenceImagesUploadResponse {
  uploaded: UploadedImageInfo[];
  failed: FailedUploadInfo[];
  total: number;
  task_id: string;
}

// 启动修补任务请求
export interface StartRepairRequest {
  use_reference_images: boolean;
}

// 启动修补任务响应
export interface StartRepairResponse {
  task_id: string;
  status: TaskStatus;
}

// 统一API响应
export interface ApiResponse<T = any> {
  success: boolean;
  data: T;
  message: string;
}

/**
 * 数据转换函数
 */

// 获取图片URL
export function getImageUrl(
  taskId: string,
  imageType: "main" | "reference" | "result",
  filename: string | null
): string {
  if (!filename) return "";
  return `/api/repair/tasks/${taskId}/images/${imageType}/${filename}`;
}

function normalizeOutputCount(n: unknown): 1 | 2 | 4 {
  const v = Number(n);
  if (v === 2 || v === 4) return v as 2 | 4;
  return 1;
}

const TASK_STATUSES: TaskStatus[] = ["pending", "processing", "completed", "failed"];

function normalizeStatus(s: unknown): TaskStatus {
  const x = String(s ?? "").trim().toLowerCase();
  return (TASK_STATUSES.includes(x as TaskStatus) ? x : "pending") as TaskStatus;
}

/**
 * 将后端 TaskSimple / TaskDetail（及历史仅含 *_filenames 的 payload）转为前端 RepairTask
 */
export function backendToFrontendTask(raw: unknown): RepairTask {
  const t = raw as Record<string, unknown>;
  const id = String(t.id ?? "");

  let mainImage = "";
  const mainObj = t.main_image;
  if (mainObj && typeof mainObj === "object") {
    const m = mainObj as { url?: string; filename?: string };
    mainImage = m.url ?? (m.filename ? getImageUrl(id, "main", m.filename) : "");
  }
  if (!mainImage && "main_image_filename" in t) {
    mainImage = getImageUrl(id, "main", t.main_image_filename as string | null);
  }

  let referenceImages: string[] = [];
  if (Array.isArray(t.reference_images)) {
    referenceImages = (t.reference_images as BackendImageInfo[])
      .map((r) => r.url || (r.filename ? getImageUrl(id, "reference", r.filename) : ""))
      .filter(Boolean);
  } else if (Array.isArray(t.reference_image_filenames)) {
    referenceImages = (t.reference_image_filenames as string[]).map((filename) =>
      getImageUrl(id, "reference", filename)
    );
  }

  let results: string[] = [];
  if (Array.isArray(t.result_images)) {
    results = (t.result_images as BackendImageInfo[])
      .map((r) => r.url || (r.filename ? getImageUrl(id, "result", r.filename) : ""))
      .filter(Boolean);
  } else if (Array.isArray(t.result_image_filenames)) {
    results = (t.result_image_filenames as string[]).map((filename) =>
      getImageUrl(id, "result", filename)
    );
  }

  return {
    id,
    name: String(t.name ?? ""),
    status: normalizeStatus(t.status),
    createdAt: t.created_at != null ? String(t.created_at) : "",
    updatedAt: t.updated_at != null ? String(t.updated_at) : "",
    mainImage,
    prompt: String(t.prompt ?? ""),
    referenceImages,
    outputCount: normalizeOutputCount(t.output_count),
    aspectRatio: normalizeAspectRatio(t.aspect_ratio),
    results,
    errorMessage: (t.error_message as string | null) ?? null,
  };
}

// 前端任务更新 -> 后端请求格式
export function frontendToBackendUpdate(data: {
  name?: string;
  prompt?: string;
  outputCount?: number;
  aspectRatio?: AspectRatio;
}): TaskUpdateRequest {
  const result: TaskUpdateRequest = {};
  if (data.name !== undefined) result.name = data.name;
  if (data.prompt !== undefined) result.prompt = data.prompt;
  if (data.outputCount !== undefined) result.output_count = data.outputCount;
  if (data.aspectRatio !== undefined) result.aspect_ratio = data.aspectRatio;
  return result;
}

// 编辑器状态类型（与现有组件兼容）
export interface EditorState {
  mainImage: string;
  prompt: string;
  referenceImages: string[];
  outputCount: 1 | 2 | 4;
  aspectRatio: AspectRatio;
}
