/**
 * 单个任务详情Hook
 */

import { useState, useCallback, useEffect, useRef } from "react";
import repairApi from "@/services/repairApi";
import type { RepairTask, TaskStatus } from "@/types/repair";
import { backendToFrontendTask, frontendToBackendUpdate } from "@/types/repair";

const POLLING_INTERVAL = 15_000; // 15 秒轮询一次（LLM 耗时长，无需高频请求）

export function useRepairTask(taskId: string | null) {
  const [task, setTask] = useState<RepairTask | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const taskIdRef = useRef(taskId);
  taskIdRef.current = taskId;

  const startPollingRef = useRef<() => void>(() => {});

  // 清除轮询
  const clearPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const runPollingTick = useCallback(async () => {
    const id = taskIdRef.current;
    if (!id) return;
    try {
      const backendTask = await repairApi.getTaskStatus(id);
      const frontendTask = backendToFrontendTask(backendTask);
      setTask(frontendTask);

      if (frontendTask.status !== "processing") {
        clearPolling();
        const full = await repairApi.getTask(id);
        setTask(backendToFrontendTask(full));
      }
    } catch (err) {
      console.error("轮询失败:", err);
    }
  }, [clearPolling]);

  const startPolling = useCallback(() => {
    clearPolling();
    void runPollingTick();
    pollingRef.current = setInterval(() => {
      void runPollingTick();
    }, POLLING_INTERVAL);
  }, [clearPolling, runPollingTick]);

  startPollingRef.current = startPolling;

  const maybeStartPolling = useCallback(
    (status: TaskStatus) => {
      if (status === "processing") {
        startPollingRef.current();
      } else {
        clearPolling();
      }
    },
    [clearPolling]
  );

  // 获取任务详情
  const fetchTask = useCallback(async () => {
    const id = taskIdRef.current;
    if (!id) return;

    setLoading(true);
    setError(null);
    try {
      const backendTask = await repairApi.getTask(id);
      const frontendTask = backendToFrontendTask(backendTask);
      setTask(frontendTask);
      maybeStartPolling(frontendTask.status);
    } catch (err) {
      const message = err instanceof Error ? err.message : "获取任务详情失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [maybeStartPolling]);

  // 更新任务
  const updateTask = useCallback(
    async (data: Partial<{ name?: string; prompt?: string; outputCount?: number }>) => {
      const id = taskIdRef.current;
      if (!id) return;

      setError(null);
      try {
        const backendData = frontendToBackendUpdate(data);
        const backendTask = await repairApi.updateTask(id, backendData);
        const frontendTask = backendToFrontendTask(backendTask);
        setTask(frontendTask);
        return frontendTask;
      } catch (err) {
        const message = err instanceof Error ? err.message : "更新任务失败";
        setError(message);
        throw err;
      }
    },
    []
  );

  // 上传主图
  const uploadMainImage = useCallback(
    async (file: File) => {
      const id = taskIdRef.current;
      if (!id) return;

      setIsUploading(true);
      setUploadProgress(0);
      setError(null);

      try {
        const response = await repairApi.uploadMainImage(id, file);
        setUploadProgress(100);
        await fetchTask();
        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : "上传主图失败";
        setError(message);
        throw err;
      } finally {
        setIsUploading(false);
        setUploadProgress(0);
      }
    },
    [fetchTask]
  );

  // 上传参考图
  const uploadReferenceImages = useCallback(
    async (files: File[]) => {
      const id = taskIdRef.current;
      if (!id) return;

      setIsUploading(true);
      setUploadProgress(0);
      setError(null);

      try {
        const response = await repairApi.uploadReferenceImages(id, files);
        setUploadProgress(100);
        await fetchTask();
        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : "上传参考图失败";
        setError(message);
        throw err;
      } finally {
        setIsUploading(false);
        setUploadProgress(0);
      }
    },
    [fetchTask]
  );

  // 删除主图
  const deleteMainImage = useCallback(async () => {
    const id = taskIdRef.current;
    if (!id) return;

    setError(null);
    try {
      await repairApi.deleteMainImage(id);
      await fetchTask();
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除主图失败";
      setError(message);
      throw err;
    }
  }, [fetchTask]);

  // 删除参考图
  const deleteReferenceImage = useCallback(
    async (filename: string) => {
      const id = taskIdRef.current;
      if (!id) return;

      setError(null);
      try {
        await repairApi.deleteReferenceImage(id, filename);
        await fetchTask();
      } catch (err) {
        const message = err instanceof Error ? err.message : "删除参考图失败";
        setError(message);
        throw err;
      }
    },
    [fetchTask]
  );

  // 启动修补任务
  const startRepair = useCallback(
    async (useReferenceImages: boolean = false) => {
      const id = taskIdRef.current;
      if (!id) return;

      setError(null);
      try {
        const response = await repairApi.startRepair(id, useReferenceImages);
        // 先开轮询再拉详情：避免首包 GET 超时/阻塞时轮询从未启动
        if (response.status === "processing") {
          startPollingRef.current();
        }
        try {
          await fetchTask();
        } catch (fetchErr) {
          console.warn("启动修补后刷新任务详情失败（轮询将继续）:", fetchErr);
        }
        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : "启动修补任务失败";
        setError(message);
        throw err;
      }
    },
    [fetchTask]
  );

  // 初始化
  useEffect(() => {
    if (taskId) {
      void fetchTask();
    } else {
      setTask(null);
      clearPolling();
    }

    return () => {
      clearPolling();
    };
  }, [taskId, fetchTask, clearPolling]);

  return {
    task,
    loading,
    error,
    isUploading,
    uploadProgress,
    fetchTask,
    updateTask,
    uploadMainImage,
    uploadReferenceImages,
    deleteMainImage,
    deleteReferenceImage,
    startRepair,
  };
}
