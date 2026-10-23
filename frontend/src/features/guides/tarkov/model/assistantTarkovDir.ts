import type { AssistantBoundDir, AssistantDirEntry } from "./assistantHostFiles";
import type {
  ListedFileMeta,
  ReadableDir,
  ReadableEntry,
  ReadableFile,
} from "@/features/guides/tarkov/model/tarkovGameLogAccess";

const WATCH = Symbol.for("zhange.assistant.watch");
const BOUND = Symbol.for("zhange.assistant.bound");

type AssistantDir = ReadableDir &
  ReadableEntry & {
    kind: "directory";
    path: string;
    [WATCH]?: (onChange: () => void) => () => void;
    [BOUND]: true;
  };

function joinRel(base: string, name: string): string {
  const clean = name.replace(/^[\\/]+/, "").replace(/\\/g, "/");
  return base ? `${base}/${clean}` : clean;
}

function displayPath(root: string, rel: string): string {
  const base = root.replace(/[\\/]+$/, "");
  if (!rel) return base;
  return `${base}\\${rel.replace(/\//g, "\\")}`;
}

function dirName(path: string): string {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || path;
}

function entryRemoved(removed: readonly string[], rel: string, name: string): boolean {
  return removed.some((row) => {
    const text = row.replace(/\\/g, "/");
    return text === rel || text === name || text.endsWith(`/${name}`);
  });
}

function finiteOrUndefined(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

/** list 回的大小与修改时间；轮询拿它比对，没变就不经桥读正文或图片字节。 */
function listedMeta(row: AssistantDirEntry): ListedFileMeta {
  return {
    size: finiteOrUndefined(row.size),
    lastModified: finiteOrUndefined(row.lastModified),
  };
}

function toEntry(
  bound: AssistantBoundDir,
  rel: string,
  row: AssistantDirEntry,
): ReadableEntry {
  if (row.kind === "directory") {
    return childDir(bound, joinRel(rel, row.name));
  }
  const fileRel = joinRel(rel, row.name);
  const lastModified = row.lastModified ?? 0;
  const file: ReadableFile & ReadableEntry = {
    kind: "file",
    name: row.name,
    listed: listedMeta(row),
    getFile: async () => {
      if (bound.readText) {
        const read = await bound.readText(fileRel);
        return new File([read.text], row.name, {
          type: "text/plain",
          lastModified: read.lastModified || lastModified,
        });
      }
      if (!bound.readBytes) {
        throw new Error("战鸽助手没有提供读取文件的方法");
      }
      const bytes = await bound.readBytes(fileRel);
      return new File([bytes], row.name, {
        type: "application/octet-stream",
        lastModified,
      });
    },
  };
  return file;
}

function childDir(bound: AssistantBoundDir, rel: string): AssistantDir {
  const path = displayPath(bound.path, rel);
  const dir: AssistantDir = {
    kind: "directory",
    name: dirName(path),
    path,
    [BOUND]: true,
    queryPermission: async (opts) => {
      if (opts?.mode === "readwrite") return bound.remove ? "granted" : "denied";
      return "granted";
    },
    requestPermission: async (opts) => dir.queryPermission(opts),
    values: async function* values() {
      const rows = await bound.list(rel);
      for (const row of rows) yield toEntry(bound, rel, row);
    },
    getDirectoryHandle: async (name: string) => childDir(bound, joinRel(rel, name)),
    getFileHandle: async (name: string) => {
      const rows = await bound.list(rel);
      const hit = rows.find((row) => row.kind === "file" && row.name === name);
      if (!hit) throw new Error(`找不到文件 ${name}`);
      const entry = toEntry(bound, rel, hit);
      if (!entry.getFile) throw new Error(`找不到文件 ${name}`);
      return entry as ReadableFile;
    },
    removeEntry: bound.remove
      ? async (name: string) => {
          const fileRel = joinRel(rel, name);
          const removed = await bound.remove!([fileRel]);
          if (!entryRemoved(removed, fileRel, name)) {
            throw new Error(`删除失败 ${name}`);
          }
        }
      : undefined,
  };
  if (bound.watch && !rel) dir[WATCH] = bound.watch;
  return dir;
}

export function assistantBoundToDir(bound: AssistantBoundDir): ReadableDir {
  return childDir(bound, "");
}

/** 助手绑定转出来的目录（带函数，不能存进 IndexedDB）。 */
export function isAssistantDir(dir: ReadableDir | null | undefined): boolean {
  return Boolean(dir && (dir as Partial<AssistantDir>)[BOUND]);
}

export function assistantDirWatch(
  dir: ReadableDir,
): ((onChange: () => void) => () => void) | null {
  const watch = (dir as AssistantDir)[WATCH];
  return typeof watch === "function" ? watch : null;
}
