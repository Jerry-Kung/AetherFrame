import { useEffect, useRef } from "react";

export interface UseTaskPollingOptions<TStatus> {
  taskId: string | null;
  enabled: boolean;
  fetchStatus: (taskId: string) => Promise<TStatus>;
  isTerminal: (s: TStatus) => boolean;
  intervalMs?: number;
  maxConsecutiveErrors?: number;
  onProgress?: (s: TStatus) => void;
  onTerminal: (s: TStatus) => void;
  onGiveUp: (lastError: unknown) => void;
}

export function useTaskPolling<TStatus>(opts: UseTaskPollingOptions<TStatus>): void {
  const {
    taskId,
    enabled,
    fetchStatus,
    isTerminal,
    intervalMs = 10_000,
    maxConsecutiveErrors = 3,
    onProgress,
    onTerminal,
    onGiveUp,
  } = opts;

  const callbacksRef = useRef({ fetchStatus, isTerminal, onProgress, onTerminal, onGiveUp });
  useEffect(() => {
    callbacksRef.current = { fetchStatus, isTerminal, onProgress, onTerminal, onGiveUp };
  });

  useEffect(() => {
    if (!enabled || !taskId) return;
    let alive = true;
    let timer: number | null = null;
    let consecutiveErrors = 0;

    const tick = async () => {
      try {
        const status = await callbacksRef.current.fetchStatus(taskId);
        if (!alive) return;
        consecutiveErrors = 0;
        callbacksRef.current.onProgress?.(status);
        if (callbacksRef.current.isTerminal(status)) {
          callbacksRef.current.onTerminal(status);
          return;
        }
      } catch (e) {
        if (!alive) return;
        consecutiveErrors += 1;
        if (consecutiveErrors >= maxConsecutiveErrors) {
          callbacksRef.current.onGiveUp(e);
          return;
        }
      }
      if (!alive) return;
      timer = window.setTimeout(tick, intervalMs);
    };

    void tick();

    return () => {
      alive = false;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [taskId, enabled, intervalMs, maxConsecutiveErrors]);
}
