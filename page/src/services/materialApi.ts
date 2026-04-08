/**
 * 素材加工模块 /api/material
 */
import type { ApiCharacterDetail, ApiCharacterSummary } from "@/types/material";
import { ApiError } from "@/services/api";

const API_BASE = "/api/material";
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

function throwIfError<T>(response: Response, data: ApiEnvelope<T>): asserts data is ApiEnvelope<T> & { success: true; data: T } {
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

export interface CharacterListResult {
  characters: ApiCharacterSummary[];
  total: number;
  skip: number;
  limit: number;
}

export async function listCharacters(
  skip = 0,
  limit = 50
): Promise<CharacterListResult> {
  const url = `${API_BASE}/characters?skip=${skip}&limit=${limit}`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<CharacterListResult>(response);
    throwIfError(response, data);
    return data.data as CharacterListResult;
  } catch (e) {
    rethrow(e);
  }
}

export async function getCharacter(id: string): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(id)}`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

export async function createCharacter(body: {
  name: string;
  display_name?: string | null;
}): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

export async function patchCharacter(
  id: string,
  body: { name?: string; display_name?: string | null }
): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(id)}`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

export async function deleteCharacter(id: string): Promise<void> {
  const url = `${API_BASE}/characters/${encodeURIComponent(id)}`;
  try {
    const response = await fetchWithTimeout(url, { method: "DELETE" });
    const data = await parseJson(response);
    throwIfError(response, data);
  } catch (e) {
    rethrow(e);
  }
}

export async function putSettingText(characterId: string, settingText: string): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/setting`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setting_text: settingText }),
    });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

export async function putSettingFile(characterId: string, file: File): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/setting`;
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetchWithTimeout(url, { method: "PUT", body: form });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

export interface RawImageUploaded {
  id: string;
  url: string;
  type: string;
  tags: string[];
}

export interface RawImagesUploadResult {
  uploaded: RawImageUploaded[];
  failed: { original_filename: string; error: string }[];
  total: number;
  character_id: string;
}

export async function postRawImages(
  characterId: string,
  files: File[],
  tagsPerFile?: string[][],
  typesPerFile?: string[]
): Promise<RawImagesUploadResult> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/raw-images`;
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  if (tagsPerFile && tagsPerFile.length > 0) {
    form.append("tags", JSON.stringify(tagsPerFile));
  }
  if (typesPerFile && typesPerFile.length > 0) {
    form.append("types", JSON.stringify(typesPerFile));
  }
  try {
    const response = await fetchWithTimeout(url, { method: "POST", body: form });
    const data = await parseJson<RawImagesUploadResult>(response);
    throwIfError(response, data);
    return data.data as RawImagesUploadResult;
  } catch (e) {
    rethrow(e);
  }
}

export async function deleteRawImage(characterId: string, imageId: string): Promise<void> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/raw-images/${encodeURIComponent(imageId)}`;
  try {
    const response = await fetchWithTimeout(url, { method: "DELETE" });
    const data = await parseJson(response);
    throwIfError(response, data);
  } catch (e) {
    rethrow(e);
  }
}

export async function patchRawImageTags(
  characterId: string,
  imageId: string,
  tags: string[]
): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/raw-images/${encodeURIComponent(imageId)}`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

export type StandardShotType =
  | "full_front"
  | "full_side"
  | "half_front"
  | "half_side"
  | "face_close";
export type StandardAspectRatio = "16:9" | "1:1" | "9:16";

export interface StandardPhotoStartResult {
  task_id: string;
  status: string;
  shot_type: StandardShotType;
  aspect_ratio: StandardAspectRatio;
  output_count: number;
}

export interface StandardPhotoStatusResult {
  task_id: string;
  character_id: string;
  shot_type: StandardShotType;
  aspect_ratio: StandardAspectRatio;
  output_count: number;
  status: "pending" | "processing" | "completed" | "failed";
  error_message: string | null;
  selected_raw_image_ids: string[];
  result_images: string[];
  created_at: string;
  updated_at: string;
}

export async function startStandardPhotoTask(
  characterId: string,
  body: {
    shot_type: StandardShotType;
    aspect_ratio: StandardAspectRatio;
    output_count: number;
    selected_raw_image_ids: string[];
  }
): Promise<StandardPhotoStartResult> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/standard-photo/start`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      timeout: 60000,
    });
    const data = await parseJson<StandardPhotoStartResult>(response);
    throwIfError(response, data);
    return data.data as StandardPhotoStartResult;
  } catch (e) {
    rethrow(e);
  }
}

export async function retryStandardPhotoTask(characterId: string): Promise<StandardPhotoStartResult> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/standard-photo/retry`;
  try {
    const response = await fetchWithTimeout(url, { method: "POST", timeout: 60000 });
    const data = await parseJson<StandardPhotoStartResult>(response);
    throwIfError(response, data);
    return data.data as StandardPhotoStartResult;
  } catch (e) {
    rethrow(e);
  }
}

export async function getStandardPhotoStatus(
  characterId: string
): Promise<StandardPhotoStatusResult> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/standard-photo/status`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<StandardPhotoStatusResult>(response);
    throwIfError(response, data);
    return data.data as StandardPhotoStatusResult;
  } catch (e) {
    rethrow(e);
  }
}

export async function selectStandardPhotoResult(
  characterId: string,
  body: { selected_result_filename?: string; selected_result_index?: number }
): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/standard-photo/select`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

/** 删除某一槽位的正式标准参考照（0–4，与加工任务标准照类型顺序一致） */
export async function deleteOfficialPhotoSlot(
  characterId: string,
  slotIndex: number
): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/standard-photo/slot/${slotIndex}`;
  try {
    const response = await fetchWithTimeout(url, { method: "DELETE" });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

/** 保存角色小档案 */
export async function saveCharaProfile(
  characterId: string,
  charaProfile: string
): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/bio`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chara_profile: charaProfile }),
    });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

/** 保存角色创作建议 */
export async function saveCreativeAdvice(
  characterId: string,
  creativeAdvice: string
): Promise<ApiCharacterDetail> {
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/bio`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ creative_advice: creativeAdvice }),
    });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}
