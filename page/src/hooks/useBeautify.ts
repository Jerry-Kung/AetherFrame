import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/services/api";
import * as beautifyApi from "@/services/beautifyApi";
import type { BeautifyStatus } from "@/services/beautifyApi";

const POLL_INTERVAL_MS = 4000;

export type BeautifyUiState = "idle" | "running" | "done" | "failed";

export interface BeautifyImageFields {
  beautifyTaskId?: string | null;
  beautifyStatus?: BeautifyStatus | null;
  beautifiedUrl?: string | null;
}

export type BeautifyPatch = BeautifyImageFields;

export function useBeautify(opts: {
  image: BeautifyImageFields;
  source: { kind: "quick_create" | "repair"; taskId: string };
  sourceImagePath: string;
  onChanged?: (patch: BeautifyPatch) => void;
}) {
  const { image, source, sourceImagePath, onChanged } = opts;
  const onChangedRef = useRef(onChanged);
  onChangedRef.current = onChanged;

  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const pollLockRef = useRef(false);

  const taskId = image.beautifyTaskId ?? null;
  const status = image.beautifyStatus ?? null;

  const uiState: BeautifyUiState = (() => {
    if (status === "completed" && image.beautifiedUrl) return "done";
    if (status === "failed") return "failed";
    if (busy || status === "pending" || status === "processing") return "running";
    return "idle";
  })();

  const emit = useCallback((patch: BeautifyPatch) => {
    onChangedRef.current?.(patch);
  }, []);

  const pollOnce = useCallback(async (pollTaskId: string) => {
    if (pollLockRef.current) return;
    pollLockRef.current = true;
    try {
      const data = await beautifyApi.getBeautifyTaskStatus(pollTaskId);
      setCurrentStep(data.current_step ?? null);
      if (data.status === "pending" || data.status === "processing") {
        emit({
          beautifyTaskId: data.task_id,
          beautifyStatus: data.status,
        });
        return;
      }
      if (data.status === "completed") {
        setErrorMessage(null);
        emit({
          beautifyTaskId: data.task_id,
          beautifyStatus: "completed",
          beautifiedUrl: data.beautified_url ?? null,
        });
        return;
      }
      if (data.status === "failed") {
        const msg = data.error_message?.trim() || "美化失败";
        setErrorMessage(msg);
        emit({
          beautifyTaskId: data.task_id,
          beautifyStatus: "failed",
          beautifiedUrl: null,
        });
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "获取美化状态失败";
      setErrorMessage(msg);
    } finally {
      pollLockRef.current = false;
    }
  }, [emit]);

  useEffect(() => {
    if (!taskId || (status !== "pending" && status !== "processing")) return;
    void pollOnce(taskId);
    const id = window.setInterval(() => {
      void pollOnce(taskId);
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [taskId, status, pollOnce]);

  const start = useCallback(async () => {
    const tid = String(source.taskId ?? "").trim();
    const path = String(sourceImagePath ?? "").trim();
    if (!tid || !path) {
      setErrorMessage("无法启动美化：缺少任务或图片路径");
      return;
    }
    setBusy(true);
    setErrorMessage(null);
    setCurrentStep(null);
    try {
      const data = await beautifyApi.startBeautify({
        source_kind: source.kind,
        source_task_id: tid,
        source_image_path: path,
      });
      emit({
        beautifyTaskId: data.task_id,
        beautifyStatus: data.status,
        beautifiedUrl: null,
      });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "启动美化失败";
      setErrorMessage(msg);
    } finally {
      setBusy(false);
    }
  }, [emit, source.kind, source.taskId, sourceImagePath]);

  const del = useCallback(async () => {
    const id = image.beautifyTaskId;
    if (!id) {
      emit({
        beautifyTaskId: null,
        beautifyStatus: null,
        beautifiedUrl: null,
      });
      return;
    }
    setBusy(true);
    setErrorMessage(null);
    try {
      await beautifyApi.deleteBeautifyTask(id);
      emit({
        beautifyTaskId: null,
        beautifyStatus: null,
        beautifiedUrl: null,
      });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "删除美化失败";
      setErrorMessage(msg);
    } finally {
      setBusy(false);
    }
  }, [emit, image.beautifyTaskId]);

  const retry = useCallback(async () => {
    await del();
    await start();
  }, [del, start]);

  return {
    state: uiState,
    start,
    del,
    retry,
    errorMessage,
    currentStep,
    busy,
  };
}
