import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CHUNK_RELOAD_GUARD_MS,
  CHUNK_RELOAD_STAMP_KEY,
  isChunkLoadError,
  planChunkReload,
} from "./chunkReload";

const CHUNK_MESSAGE = "Failed to fetch dynamically imported module: https://x/assets/TarkovPage-abc.js";

describe("isChunkLoadError", () => {
  it("recognises failed dynamic imports across browsers and the Vite preload helper", () => {
    for (const message of [
      CHUNK_MESSAGE,
      "error loading dynamically imported module: https://x/assets/a.js",
      "Importing a module script failed.",
      "Unable to preload CSS for /assets/a.css",
      "Loading chunk 12 failed.",
      "Loading CSS chunk 3 failed",
    ]) {
      expect(isChunkLoadError(new TypeError(message))).toBe(true);
      expect(isChunkLoadError(message)).toBe(true);
    }
    const named = new Error("whatever");
    named.name = "ChunkLoadError";
    expect(isChunkLoadError(named)).toBe(true);
  });

  it("ignores ordinary render and request errors", () => {
    expect(isChunkLoadError(new TypeError("Cannot read properties of undefined (reading 'map')"))).toBe(
      false,
    );
    expect(isChunkLoadError(new Error("Request failed with status code 500"))).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
    expect(isChunkLoadError(undefined)).toBe(false);
  });
});

describe("planChunkReload", () => {
  const now = 1_700_000_000_000;

  it("reloads when there is no earlier attempt", () => {
    expect(planChunkReload(null, now)).toBe(true);
    expect(planChunkReload(Number.NaN, now)).toBe(true);
  });

  it("holds off inside the guard window", () => {
    expect(planChunkReload(now - 1_000, now)).toBe(false);
    expect(planChunkReload(now - CHUNK_RELOAD_GUARD_MS + 1, now)).toBe(false);
  });

  it("tries again once the window has passed or the clock went backwards", () => {
    expect(planChunkReload(now - CHUNK_RELOAD_GUARD_MS, now)).toBe(true);
    expect(planChunkReload(now + 5_000, now)).toBe(true);
  });
});

async function settles(promise: Promise<unknown>, ms = 20): Promise<boolean> {
  return Promise.race([
    promise.then(
      () => true,
      () => true,
    ),
    new Promise<boolean>((resolve) => setTimeout(() => resolve(false), ms)),
  ]);
}

describe("reload in the page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function loadInPage(seed: Record<string, string> = {}) {
    vi.resetModules();
    const store = new Map(Object.entries(seed));
    const reload = vi.fn();
    const listeners = new Map<string, (event: Event) => void>();
    vi.stubGlobal("window", {
      sessionStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => {
          store.set(key, value);
        },
      },
      location: { reload },
      addEventListener: (type: string, listener: (event: Event) => void) => {
        listeners.set(type, listener);
      },
    });
    const mod = await import("./chunkReload");
    return { mod, store, reload, listeners };
  }

  function preloadErrorEvent() {
    return { preventDefault: vi.fn() };
  }

  it("reloads once and treats later failures as part of that reload", async () => {
    const { mod, store, reload } = await loadInPage();
    expect(mod.chunkReloadPending()).toBe(false);
    expect(mod.reloadOnceForChunkError()).toBe(true);
    expect(mod.reloadOnceForChunkError()).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(mod.chunkReloadPending()).toBe(true);
    expect(Number(store.get(CHUNK_RELOAD_STAMP_KEY))).toBeGreaterThan(0);
  });

  it("leaves it to the error page when it reloaded a moment ago", async () => {
    const { mod, reload } = await loadInPage({
      [CHUNK_RELOAD_STAMP_KEY]: String(Date.now() - 1_000),
    });
    expect(mod.reloadOnceForChunkError()).toBe(false);
    expect(reload).not.toHaveBeenCalled();
    expect(mod.chunkReloadPending()).toBe(false);
  });

  it("cancels vite:preloadError only when it actually reloads", async () => {
    const fresh = await loadInPage();
    const first = preloadErrorEvent();
    fresh.listeners.get("vite:preloadError")?.(first as unknown as Event);
    expect(first.preventDefault).toHaveBeenCalled();
    expect(fresh.reload).toHaveBeenCalledTimes(1);

    const guarded = await loadInPage({ [CHUNK_RELOAD_STAMP_KEY]: String(Date.now()) });
    const second = preloadErrorEvent();
    guarded.listeners.get("vite:preloadError")?.(second as unknown as Event);
    expect(second.preventDefault).not.toHaveBeenCalled();
    expect(guarded.reload).not.toHaveBeenCalled();
  });

  it("keeps a failed import pending while reloading and rethrows other errors", async () => {
    const { mod, reload } = await loadInPage();
    const broken = new Error("boom");
    await expect(mod.withChunkReload(() => Promise.reject(broken))()).rejects.toBe(broken);
    expect(reload).not.toHaveBeenCalled();

    const failed = mod.withChunkReload(() => Promise.reject(new TypeError(CHUNK_MESSAGE)))();
    expect(await settles(failed)).toBe(false);
    expect(reload).toHaveBeenCalledTimes(1);

    const cancelled = mod.withChunkReload(() => Promise.resolve(undefined))();
    expect(await settles(cancelled)).toBe(false);
    const later = mod.withChunkReload(() => Promise.reject(new Error("aftershock")))();
    expect(await settles(later)).toBe(false);
  });

  it("passes modules through untouched", async () => {
    const { mod } = await loadInPage();
    const page = { default: () => null };
    await expect(mod.withChunkReload(() => Promise.resolve(page))()).resolves.toBe(page);
  });
});
