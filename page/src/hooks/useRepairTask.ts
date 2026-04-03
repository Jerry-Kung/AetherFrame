/**
 * 单个任务详情Hook
 */

import { useState, useCallback, useEffect, useRef } from "react";
import repairApi from "@/services/repairApi";
import type { RepairTask, BackendTask, EditorState, TaskStatus } from "@/types/repair";
import { backendToFrontendTask, frontendToBackendUpdate } from "@/types/repair";

const POLLING_INTERVAL = 2500; // 2.5秒轮询一次

export function useRepairTask(taskId: string | null) {
  const [task, setTask] = useState<RepairTask | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // 清除轮询
  const clearPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  // 获取任务详情
  const fetchTask = useCallback(async () => {
    if (!taskId) return;
    
    setLoading(true);
    setError(null);
    try {
      const backendTask = await repairApi.getTask(taskId);
      const frontendTask = backendToFrontendTask(backendTask);
      setTask(frontendTask);
      
      // 如果任务在处理中，启动轮询
      if (frontendTask.status === "processing") {
        startPolling();
      } else {
        clearPolling();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "获取任务详情失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [taskId, clearPolling]);

  // 启动轮询
  const startPolling = useCallback(() => {
    clearPolling();
    pollingRef.current = setInterval(async () => {
      if (!taskId) return;
      try {
        const backendTask = await repairApi.getTaskStatus(taskId);
        const frontendTask = backendToFrontendTask(backendTask);
        setTask(frontendTask);
        
        // 如果任务完成或失败，停止轮询
        if (frontendTask.status !== "processing") {
          clearPolling();
          // 完成后获取完整详情
          fetchTask();
        }
      } catch (err) {
        console.error("轮询失败:", err);
      }
    }, POLLING_INTERVAL);
  }, [taskId, clearPolling, fetchTask]);

  // 更新任务
  const updateTask = useCallback(async (data: Partial<{
    name?: string;
    prompt?: string;
    outputCount?: number;
  }>) => {
    if (!taskId) return;
    
    setError(null);
    try {
      const backendData = frontendToBackendUpdate(data);
      const backendTask = await repairApi.updateTask(taskId, backendData);
      const frontendTask = backendToFrontendTask(backendTask);
      setTask(frontendTask);
      return frontendTask;
    } catch (err) {
      const message = err instanceof Error ? err.message : "更新任务失败";
      setError(message);
      throw err;
    }
  }, [taskId]);

  // 上传主图
  const uploadMainImage = useCallback(async (file: File) => {
    if (!taskId) return;
    
    setIsUploading(true);
    setUploadProgress(0);
    setError(null);
    
    try {
      const response = await repairApi.uploadMainImage(taskId, file);
      setUploadProgress(100);
      // 刷新任务
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
  }, [taskId, fetchTask]);

  // 上传参考图
  const uploadReferenceImages = useCallback(async (files: File[]) => {
    if (!taskId) return;
    
    setIsUploading(true);
    setUploadProgress(0);
    setError(null);
    
    try {
      const response = await repairApi.uploadReferenceImages(taskId, files);
      setUploadProgress(100);
      // 刷新任务
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
  }, [taskId, fetchTask]);

  // 删除主图
  const deleteMainImage = useCallback(async () => {
    if (!taskId) return;
    
    setError(null);
    try {
      await repairApi.deleteMainImage(taskId);
      await fetchTask();
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除主图失败";
      setError(message);
      throw err;
    }
  }, [taskId, fetchTask]);

  // 删除参考图
  const deleteReferenceImage = useCallback(async (filename: string) => {
    if (!taskId) return;
    
    setError(null);
    try {
      await repairApi.deleteReferenceImage(taskId, filename);
      await fetchTask();
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除参考图失败";
      setError(message);
      throw err;
    }
  }, [taskId, fetchTask]);

  // 启动修补任务
  const startRepair = useCallback(async (useReferenceImages: boolean = false) => {
    if (!taskId) return;
    
    setError(null);
    try {
      const response = await repairApi.startRepair(taskId, useReferenceImages);
      // 启动后立即刷新并开始轮询
      await fetchTask();
      return response;
    } catch (err) {
      const message = err instanceof Error ? err.message : "启动修补任务失败";
      setError(message);
      throw err;
    }
  }, [taskId, fetchTask]);

  // 初始化
  useEffect(() => {
    if (taskId) {
      fetchTask();
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
