/**
 * 任务列表Hook
 */

import { useState, useCallback, useEffect } from "react";
import repairApi from "@/services/repairApi";
import type { RepairTask } from "@/types/repair";
import { backendToFrontendTask } from "@/types/repair";

export function useRepairTasks() {
  const [tasks, setTasks] = useState<RepairTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 获取任务列表
  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await repairApi.getTasks({
        order_by: "created_at",
        order_dir: "desc",
        limit: 100,
      });
      const rows = response.tasks ?? [];
      const frontendTasks = rows.map((row) => backendToFrontendTask(row));
      setTasks(frontendTasks);
    } catch (err) {
      const message = err instanceof Error ? err.message : "获取任务列表失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  // 创建任务
  const createTask = useCallback(async (name: string): Promise<RepairTask> => {
    setError(null);
    try {
      const backendTask = await repairApi.createTask({
        name,
        prompt: "",
        output_count: 1,
      });
      const frontendTask = backendToFrontendTask(backendTask);
      setTasks((prev) => [frontendTask, ...prev]);
      return frontendTask;
    } catch (err) {
      const message = err instanceof Error ? err.message : "创建任务失败";
      setError(message);
      throw err;
    }
  }, []);

  // 删除任务
  const deleteTask = useCallback(async (taskId: string) => {
    setError(null);
    try {
      await repairApi.deleteTask(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (err) {
      const message = err instanceof Error ? err.message : "删除任务失败";
      setError(message);
      throw err;
    }
  }, []);

  // 刷新单个任务
  const refreshTask = useCallback(async (taskId: string) => {
    try {
      const backendTask = await repairApi.getTask(taskId);
      const frontendTask = backendToFrontendTask(backendTask);
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? frontendTask : t))
      );
      return frontendTask;
    } catch (err) {
      const message = err instanceof Error ? err.message : "刷新任务失败";
      setError(message);
      throw err;
    }
  }, []);

  /** 用详情/轮询得到的快照更新左侧列表中的同一条任务（不发请求） */
  const applyTaskSnapshot = useCallback((task: RepairTask) => {
    setTasks((prev) => {
      const i = prev.findIndex((t) => t.id === task.id);
      if (i < 0) return prev;
      const next = [...prev];
      next[i] = task;
      return next;
    });
  }, []);

  // 初始化时获取任务列表
  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  return {
    tasks,
    loading,
    error,
    fetchTasks,
    createTask,
    deleteTask,
    refreshTask,
    applyTaskSnapshot,
  };
}
