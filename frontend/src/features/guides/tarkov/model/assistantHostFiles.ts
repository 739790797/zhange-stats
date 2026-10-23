/**
 * 塔科夫助手文件桥接契约。路径使用 `/`，list 只返回当前目录的直接子项。
 * zhange-app 在 window.zhangeAssistant.tarkovFiles 上提供目录访问与重新绑定能力。
 */
import { assistantHost, type ZhangeAssistantHost } from "@/shared/lib/assistantShell";

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

type TarkovAssistantHost = ZhangeAssistantHost & {
  tarkovFiles?: {
    screenshots?: AssistantBoundDir;
    logs?: AssistantBoundDir;
    rebindScreenshots?: () => Promise<void>;
    rebindLogs?: () => Promise<void>;
  };
};

function tarkovAssistantHost(): TarkovAssistantHost | null {
  return assistantHost() as TarkovAssistantHost | null;
}

export function assistantScreenshotsBinding(): AssistantBoundDir | null {
  return tarkovAssistantHost()?.tarkovFiles?.screenshots ?? null;
}

export function assistantLogsBinding(): AssistantBoundDir | null {
  return tarkovAssistantHost()?.tarkovFiles?.logs ?? null;
}

export function hasAssistantTarkovFiles(): boolean {
  return Boolean(assistantScreenshotsBinding() || assistantLogsBinding());
}

export async function rebindAssistantScreenshots(): Promise<boolean> {
  const rebind = tarkovAssistantHost()?.tarkovFiles?.rebindScreenshots;
  if (!rebind) return false;
  await rebind();
  return true;
}

export async function rebindAssistantLogs(): Promise<boolean> {
  const rebind = tarkovAssistantHost()?.tarkovFiles?.rebindLogs;
  if (!rebind) return false;
  await rebind();
  return true;
}
