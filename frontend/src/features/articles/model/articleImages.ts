export type ArticleBodyFormat = "markdown" | "html";
export type ArticleUploadKind = "image" | "file";
export type ArticleUploadedAsset = {
  url: string;
  name: string;
  kind: ArticleUploadKind;
};

const MAX_EMBED_BYTES = 5 * 1024 * 1024;
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const ATTACHMENT_EXTS = new Set([
  ".pdf",
  ".txt",
  ".md",
  ".csv",
  ".rtf",
  ".json",
  ".lml",
  ".doc",
  ".docx",
  ".xls",
  ".xlsx",
  ".ppt",
  ".pptx",
  ".odt",
  ".ods",
  ".odp",
  ".zip",
  ".7z",
  ".rar",
  ".tar",
  ".gz",
  ".tgz",
]);
const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".webp", ".gif"]);

export const ARTICLE_ATTACHMENT_ACCEPT = [...ATTACHMENT_EXTS].join(",");

export function isSafeArticleImageSrc(src: string): boolean {
  const text = (src || "").trim();
  if (!text || text.startsWith("//")) return false;
  if (text.startsWith("/")) {
    const path = text.split("?", 1)[0].split("#", 1)[0];
    return !path.includes("..") && !path.includes("\\") && !path.includes(":");
  }
  try {
    const parsed = new URL(text);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function escapeAttr(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function articleImageMarkup(
  url: string,
  format: ArticleBodyFormat,
  alt = "",
): string {
  if (format === "html") {
    return `<figure><img src="${escapeAttr(url)}" alt="${escapeAttr(alt)}"></figure>\n`;
  }
  return `![${alt.replace(/[[\]]/g, "")}](${url})\n`;
}

export function insertArticleImage(
  body: string,
  url: string,
  format: ArticleBodyFormat,
  alt = "",
): string {
  const chunk = articleImageMarkup(url, format, alt);
  const cur = body || "";
  if (!cur.trim()) return chunk;
  const sep = cur.endsWith("\n") ? "\n" : "\n\n";
  return `${cur}${sep}${chunk}`;
}

export function articleFileExt(name: string): string {
  const base = (name || "").replace(/\\/g, "/").split("/").pop() || "";
  const lower = base.toLowerCase();
  if (lower.endsWith(".tar.gz")) return ".tgz";
  const at = lower.lastIndexOf(".");
  return at >= 0 ? lower.slice(at) : "";
}

export function articleAttachmentHtml(url: string, name: string): string {
  const label = articleAttachmentLabel(name);
  return `<p><a href="${escapeAttr(url)}" rel="noopener noreferrer">${escapeAttr(label)}</a></p>`;
}

export function articleAttachmentLabel(name: string): string {
  const base = (name || "").replace(/\\/g, "/").split("/").pop() || "";
  let cleaned = "";
  for (const ch of base) {
    const code = ch.charCodeAt(0);
    if (code < 32 || ch === "<" || ch === ">") continue;
    cleaned += ch;
  }
  return (cleaned.trim() || "附件").slice(0, 120);
}

export function isArticleImageFile(file: File): boolean {
  if (file.type === "image/svg+xml") return false;
  if (file.type.startsWith("image/")) return true;
  return IMAGE_EXTS.has(articleFileExt(file.name));
}

export function isArticleAttachmentFile(file: File): boolean {
  return ATTACHMENT_EXTS.has(articleFileExt(file.name));
}

export function classifyArticleUpload(file: File): ArticleUploadKind | null {
  if (isArticleImageFile(file)) return "image";
  if (isArticleAttachmentFile(file)) return "file";
  return null;
}

export function filesFromList(
  files: ArrayLike<File> | null | undefined,
): File[] {
  if (!files?.length) return [];
  return Array.from(files);
}

export function filesFromClipboard(data: DataTransfer | null): File[] {
  if (!data) return [];
  const fromFiles = filesFromList(data.files);
  if (fromFiles.length) return fromFiles;
  const out: File[] = [];
  for (const item of Array.from(data.items || [])) {
    if (item.kind !== "file") continue;
    const file = item.getAsFile();
    if (file) out.push(file);
  }
  return out;
}

export function imageFilesFromList(
  files: ArrayLike<File> | null | undefined,
): File[] {
  return filesFromList(files).filter(isArticleImageFile);
}

export function imageFilesFromClipboard(data: DataTransfer | null): File[] {
  return filesFromClipboard(data).filter(isArticleImageFile);
}

export function rejectArticleImageFile(file: File): string | null {
  if (!isArticleImageFile(file)) return "请选择图片文件";
  if (file.size > MAX_EMBED_BYTES) return "图片不能超过 5MB";
  return null;
}

export function rejectArticleAttachmentFile(file: File): string | null {
  if (isArticleImageFile(file)) return null;
  if (!isArticleAttachmentFile(file)) return "不支持的附件类型";
  if (file.size > MAX_ATTACHMENT_BYTES) return "附件不能超过 10MB";
  return null;
}

export function rejectArticleUploadFile(file: File): string | null {
  const kind = classifyArticleUpload(file);
  if (kind === "image") return rejectArticleImageFile(file);
  if (kind === "file") return rejectArticleAttachmentFile(file);
  return "不支持的文件类型";
}
