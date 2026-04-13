/**
 * 素材加工模块 /api/material
 */
import type { ApiCharacterDetail, ApiCharacterSummary } from "@/types/material";
import { ApiError, parseResponseBodyAsJson } from "@/services/api";

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
  return parseResponseBodyAsJson<ApiEnvelope<T>>(response);
}

function assertValidCharacterId(characterId: string, action: string): void {
  const id = String(characterId ?? "").trim();
  if (!id || id === "undefined" || id === "null") {
    throw new ApiError(`角色ID无效，无法${action}`, 400);
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

/** 上传裁剪后的角色头像（写入独立 avatar 目录，与官方/同人参考图分离） */
export async function uploadCharacterAvatar(
  characterId: string,
  file: File
): Promise<ApiCharacterDetail> {
  assertValidCharacterId(characterId, "上传角色头像");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/avatar`;
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetchWithTimeout(url, { method: "POST", body: form });
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

export async function putSettingText(
  characterId: string,
  settingText: string,
  clearSettingSource = false
): Promise<ApiCharacterDetail> {
  assertValidCharacterId(characterId, "保存角色设定");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/setting`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        setting_text: settingText,
        clear_setting_source: clearSettingSource,
      }),
    });
    const data = await parseJson<ApiCharacterDetail>(response);
    throwIfError(response, data);
    return data.data as ApiCharacterDetail;
  } catch (e) {
    rethrow(e);
  }
}

export async function putSettingFile(characterId: string, file: File): Promise<ApiCharacterDetail> {
  assertValidCharacterId(characterId, "上传角色设定文件");
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
  assertValidCharacterId(characterId, "上传参考图");
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
  assertValidCharacterId(characterId, "删除参考图");
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
  assertValidCharacterId(characterId, "更新参考图标签");
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

export interface CharaProfileStartResult {
  task_id: string;
  status: string;
}

export interface CharaProfileStatusResult {
  task_id: string;
  character_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  error_message: string | null;
  current_step: string | null;
  selected_fanart_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface CreationAdviceStartResult {
  task_id: string;
  status: string;
}

export interface CreationAdviceSeedDraft {
  character_specific: string[];
  general: string[];
}

export interface CreationAdviceStatusResult {
  task_id: string;
  character_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  error_message: string | null;
  current_step: string | null;
  created_at: string;
  updated_at: string;
  seed_draft: CreationAdviceSeedDraft | null;
}

export async function startCharaProfileTask(
  characterId: string,
  body: { selected_fanart_ids: string[] }
): Promise<CharaProfileStartResult> {
  assertValidCharacterId(characterId, "启动角色小档案任务");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/chara-profile/start`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      timeout: 60000,
    });
    const data = await parseJson<CharaProfileStartResult>(response);
    throwIfError(response, data);
    return data.data as CharaProfileStartResult;
  } catch (e) {
    rethrow(e);
  }
}

export async function getCharaProfileStatus(
  characterId: string
): Promise<CharaProfileStatusResult> {
  assertValidCharacterId(characterId, "查询角色小档案任务状态");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/chara-profile/status`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "GET",
      timeout: 20000,
    });
    const data = await parseJson<CharaProfileStatusResult>(response);
    throwIfError(response, data);
    return data.data as CharaProfileStatusResult;
  } catch (e) {
    rethrow(e);
  }
}

export async function startCreationAdviceTask(
  characterId: string
): Promise<CreationAdviceStartResult> {
  assertValidCharacterId(characterId, "启动生成创作建议任务");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/creation-advice/start`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      timeout: 120000,
    });
    const data = await parseJson<CreationAdviceStartResult>(response);
    throwIfError(response, data);
    return data.data as CreationAdviceStartResult;
  } catch (e) {
    rethrow(e);
  }
}

export async function getCreationAdviceStatus(
  characterId: string
): Promise<CreationAdviceStatusResult> {
  assertValidCharacterId(characterId, "查询生成创作建议任务状态");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/creation-advice/status`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "GET",
      timeout: 20000,
    });
    const data = await parseJson<CreationAdviceStatusResult>(response);
    throwIfError(response, data);
    return data.data as CreationAdviceStatusResult;
  } catch (e) {
    rethrow(e);
  }
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
  assertValidCharacterId(characterId, "启动标准照任务");
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
  assertValidCharacterId(characterId, "重试标准照任务");
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
): Promise<StandardPhotoStatusResult | null> {
  assertValidCharacterId(characterId, "查询标准照任务状态");
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/standard-photo/status`;
  try {
    const response = await fetchWithTimeout(url, { method: "GET" });
    const data = await parseJson<StandardPhotoStatusResult | null>(response);
    throwIfError(response, data);
    return data.data ?? null;
  } catch (e) {
    rethrow(e);
  }
}

export async function selectStandardPhotoResult(
  characterId: string,
  body: { selected_result_filename?: string; selected_result_index?: number }
): Promise<ApiCharacterDetail> {
  assertValidCharacterId(characterId, "保存标准照结果");
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
  assertValidCharacterId(characterId, "删除标准参考照");
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

export type PatchCharacterBioBody = {
  chara_profile?: string;
  creative_advice?: string;
  official_seed_prompts?: Record<string, unknown>;
};

/** 合并更新角色 bio（chara_profile / creative_advice / official_seed_prompts 至少一项） */
export async function patchCharacterBio(
  characterId: string,
  body: PatchCharacterBioBody
): Promise<ApiCharacterDetail> {
  assertValidCharacterId(characterId, "更新角色档案");
  const payload: Record<string, unknown> = {};
  if (body.chara_profile !== undefined) payload.chara_profile = body.chara_profile;
  if (body.creative_advice !== undefined) payload.creative_advice = body.creative_advice;
  if (body.official_seed_prompts !== undefined) {
    payload.official_seed_prompts = body.official_seed_prompts;
  }
  if (Object.keys(payload).length === 0) {
    throw new ApiError("至少需要一项 bio 更新字段", 400);
  }
  const url = `${API_BASE}/characters/${encodeURIComponent(characterId)}/bio`;
  try {
    const response = await fetchWithTimeout(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
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
  return patchCharacterBio(characterId, { chara_profile: charaProfile });
}

/** 保存角色创作建议 */
export async function saveCreativeAdvice(
  characterId: string,
  creativeAdvice: string
): Promise<ApiCharacterDetail> {
  return patchCharacterBio(characterId, { creative_advice: creativeAdvice });
}
