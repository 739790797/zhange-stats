import { client } from "./http";
import type { components } from "./generated/schema";
import { filenameFromDisposition } from "@/lib/fileManager";

export type FileSummary = components["schemas"]["FileSummaryOut"];
export type FileBucket = components["schemas"]["FileBucketOut"];
export type FileBrowse = components["schemas"]["FileBrowseOut"];
export type FileBrowseEntry = components["schemas"]["FileBrowseEntryOut"];
export type FileOk = components["schemas"]["FileOkOut"];
export type FileContents = components["schemas"]["FileContentsOut"];

const FILES = "/settings/files";
const LONG_TIMEOUT_MS = 120_000;
const WRITE_TIMEOUT_MS = 300_000;

export async function fetchFileSummary(force = false) {
  const { data } = await client.get<FileSummary>(`${FILES}/summary`, {
    params: { force },
    timeout: LONG_TIMEOUT_MS,
  });
  return data;
}

export async function fetchFileBrowse(rootId: string, path = "") {
  const { data } = await client.get<FileBrowse>(`${FILES}/browse`, {
    params: { root_id: rootId, path },
    timeout: LONG_TIMEOUT_MS,
  });
  return data;
}

async function reraiseBlobError(error: unknown): Promise<never> {
  const err = error as {
    response?: { data?: unknown; status?: number; headers?: unknown };
  };
  const blob = err.response?.data;
  if (blob instanceof Blob) {
    const text = await blob.text();
    try {
      err.response = {
        ...err.response,
        data: JSON.parse(text) as { detail?: unknown },
      };
    } catch {
      err.response = { ...err.response, data: { detail: text } };
    }
  }
  throw error;
}

export async function downloadManagedFile(rootId: string, path: string) {
  try {
    const res = await client.get<Blob>(`${FILES}/download`, {
      params: { root_id: rootId, path },
      responseType: "blob",
      timeout: WRITE_TIMEOUT_MS,
    });
    const name = filenameFromDisposition(
      res.headers["content-disposition"],
      path.split("/").pop() || "download",
    );
    const url = URL.createObjectURL(res.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    await reraiseBlobError(error);
  }
}

export async function fetchManagedFileContents(rootId: string, path: string) {
  const { data } = await client.get<FileContents>(`${FILES}/contents`, {
    params: { root_id: rootId, path },
    timeout: LONG_TIMEOUT_MS,
  });
  return data;
}

export async function writeManagedFile(
  rootId: string,
  path: string,
  content: string,
) {
  const { data } = await client.put<FileOk>(
    `${FILES}/contents`,
    { root_id: rootId, path, content },
    { timeout: WRITE_TIMEOUT_MS },
  );
  return data;
}

export async function uploadManagedFile(
  rootId: string,
  path: string,
  file: File,
  onProgress?: (percent: number | null) => void,
) {
  const form = new FormData();
  form.append("root_id", rootId);
  form.append("path", path);
  form.append("file", file);
  const { data } = await client.post<FileOk>(`${FILES}/upload`, form, {
    timeout: WRITE_TIMEOUT_MS,
    onUploadProgress: (evt) => {
      if (!onProgress) return;
      if (!evt.total) {
        onProgress(null);
        return;
      }
      onProgress(Math.min(100, Math.round((evt.loaded / evt.total) * 100)));
    },
  });
  return data;
}

export async function createManagedFolder(
  rootId: string,
  path: string,
  name: string,
) {
  const { data } = await client.post<FileOk>(`${FILES}/create-folder`, {
    root_id: rootId,
    path,
    name,
  });
  return data;
}

export async function createManagedFile(
  rootId: string,
  path: string,
  name: string,
  content = "",
) {
  const { data } = await client.post<FileOk>(
    `${FILES}/create-file`,
    { root_id: rootId, path, name, content },
    { timeout: WRITE_TIMEOUT_MS },
  );
  return data;
}

export async function renameManagedFile(
  rootId: string,
  path: string,
  src: string,
  dest: string,
) {
  const { data } = await client.post<FileOk>(`${FILES}/rename`, {
    root_id: rootId,
    path,
    src,
    dest,
  });
  return data;
}

export async function deleteManagedFiles(
  rootId: string,
  path: string,
  names: string[],
) {
  const { data } = await client.post<FileOk>(`${FILES}/delete`, {
    root_id: rootId,
    path,
    names,
  });
  return data;
}
