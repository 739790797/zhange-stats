import { useCallback, useState } from "react";

const STORAGE_KEY = "zhange.tarkov.tasks.mine";

export const TARKOV_TASK_PROGRESS_LABELS: Record<string, string> = {
  available: "进行中",
  locked: "缺少前置",
  complete: "已完成",
  failed: "已失败",
};

/** 表头筛选与默认排序共用这一顺序。 */
export const TARKOV_TASK_PROGRESS_FILTERS: { id: string; label: string }[] = [
  { id: "available", label: "进行中" },
  { id: "locked", label: "缺少前置" },
  { id: "complete", label: "已完成" },
  { id: "failed", label: "已失败" },
];

export function tarkovTaskProgressLabel(status: string | null | undefined): string {
  const key = (status || "").trim();
  return TARKOV_TASK_PROGRESS_LABELS[key] || "";
}

export function readTarkovTaskMineMode(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function useTarkovTaskMineMode() {
  const [enabled, setEnabled] = useState(readTarkovTaskMineMode);
  const setMine = useCallback((value: boolean) => {
    setEnabled(value);
    try {
      localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
    } catch {
      /* ignore quota / private mode */
    }
  }, []);
  return [enabled, setMine] as const;
}
