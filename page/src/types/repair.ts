/**
 * 修补模块类型定义
 */

// 任务状态类型
export type TaskStatus = "pending" | "processing" | "completed" | "failed";

// 后端任务数据（snake_case）
export interface BackendTask {
  id: string;
  name: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  main_image_filename: string | null;
  prompt: string | null;
  reference_image_filenames: string[];
  output_count: number;
  result_image_filenames: string[];
  error_message: string | null;
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
}

// 任务更新请求
export interface TaskUpdateRequest {
  name?: string;
  prompt?: string;
  output_count?: number;
}

// Prompt模板类型
export interface PromptTemplate {
  id: string;
  label: string;
  prompt: string;
  is_builtin: boolean;
  created_at: string;
}

// 模板创建请求
export interface PromptTemplateCreateRequest {
  label: string;
  prompt: string;
}

// 模板更新请求
export interface PromptTemplateUpdateRequest {
  label?: string;
  prompt?: string;
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
  filename: string;
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

// 后端任务 -> 前端任务
export function backendToFrontendTask(backendTask: BackendTask): RepairTask {
  return {
    id: backendTask.id,
    name: backendTask.name,
    status: backendTask.status,
    createdAt: backendTask.created_at,
    updatedAt: backendTask.updated_at,
    mainImage: getImageUrl(backendTask.id, "main", backendTask.main_image_filename),
    prompt: backendTask.prompt || "",
    referenceImages: backendTask.reference_image_filenames.map((filename) =>
      getImageUrl(backendTask.id, "reference", filename)
    ),
    outputCount: (backendTask.output_count as 1 | 2 | 4) || 1,
    results: backendTask.result_image_filenames.map((filename) =>
      getImageUrl(backendTask.id, "result", filename)
    ),
    errorMessage: backendTask.error_message,
  };
}

// 前端任务更新 -> 后端请求格式
export function frontendToBackendUpdate(data: {
  name?: string;
  prompt?: string;
  outputCount?: number;
}): TaskUpdateRequest {
  const result: TaskUpdateRequest = {};
  if (data.name !== undefined) result.name = data.name;
  if (data.prompt !== undefined) result.prompt = data.prompt;
  if (data.outputCount !== undefined) result.output_count = data.outputCount;
  return result;
}

// 编辑器状态类型（与现有组件兼容）
export interface EditorState {
  mainImage: string;
  prompt: string;
  referenceImages: string[];
  outputCount: 1 | 2 | 4;
}
