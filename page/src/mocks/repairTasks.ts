/**
 * 修补模块本地 mock 数据（开发/演示用；线上列表来自 API）
 */

import type { AspectRatio, RepairTask } from "@/types/repair";

export type { AspectRatio, RepairTask };

export const mockRepairTasks: RepairTask[] = [
  {
    id: "mock-001",
    name: "示例修补任务",
    status: "pending",
    createdAt: "2026-04-01",
    updatedAt: "2026-04-01",
    mainImage: "",
    prompt: "",
    referenceImages: [],
    outputCount: 1,
    aspectRatio: "16:9",
    results: [],
    errorMessage: null,
  },
  {
    id: "mock-002",
    name: "示例修补任务 2",
    status: "completed",
    createdAt: "2026-04-02",
    updatedAt: "2026-04-02",
    mainImage: "",
    prompt: "修补示例",
    referenceImages: [],
    outputCount: 2,
    aspectRatio: "16:9",
    results: [],
    errorMessage: null,
  },
];
