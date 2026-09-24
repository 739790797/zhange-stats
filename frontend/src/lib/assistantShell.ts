/**
 * 战鸽助手（zhange-app）嵌入契约。
 * 助手在页面脚本前设置 `window.zhangeAssistant`，或打开 `?embed=assistant`。
 * 个人中心只要主体时再加 `pane: "body"` 或 `?pane=body`。
 * 综合查询只要搜索框时用 `?pane=search`，只认当前地址，不写入会话。
 * 目录相对路径用 `/`。`list` 只回当前层的名字。
 */

export const ASSISTANT_EMBED_QUERY = "assistant";
export const ASSISTANT_EMBED_STORAGE_KEY = "zhange.assistant.embed";
/** 个人中心子页只画 tab 主体。须同时处于助手嵌入。 */
export const ASSISTANT_PANE_BODY = "body";
/** 综合查询只画搜索框。须同时处于助手嵌入，且只看当前地址。 */
export const ASSISTANT_PANE_SEARCH = "search";
export const ASSISTANT_PANE_STORAGE_KEY = "zhange.assistant.pane";

export type AssistantDirEntry = {
  kind: "file" | "directory";
  name: string;
  lastModified?: number;
  size?: number;
};

export type AssistantBoundDir = {
  path: string;
  list: (relativeDir?: string) => Promise<AssistantDirEntry[]>;
  readBytes?: (relativePath: string) => Promise<ArrayBuffer>;
  readText?: (
    relativePath: string,
  ) => Promise<{ text: string; lastModified: number; size: number }>;
  remove?: (relativePaths: string[]) => Promise<string[]>;
  watch?: (onChange: () => void) => () => void;
};

export type AssistantImage = {
  name?: string;
  type?: string;
  bytes: ArrayBuffer;
};

export type ZhangeAssistantHost = {
  embed?: boolean;
  /** `true` 或 `"body"`：个人中心只画当前 tab 主体。 */
  pane?: boolean | "body";
  tarkovFiles?: {
    screenshots?: AssistantBoundDir;
    logs?: AssistantBoundDir;
    rebindScreenshots?: () => Promise<void>;
    rebindLogs?: () => Promise<void>;
  };
  pickImage?: () => Promise<AssistantImage | null>;
};

type AssistantWindow = Window & { zhangeAssistant?: ZhangeAssistantHost };

export function assistantHost(
  win: AssistantWindow | undefined = typeof window === "undefined"
    ? undefined
    : (window as AssistantWindow),
): ZhangeAssistantHost | null {
  const host = win?.zhangeAssistant;
  if (!host || typeof host !== "object") return null;
  return host;
}

export function assistantEmbedFromLocation(
  search: string,
  host: ZhangeAssistantHost | null,
  stored: string | null,
): boolean {
  if (host?.embed === true) return true;
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  if (params.get("embed") === ASSISTANT_EMBED_QUERY) return true;
  return stored === "1";
}

export function assistantBodyPaneFromLocation(
  search: string,
  host: ZhangeAssistantHost | null,
  stored: string | null,
): boolean {
  if (host?.pane === true || host?.pane === ASSISTANT_PANE_BODY) return true;
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  if (params.get("pane") === ASSISTANT_PANE_BODY) return true;
  return stored === ASSISTANT_PANE_BODY;
}

export function assistantSearchPaneFromLocation(search: string): boolean {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  return params.get("pane") === ASSISTANT_PANE_SEARCH;
}

export function isAssistantEmbed(): boolean {
  if (typeof window === "undefined") return false;
  const embedded = assistantEmbedFromLocation(
    window.location.search,
    assistantHost(),
    window.sessionStorage.getItem(ASSISTANT_EMBED_STORAGE_KEY),
  );
  if (embedded) {
    window.sessionStorage.setItem(ASSISTANT_EMBED_STORAGE_KEY, "1");
  }
  return embedded;
}

export function rememberAssistantEmbed(): void {
  isAssistantEmbed();
}

/** 助手子菜单打开个人中心 tab 时只要主体。浏览器无嵌入标记时为 false。 */
export function isAssistantBodyPane(): boolean {
  if (!isAssistantEmbed()) return false;
  if (typeof window === "undefined") return false;
  const pane = assistantBodyPaneFromLocation(
    window.location.search,
    assistantHost(),
    window.sessionStorage.getItem(ASSISTANT_PANE_STORAGE_KEY),
  );
  if (pane) {
    window.sessionStorage.setItem(ASSISTANT_PANE_STORAGE_KEY, ASSISTANT_PANE_BODY);
  }
  return pane;
}

/** 助手「综合查询」只要搜索框。只认地址上的 `pane=search`，不沿用个人中心的会话标记。 */
export function isAssistantSearchPane(): boolean {
  if (!isAssistantEmbed()) return false;
  if (typeof window === "undefined") return false;
  return assistantSearchPaneFromLocation(window.location.search);
}

export function assistantScreenshotsBinding(): AssistantBoundDir | null {
  return assistantHost()?.tarkovFiles?.screenshots ?? null;
}

export function assistantLogsBinding(): AssistantBoundDir | null {
  return assistantHost()?.tarkovFiles?.logs ?? null;
}

export function hasAssistantTarkovFiles(): boolean {
  return Boolean(assistantScreenshotsBinding() || assistantLogsBinding());
}

export async function rebindAssistantScreenshots(): Promise<boolean> {
  const rebind = assistantHost()?.tarkovFiles?.rebindScreenshots;
  if (!rebind) return false;
  await rebind();
  return true;
}

export async function rebindAssistantLogs(): Promise<boolean> {
  const rebind = assistantHost()?.tarkovFiles?.rebindLogs;
  if (!rebind) return false;
  await rebind();
  return true;
}

export function assistantCanPickImage(): boolean {
  return typeof assistantHost()?.pickImage === "function";
}

export async function pickAssistantImage(): Promise<File | null> {
  const pick = assistantHost()?.pickImage;
  if (!pick) return null;
  const image = await pick();
  if (!image?.bytes) return null;
  const type = (image.type || "image/png").trim() || "image/png";
  const name = (image.name || "screenshot.png").trim() || "screenshot.png";
  return new File([image.bytes], name, { type });
}
