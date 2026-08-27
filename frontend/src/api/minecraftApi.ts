import { client } from "./http";
import type { components } from "./generated/schema";

export type MinecraftStatus = components["schemas"]["MinecraftStatusOut"];
export type MinecraftPlayer = components["schemas"]["MinecraftPlayerOut"];
export type MinecraftPowerSignal =
  components["schemas"]["MinecraftPowerIn"]["signal"];
export type MinecraftPowerResult = components["schemas"]["MinecraftPowerOut"];
export type MinecraftFileEntry = components["schemas"]["MinecraftFileEntryOut"];
export type MinecraftFileList = components["schemas"]["MinecraftFileListOut"];
export type MinecraftFileContents =
  components["schemas"]["MinecraftFileContentsOut"];
export type MinecraftFileOk = components["schemas"]["MinecraftFileOkOut"];
export type MinecraftFileDownload =
  components["schemas"]["MinecraftFileDownloadOut"];
export type MinecraftModTools = components["schemas"]["MinecraftModToolsOut"];
export type MinecraftModTool = components["schemas"]["MinecraftModToolOut"];
export type MinecraftModInventoryJar =
  components["schemas"]["MinecraftModInventoryJarOut"];
export type MinecraftChunkyStatus =
  components["schemas"]["MinecraftChunkyStatusOut"];
export type MinecraftModToolCommand =
  components["schemas"]["MinecraftModToolCommandOut"];
export type MinecraftModToolCommandIn =
  components["schemas"]["MinecraftModToolCommandIn"];
export type MinecraftChunkyAction = MinecraftModToolCommandIn["action"];
export type MinecraftModToolExecIn =
  components["schemas"]["MinecraftModToolExecIn"];
export type MinecraftModCommandNode =
  components["schemas"]["MinecraftModCommandNodeOut"];
export type MinecraftModCommandArg =
  components["schemas"]["MinecraftModCommandArgOut"];
export type MinecraftModFeature =
  components["schemas"]["MinecraftModFeatureOut"];
export type MinecraftModToolInstall =
  components["schemas"]["MinecraftModToolInstallOut"];
export type MinecraftModToolInstallIn =
  components["schemas"]["MinecraftModToolInstallIn"];
export type MinecraftModToolVersions =
  components["schemas"]["MinecraftModToolVersionsOut"];
export type MinecraftModToolPresetApply =
  components["schemas"]["MinecraftModToolPresetApplyOut"];
export type MinecraftModToolPreset =
  components["schemas"]["MinecraftModToolPresetOut"];
export type MinecraftModToolPresetPin =
  components["schemas"]["MinecraftModToolPresetPinOut"];
export type MinecraftModToolPresetIn =
  components["schemas"]["MinecraftModToolPresetIn"];
export type MinecraftModToolPresetKeys =
  components["schemas"]["MinecraftModToolPresetKeysOut"];
export type MinecraftFileCompressIn =
  components["schemas"]["MinecraftFileCompressIn"];
export type MinecraftPerf = components["schemas"]["MinecraftPerfOut"];
export type MinecraftPresence = components["schemas"]["MinecraftPresenceOut"];
export type MinecraftPresenceRow =
  components["schemas"]["MinecraftPresenceRowOut"];

export async function fetchMinecraftStatus() {
  const { data } = await client.get<MinecraftStatus>(
    "/guides/minecraft/status",
    { timeout: 45_000 },
  );
  return data;
}

export async function fetchMinecraftPresence(date: string, end?: string) {
  const { data } = await client.get<MinecraftPresence>(
    "/guides/minecraft/presence",
    {
      params: end ? { date, end } : { date },
      timeout: 20_000,
    },
  );
  return data;
}

export async function fetchMinecraftPerf(range = "30m") {
  const { data } = await client.get<MinecraftPerf>("/guides/minecraft/perf", {
    params: { range },
  });
  return data;
}

export async function sendMinecraftPower(signal: MinecraftPowerSignal) {
  const { data } = await client.post<MinecraftPowerResult>(
    "/guides/minecraft/power",
    { signal },
    { timeout: 30_000 },
  );
  return data;
}

export function minecraftConsoleWsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/guides/minecraft/console`;
}

const FILES = "/guides/minecraft/files";
const FILE_TIMEOUT = 180_000;

export async function fetchMinecraftFiles(directory: string) {
  const { data } = await client.get<MinecraftFileList>(FILES, {
    params: { directory },
    timeout: 30_000,
  });
  return data;
}

export async function fetchMinecraftFileContents(path: string) {
  const { data } = await client.get<MinecraftFileContents>(`${FILES}/contents`, {
    params: { path },
    timeout: 60_000,
  });
  return data;
}

export async function writeMinecraftFile(path: string, content: string) {
  const { data } = await client.put<MinecraftFileOk>(
    `${FILES}/contents`,
    { path, content },
    { timeout: FILE_TIMEOUT },
  );
  return data;
}

export async function fetchMinecraftFileDownload(path: string) {
  const { data } = await client.get<MinecraftFileDownload>(`${FILES}/download`, {
    params: { path },
    timeout: 30_000,
  });
  return data;
}

export async function uploadMinecraftFile(
  directory: string,
  file: File,
  onProgress?: (percent: number | null) => void,
) {
  const form = new FormData();
  form.append("directory", directory);
  form.append("file", file);
  const { data } = await client.post<MinecraftFileOk>(`${FILES}/upload`, form, {
    timeout: FILE_TIMEOUT,
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

export async function createMinecraftFolder(directory: string, name: string) {
  const { data } = await client.post<MinecraftFileOk>(
    `${FILES}/create-folder`,
    { directory, name },
  );
  return data;
}

export async function createMinecraftFile(
  directory: string,
  name: string,
  content = "",
) {
  const { data } = await client.post<MinecraftFileOk>(
    `${FILES}/create-file`,
    { directory, name, content },
    { timeout: FILE_TIMEOUT },
  );
  return data;
}

export async function renameMinecraftFile(
  directory: string,
  src: string,
  dest: string,
) {
  const { data } = await client.post<MinecraftFileOk>(`${FILES}/rename`, {
    directory,
    src,
    dest,
  });
  return data;
}

export async function copyMinecraftFile(path: string) {
  const { data } = await client.post<MinecraftFileOk>(`${FILES}/copy`, { path });
  return data;
}

export async function deleteMinecraftFiles(directory: string, names: string[]) {
  const { data } = await client.post<MinecraftFileOk>(`${FILES}/delete`, {
    directory,
    names,
  });
  return data;
}

export async function compressMinecraftFiles(
  payload: MinecraftFileCompressIn,
) {
  const { data } = await client.post<MinecraftFileOk>(
    `${FILES}/compress`,
    payload,
    { timeout: FILE_TIMEOUT },
  );
  return data;
}

export async function decompressMinecraftFile(directory: string, name: string) {
  const { data } = await client.post<MinecraftFileOk>(
    `${FILES}/decompress`,
    { directory, name },
    { timeout: FILE_TIMEOUT },
  );
  return data;
}

export async function chmodMinecraftFiles(
  directory: string,
  names: string[],
  mode: string,
) {
  const { data } = await client.post<MinecraftFileOk>(`${FILES}/chmod`, {
    directory,
    names,
    mode,
  });
  return data;
}

export async function pullMinecraftFile(
  directory: string,
  url: string,
  filename = "",
) {
  const { data } = await client.post<MinecraftFileOk>(
    `${FILES}/pull`,
    { directory, url, filename },
    { timeout: FILE_TIMEOUT },
  );
  return data;
}

export async function fetchMinecraftModTools(force = false) {
  const { data } = await client.get<MinecraftModTools>(
    "/guides/minecraft/mod-tools",
    { params: { force }, timeout: 45_000 },
  );
  return data;
}

export async function runMinecraftChunkyCommand(
  payload: MinecraftModToolCommandIn,
) {
  const { data } = await client.post<MinecraftModToolCommand>(
    "/guides/minecraft/mod-tools/chunky",
    payload,
    { timeout: 30_000 },
  );
  return data;
}

export async function runMinecraftModToolCommand(
  toolId: string,
  payload: MinecraftModToolExecIn,
) {
  const { data } = await client.post<MinecraftModToolCommand>(
    `/guides/minecraft/mod-tools/${toolId}/command`,
    payload,
    { timeout: 30_000 },
  );
  return data;
}

export async function fetchMinecraftModToolVersions(toolId: string) {
  const { data } = await client.get<MinecraftModToolVersions>(
    `/guides/minecraft/mod-tools/${toolId}/versions`,
    { timeout: 45_000 },
  );
  return data;
}

export async function installMinecraftModTool(
  toolId: string,
  payload: MinecraftModToolInstallIn = {
    version_id: "",
    preset_id: "",
    restart: false,
  },
) {
  const { data } = await client.post<MinecraftModToolInstall>(
    `/guides/minecraft/mod-tools/${toolId}/install`,
    payload,
    { timeout: FILE_TIMEOUT },
  );
  return data;
}

export async function applyMinecraftModToolPreset(toolId: string) {
  const { data } = await client.post<MinecraftModToolPresetApply>(
    `/guides/minecraft/mod-tools/${toolId}/preset/apply`,
    undefined,
    { timeout: 60_000 },
  );
  return data;
}

export async function fetchMinecraftModToolPreset(toolId: string) {
  const { data } = await client.get<MinecraftModToolPreset>(
    `/guides/minecraft/mod-tools/${toolId}/preset`,
  );
  return data;
}

export async function fetchMinecraftModToolPresetKeys(
  toolId: string,
  path: string,
) {
  const { data } = await client.get<MinecraftModToolPresetKeys>(
    `/guides/minecraft/mod-tools/${toolId}/preset/keys`,
    { params: { path } },
  );
  return data;
}

export async function saveMinecraftModToolPreset(
  toolId: string,
  payload: MinecraftModToolPresetIn,
) {
  const { data } = await client.put<MinecraftModToolPreset>(
    `/guides/minecraft/mod-tools/${toolId}/preset`,
    payload,
  );
  return data;
}
