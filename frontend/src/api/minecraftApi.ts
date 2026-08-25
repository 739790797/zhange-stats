import { client } from "./http";
import type { components } from "./generated/schema";

export type MinecraftStatus = components["schemas"]["MinecraftStatusOut"];
export type MinecraftPlayer = components["schemas"]["MinecraftPlayerOut"];
export type MinecraftPowerSignal =
  components["schemas"]["MinecraftPowerIn"]["signal"];
export type MinecraftPowerResult = components["schemas"]["MinecraftPowerOut"];
export type MinecraftPlaybook = components["schemas"]["MinecraftPlaybookOut"];
export type MinecraftProfile = components["schemas"]["MinecraftProfileOut"];
export type MinecraftProfileUpdate =
  components["schemas"]["MinecraftProfileUpdate"];
export type MinecraftModPin = components["schemas"]["MinecraftModPinOut"];
export type MinecraftOverride = components["schemas"]["MinecraftOverrideOut"];
export type MinecraftApplyResult = components["schemas"]["MinecraftApplyOut"];
export type MinecraftEggs = components["schemas"]["MinecraftEggsOut"];
export type MinecraftLiveConfig =
  components["schemas"]["MinecraftLiveConfigOut"];
export type MinecraftPlaybookStages =
  components["schemas"]["MinecraftPlaybookStagesOut"];
export type MinecraftGameVersion =
  components["schemas"]["MinecraftGameVersionOut"];
export type MinecraftModSearchHit =
  components["schemas"]["MinecraftModSearchHitOut"];
export type MinecraftModUpdate = components["schemas"]["MinecraftModUpdateOut"];
export type MinecraftApplied = components["schemas"]["MinecraftAppliedOut"];
export type MinecraftFileEntry = components["schemas"]["MinecraftFileEntryOut"];
export type MinecraftFileList = components["schemas"]["MinecraftFileListOut"];
export type MinecraftFileContents =
  components["schemas"]["MinecraftFileContentsOut"];
export type MinecraftFileOk = components["schemas"]["MinecraftFileOkOut"];
export type MinecraftFileDownload =
  components["schemas"]["MinecraftFileDownloadOut"];
export type MinecraftModTools = components["schemas"]["MinecraftModToolsOut"];
export type MinecraftModTool = components["schemas"]["MinecraftModToolOut"];
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
export type MinecraftModToolInstall =
  components["schemas"]["MinecraftModToolInstallOut"];
export type MinecraftModToolInstallIn =
  components["schemas"]["MinecraftModToolInstallIn"];
export type MinecraftModToolVersions =
  components["schemas"]["MinecraftModToolVersionsOut"];
export type MinecraftModToolPresetApply =
  components["schemas"]["MinecraftModToolPresetApplyOut"];
export type MinecraftModToolPresetDraft =
  components["schemas"]["MinecraftModToolPresetDraftOut"];
export type MinecraftModToolPresetDraftIn =
  components["schemas"]["MinecraftModToolPresetDraftIn"];
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

export async function fetchMinecraftProfile() {
  const { data } = await client.get<MinecraftProfile>(
    "/guides/minecraft/profile",
  );
  return data;
}

export async function updateMinecraftProfile(payload: MinecraftProfileUpdate) {
  const { data } = await client.put<MinecraftProfile>(
    "/guides/minecraft/profile",
    payload,
  );
  return data;
}

const PLAYBOOK_TIMEOUT = 360_000;

export async function applyMinecraftProfile() {
  const { data } = await client.post<MinecraftApplyResult>(
    "/guides/minecraft/apply",
    {},
    { timeout: PLAYBOOK_TIMEOUT },
  );
  return data;
}

export async function bootstrapMinecraftServer(payload?: {
  startup?: string;
  egg_id?: number | null;
}) {
  const { data } = await client.post<MinecraftApplyResult>(
    "/guides/minecraft/bootstrap",
    payload || {},
    { timeout: PLAYBOOK_TIMEOUT },
  );
  return data;
}

export async function syncMinecraftEgg(payload?: {
  startup?: string;
  egg_id?: number | null;
}) {
  const { data } = await client.post<MinecraftEggs>(
    "/guides/minecraft/sync-egg",
    payload || {},
    { timeout: 60_000 },
  );
  return data;
}

export async function syncMinecraftMods() {
  const { data } = await client.post<MinecraftApplyResult>(
    "/guides/minecraft/sync-mods",
    {},
    { timeout: PLAYBOOK_TIMEOUT },
  );
  return data;
}

export async function applyMinecraftConfig() {
  const { data } = await client.post<MinecraftApplyResult>(
    "/guides/minecraft/apply-config",
    {},
    { timeout: PLAYBOOK_TIMEOUT },
  );
  return data;
}

export async function fetchMinecraftEggs(loader = "") {
  const { data } = await client.get<MinecraftEggs>("/guides/minecraft/eggs", {
    params: loader ? { loader } : {},
    timeout: 30_000,
  });
  return data;
}

export async function fetchMinecraftLiveConfigs() {
  const { data } = await client.get<MinecraftLiveConfig[]>(
    "/guides/minecraft/live-configs",
    { timeout: 45_000 },
  );
  return data;
}

export async function fetchMinecraftGameVersions() {
  const { data } = await client.get<MinecraftGameVersion[]>(
    "/guides/minecraft/game-versions",
    { timeout: 20_000 },
  );
  return data;
}

export async function fetchMinecraftLoaderVersions(
  loader: string,
  mcVersion: string,
) {
  const { data } = await client.get<{ versions: string[] }>(
    "/guides/minecraft/loader-versions",
    { params: { loader, mc_version: mcVersion }, timeout: 20_000 },
  );
  return data.versions;
}

export async function searchMinecraftMods(opts: {
  q: string;
  loader: string;
  mcVersion: string;
}) {
  const { data } = await client.get<{ hits: MinecraftModSearchHit[] }>(
    "/guides/minecraft/mods/search",
    {
      params: {
        q: opts.q,
        loader: opts.loader,
        mc_version: opts.mcVersion,
      },
      timeout: 20_000,
    },
  );
  return data.hits;
}

export async function fetchMinecraftModVersions(opts: {
  projectId: string;
  loader: string;
  mcVersion: string;
}) {
  const { data } = await client.get<MinecraftModPin[]>(
    "/guides/minecraft/mods/versions",
    {
      params: {
        project_id: opts.projectId,
        loader: opts.loader,
        mc_version: opts.mcVersion,
      },
      timeout: 20_000,
    },
  );
  return data;
}

export async function pinMinecraftMod(projectId: string, versionId: string) {
  const { data } = await client.post<MinecraftModPin>(
    "/guides/minecraft/mods/pin",
    { project_id: projectId, version_id: versionId },
    { timeout: 20_000 },
  );
  return data;
}

export async function fetchMinecraftModUpdates() {
  const { data } = await client.get<MinecraftModUpdate[]>(
    "/guides/minecraft/mods/updates",
    { timeout: 60_000 },
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

export async function uploadMinecraftFile(directory: string, file: File) {
  const form = new FormData();
  form.append("directory", directory);
  form.append("file", file);
  const { data } = await client.post<MinecraftFileOk>(`${FILES}/upload`, form, {
    timeout: FILE_TIMEOUT,
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

export async function applyMinecraftModToolPreset(
  toolId: string,
  presetId = "",
) {
  const { data } = await client.post<MinecraftModToolPresetApply>(
    `/guides/minecraft/mod-tools/${toolId}/config`,
    { preset_id: presetId },
    { timeout: 60_000 },
  );
  return data;
}

export async function fetchMinecraftModToolPreset(
  toolId: string,
  presetId: string,
) {
  const { data } = await client.get<MinecraftModToolPresetDraft>(
    `/guides/minecraft/mod-tools/${toolId}/presets/${encodeURIComponent(presetId)}`,
  );
  return data;
}

export async function saveMinecraftModToolPreset(
  toolId: string,
  presetId: string,
  payload: MinecraftModToolPresetDraftIn,
) {
  const { data } = await client.put<MinecraftModToolPresetDraft>(
    `/guides/minecraft/mod-tools/${toolId}/presets/${encodeURIComponent(presetId)}`,
    payload,
  );
  return data;
}
