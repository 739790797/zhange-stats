import { client } from "./http";
import type { components } from "./generated/schema";
import { filenameFromDisposition } from "@/lib/fileManager";

export type FileSummary = components["schemas"]["FileSummaryOut"];
export type FileBucket = components["schemas"]["FileBucketOut"];
export type FileBrowse = components["schemas"]["FileBrowseOut"];
export type FileBrowseEntry = components["schemas"]["FileBrowseEntryOut"];

const FILES = "/settings/files";
const LONG_TIMEOUT_MS = 120_000;

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
      timeout: 300_000,
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
