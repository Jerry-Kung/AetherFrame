export type VideoStatus =
  | "draft" | "pending" | "uploading" | "generating" | "downloading"
  | "completed" | "failed";

export type PromptJobStatus = "pending" | "running" | "completed" | "failed";

export type ImageRole = "first_frame" | "reference_image";

export interface VideoTask {
  task_id: string;
  source_kind: string;
  status: VideoStatus;
  image_role: ImageRole;
  duration: number;
  generate_audio: boolean;
  ratio: string;
  ref_prompt_text?: string | null;
  video_prompt_text?: string | null;
  prompt_mode?: string | null;
  prompt_job_status?: PromptJobStatus | null;
  prompt_job_result?: string | null;
  prompt_job_error?: string | null;
  video_filename?: string | null;
  error_message?: string | null;
  recommended_ratio?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}
