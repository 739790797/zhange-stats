/** 发版后旧页面再去拿已被替换的分包会失败：识别出来就整页刷新一次，换上新的 index.html。 */

import { lazy, type LazyExoticComponent } from "react";

export const CHUNK_RELOAD_STAMP_KEY = "zhange-chunk-reload-at";
/** 这段时间内只自动刷新一次；新版本也缺包时交给错误页的手动刷新，免得来回刷。 */
export const CHUNK_RELOAD_GUARD_MS = 60_000;

const CHUNK_ERROR_RE =
  /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed|Unable to preload CSS|Loading (CSS )?chunk \S+ failed/i;

let reloading = false;

export function isChunkLoadError(error: unknown): boolean {
  if (error instanceof Error) {
    return error.name === "ChunkLoadError" || CHUNK_ERROR_RE.test(error.message);
  }
  return typeof error === "string" && CHUNK_ERROR_RE.test(error);
}

export function planChunkReload(lastAt: number | null, now: number): boolean {
  if (lastAt == null || !Number.isFinite(lastAt)) return true;
  return now < lastAt || now - lastAt >= CHUNK_RELOAD_GUARD_MS;
}

/** 已经在刷新：此后冒出来的加载错误都是这次刷新的余波，不必再报错。 */
export function chunkReloadPending(): boolean {
  return reloading;
}

/** 按保护期刷新一次；返回是否真的发起了刷新。拿不到 sessionStorage 时不自动刷新。 */
export function reloadOnceForChunkError(): boolean {
  if (reloading) return true;
  if (typeof window === "undefined") return false;
  try {
    const storage = window.sessionStorage;
    const now = Date.now();
    const raw = storage.getItem(CHUNK_RELOAD_STAMP_KEY);
    if (!planChunkReload(raw ? Number(raw) : null, now)) return false;
    storage.setItem(CHUNK_RELOAD_STAMP_KEY, String(now));
  } catch {
    return false;
  }
  reloading = true;
  window.location.reload();
  return true;
}

function pendingForever(): Promise<never> {
  return new Promise<never>(() => {});
}

/**
 * 动态 import 加一层：分包失败时刷新页面，刷新期间不再 resolve / reject，Suspense 保持占位而不是闪错误页。
 * vite:preloadError 被拦下后 import 会得到 undefined，也按刷新处理。
 */
export function withChunkReload<T>(factory: () => Promise<T>): () => Promise<T> {
  return async () => {
    try {
      const mod = await factory();
      if (mod == null && reloading) return pendingForever();
      return mod;
    } catch (error) {
      if (reloading || (isChunkLoadError(error) && reloadOnceForChunkError())) {
        return pendingForever();
      }
      throw error;
    }
  };
}

/** React.lazy 自己对组件的约束，照搬才能把各页面的 props 类型原样带出去。 */
type LazyComponent = Awaited<ReturnType<Parameters<typeof lazy>[0]>>["default"];

export function lazyWithReload<T extends LazyComponent>(
  factory: () => Promise<{ default: T }>,
): LazyExoticComponent<T> {
  return lazy(withChunkReload(factory));
}

if (typeof window !== "undefined") {
  window.addEventListener("vite:preloadError", (event) => {
    if (reloadOnceForChunkError()) event.preventDefault();
  });
}
