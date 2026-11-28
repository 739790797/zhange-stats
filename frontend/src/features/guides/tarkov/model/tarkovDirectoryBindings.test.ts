import { afterEach, describe, expect, it, vi } from "vitest";
import { TARKOV_LIVE_DIRS_EVENT } from "./tarkovLiveWatch";
import {
  loadTarkovDirectoryBinding,
  queryLogsDirPermission,
  requestScreenshotsDirPermission,
  saveTarkovDirectoryBinding,
  type ReadableDir,
} from "./tarkovGameLogAccess";

function browserStorage(data: Record<string, unknown> = {}) {
  const store = {
    get: (key: string) => ({ result: data[key] }),
    put: vi.fn(),
  };
  const txn = {
    oncomplete: null as (() => void) | null,
    onabort: null as (() => void) | null,
    objectStore: () => store,
    abort: vi.fn(),
  };
  const db = { close: vi.fn(), transaction: vi.fn(() => txn) };
  const request = {
    result: db,
    onblocked: null as (() => void) | null,
    onsuccess: null as (() => void) | null,
  };
  const page = new EventTarget();
  vi.stubGlobal("window", page);
  vi.stubGlobal("indexedDB", { open: () => request });
  return { request, db, txn, store, page };
}

function directory(name = "Screenshots"): ReadableDir {
  return {
    name,
    queryPermission: async () => "granted",
    requestPermission: async () => "granted",
    getDirectoryHandle: async () => {
      throw new Error("No directory in this fixture");
    },
    getFileHandle: async () => {
      throw new Error("No file in this fixture");
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("Tarkov directory bindings", () => {
  it("restores handles and paths saved by the existing IndexedDB layout", async () => {
    const handle = directory();
    const { request, txn } = browserStorage({
      "screenshots-dir": handle,
      "screenshots-dir-path": "D:\\Documents\\Escape from Tarkov\\Screenshots",
    });
    const restored = loadTarkovDirectoryBinding("screenshots");
    request.onsuccess?.();
    txn.oncomplete?.();
    await expect(restored).resolves.toEqual({
      handle,
      path: "D:\\Documents\\Escape from Tarkov\\Screenshots",
    });
  });

  it("reports a blocked open and closes a connection delivered after the failure", async () => {
    const { request, db } = browserStorage();
    const restored = loadTarkovDirectoryBinding("logs");
    request.onblocked?.();
    await expect(restored).rejects.toThrow("关闭其他战鸽数据标签页");
    request.onsuccess?.();
    expect(db.close).toHaveBeenCalledOnce();
    expect(db.transaction).not.toHaveBeenCalled();
  });

  it("releases the caller when the browser never returns an open result", async () => {
    vi.useFakeTimers();
    browserStorage();
    const restored = expect(loadTarkovDirectoryBinding("logs")).rejects.toThrow(
      "浏览器存储响应超时",
    );
    await vi.runAllTimersAsync();
    await restored;
  });

  it("never announces a binding when IndexedDB aborts its write", async () => {
    const { request, txn, page } = browserStorage();
    const event = vi.fn();
    page.addEventListener(TARKOV_LIVE_DIRS_EVENT, event);
    const saved = saveTarkovDirectoryBinding("screenshots", directory(), "Screenshots");
    request.onsuccess?.();
    txn.onabort?.();
    await expect(saved).rejects.toThrow("无法保存目录授权");
    expect(event).not.toHaveBeenCalled();
  });

  it("publishes the changed directory only after the handle and path commit", async () => {
    const { request, txn, store, page } = browserStorage();
    const handle = directory("NewScreenshots");
    const changed: unknown[] = [];
    page.addEventListener(TARKOV_LIVE_DIRS_EVENT, (event) => {
      changed.push((event as CustomEvent).detail);
    });
    const saved = saveTarkovDirectoryBinding("screenshots", handle, "NewScreenshots");
    request.onsuccess?.();
    expect(store.put.mock.calls).toEqual([
      [handle, "screenshots-dir"],
      ["NewScreenshots", "screenshots-dir-path"],
    ]);
    expect(changed).toEqual([]);
    txn.oncomplete?.();
    await saved;
    expect(changed).toEqual(["screenshots"]);
  });

  it("times out a saved log handle whose browser permission query never settles", async () => {
    vi.useFakeTimers();
    const handle = { ...directory("Logs"), queryPermission: () => new Promise<never>(() => {}) };
    const restored = expect(queryLogsDirPermission(handle)).rejects.toThrow("读取本机目录超时");
    await vi.runAllTimersAsync();
    await restored;
  });

  it("reads screenshots without asking for delete access by default", async () => {
    const touched: string[] = [];
    const handle: ReadableDir = {
      ...directory(),
      requestPermission: async ({ mode = "read" } = {}) => {
        touched.push(mode);
        return mode === "read" ? "granted" : "denied";
      },
    };
    await expect(requestScreenshotsDirPermission(handle)).resolves.toBe("granted");
    expect(touched).toEqual(["read"]);
  });
});
