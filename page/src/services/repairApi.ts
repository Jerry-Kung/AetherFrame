/**
 * 修补模块API服务
 */

import http from "./api";
import type {
  BackendTask,
  TaskListResponse,
  TaskCreateRequest,
  TaskUpdateRequest,
  PromptTemplate,
  PromptTemplateCreateRequest,
  PromptTemplateUpdateRequest,
  MainImageUploadResponse,
  ReferenceImagesUploadResponse,
  StartRepairRequest,
  StartRepairResponse,
} from "@/types/repair";

/**
 * 任务管理API
 */

// 获取任务列表
export async function getTasks(params?: {
  skip?: number;
  limit?: number;
  order_by?: string;
  order_dir?: string;
  status?: string;
}): Promise<TaskListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
  if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
  if (params?.order_by) searchParams.set("order_by", params.order_by);
  if (params?.order_dir) searchParams.set("order_dir", params.order_dir);
  if (params?.status) searchParams.set("status", params.status);

  const queryString = searchParams.toString();
  const endpoint = queryString ? `/tasks?${queryString}` : "/tasks";

  return http.get<TaskListResponse>(endpoint);
}

// 创建任务
export async function createTask(data: TaskCreateRequest): Promise<BackendTask> {
  return http.post<BackendTask>("/tasks", data);
}

// 获取任务详情
export async function getTask(taskId: string): Promise<BackendTask> {
  return http.get<BackendTask>(`/tasks/${taskId}`);
}

// 更新任务
export async function updateTask(
  taskId: string,
  data: TaskUpdateRequest
): Promise<BackendTask> {
  return http.put<BackendTask>(`/tasks/${taskId}`, data);
}

// 删除任务
export async function deleteTask(taskId: string): Promise<void> {
  return http.delete<void>(`/tasks/${taskId}`);
}

/**
 * 文件上传API
 */

// 上传主图
export async function uploadMainImage(
  taskId: string,
  file: File
): Promise<MainImageUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return http.upload<MainImageUploadResponse>(`/tasks/${taskId}/main-image`, formData);
}

// 上传参考图
export async function uploadReferenceImages(
  taskId: string,
  files: File[]
): Promise<ReferenceImagesUploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return http.upload<ReferenceImagesUploadResponse>(
    `/tasks/${taskId}/reference-images`,
    formData
  );
}

// 删除主图
export async function deleteMainImage(taskId: string): Promise<void> {
  return http.delete<void>(`/tasks/${taskId}/main-image`);
}

// 删除参考图
export async function deleteReferenceImage(
  taskId: string,
  filename: string
): Promise<void> {
  return http.delete<void>(`/tasks/${taskId}/reference-images/${encodeURIComponent(filename)}`);
}

// 获取图片URL（从类型导出）
export { getImageUrl } from "@/types/repair";

/**
 * Prompt模板API
 */

// 获取模板列表
export async function getTemplates(template_type?: "builtin" | "custom"): Promise<PromptTemplate[]> {
  const endpoint = template_type
    ? `/templates?template_type=${template_type}`
    : "/templates";
  return http.get<PromptTemplate[]>(endpoint);
}

// 创建模板
export async function createTemplate(
  data: PromptTemplateCreateRequest
): Promise<PromptTemplate> {
  return http.post<PromptTemplate>("/templates", data);
}

// 获取模板详情
export async function getTemplate(templateId: string): Promise<PromptTemplate> {
  return http.get<PromptTemplate>(`/templates/${templateId}`);
}

// 更新模板
export async function updateTemplate(
  templateId: string,
  data: PromptTemplateUpdateRequest
): Promise<PromptTemplate> {
  return http.put<PromptTemplate>(`/templates/${templateId}`, data);
}

// 删除模板
export async function deleteTemplate(templateId: string): Promise<void> {
  return http.delete<void>(`/templates/${templateId}`);
}

/**
 * 任务执行API
 */

// 启动修补任务
export async function startRepair(
  taskId: string,
  useReferenceImages: boolean
): Promise<StartRepairResponse> {
  const data: StartRepairRequest = {
    use_reference_images: useReferenceImages,
  };
  return http.post<StartRepairResponse>(`/tasks/${taskId}/start`, data);
}

// 获取任务状态
export async function getTaskStatus(taskId: string): Promise<BackendTask> {
  return http.get<BackendTask>(`/tasks/${taskId}/status`);
}

export default {
  getTasks,
  createTask,
  getTask,
  updateTask,
  deleteTask,
  uploadMainImage,
  uploadReferenceImages,
  deleteMainImage,
  deleteReferenceImage,
  getImageUrl,
  getTemplates,
  createTemplate,
  getTemplate,
  updateTemplate,
  deleteTemplate,
  startRepair,
  getTaskStatus,
};
