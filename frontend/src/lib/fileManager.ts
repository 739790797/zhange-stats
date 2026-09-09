export type FileKind = "generated" | "dependency" | "cache" | "download";

export const FILE_KIND_LABEL: Record<FileKind, string> = {
  generated: "产生",
  dependency: "依赖",
  cache: "缓存",
  download: "下载",
};

export function formatBytes(n: number) {
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n === 0) return "0 B";
  const gb = n / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  const mb = n / 1024 ** 2;
  if (mb >= 1) return `${mb.toFixed(2)} MB`;
  const kb = n / 1024;
  if (kb >= 1) return `${kb.toFixed(0)} KB`;
  return `${Math.round(n)} B`;
}

export function formatPercent(used: number, total: number) {
  if (!Number.isFinite(used) || !Number.isFinite(total) || total <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round((used / total) * 100)));
}

export function isFileBrowseLocked(row: {
  name?: string;
  sensitive?: boolean;
  missing?: boolean;
}): boolean {
  if (row.name === "..") return false;
  return Boolean(row.sensitive || row.missing);
}

export type DiskVolumeInput = {
  id: string;
  path: string;
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
};

export type DiskStack = {
  totalBytes: number;
  siteBytes: number;
  otherBytes: number;
  freeBytes: number;
  path: string;
};

export function stackDiskUsage(
  siteBytes: number,
  volumes: DiskVolumeInput[],
): DiskStack | null {
  if (!volumes.length) return null;
  const vol = volumes.find((row) => row.id === "vol_install") || volumes[0];
  const total = Math.max(0, vol.total_bytes);
  if (!Number.isFinite(total) || total <= 0) return null;
  const used = Math.min(total, Math.max(0, vol.used_bytes));
  const free = Math.max(0, total - used);
  const siteRaw = Number.isFinite(siteBytes) ? Math.max(0, siteBytes) : 0;
  const site = Math.min(siteRaw, used);
  return {
    totalBytes: total,
    siteBytes: site,
    otherBytes: Math.max(0, used - site),
    freeBytes: free,
    path: vol.path,
  };
}

export function joinFileRel(base: string, name: string) {
  const left = (base || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  const right = (name || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  if (!left) return right;
  if (!right) return left;
  return `${left}/${right}`;
}

export function parentFileRel(path: string) {
  const text = (path || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  if (!text) return "";
  const idx = text.lastIndexOf("/");
  return idx <= 0 ? "" : text.slice(0, idx);
}

/** 目录浏览从当前根/路径返回上一层；根目录再上一级即「全部」。 */
export function fileBrowseUp(
  rootId: string,
  path: string,
): { root: string; path: string } {
  if ((path || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "")) {
    return { root: rootId, path: parentFileRel(path) };
  }
  return { root: "", path: "" };
}

export type FileAllRootRow = {
  key: string;
  name: string;
  is_dir: true;
  size: 0;
  modified_at: null;
  sensitive: false;
  downloadable: false;
  browseRootId: string;
  missing: boolean;
};

export function fileAllRootRows(
  roots: { id: string; label: string; exists: boolean }[],
): FileAllRootRow[] {
  return roots.map((row) => ({
    key: row.id,
    name: row.label,
    is_dir: true,
    size: 0,
    modified_at: null,
    sensitive: false,
    downloadable: false,
    browseRootId: row.id,
    missing: !row.exists,
  }));
}

export function filenameFromDisposition(header: string | undefined, fallback: string) {
  const text = (header || "").trim();
  const star = /filename\*=UTF-8''([^;]+)/i.exec(text);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1]);
    } catch {
      return star[1];
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(text);
  return (plain?.[1] || fallback).trim() || fallback;
}
