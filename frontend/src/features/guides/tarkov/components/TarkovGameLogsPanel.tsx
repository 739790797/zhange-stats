import { Alert, Button, Input, InputNumber, message } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  displayPathForResolved,
  isFileSystemAccessSupported,
  isPickerAbort,
  loadTarkovDirectoryBinding,
  pickLogsDirectory,
  pickScreenshotsDirectory,
  queryLogsDirPermission,
  queryScreenshotsDirPermission,
  requestLogsDirPermission,
  requestScreenshotsDirPermission,
  resolveLogsDirDetailed,
  resolveScreenshotsDirDetailed,
  saveTarkovDirectoryBinding,
  saveTarkovDirectoryDisplayPath,
  screenshotsDirCanWrite,
  withTarkovDirectoryTimeout,
  type ReadableDir,
  type TarkovDirectoryKind,
} from "@/features/guides/tarkov/model/tarkovGameLogAccess";
import {
  TARKOV_LOGS_PATH_HINT,
  TARKOV_SCREENSHOT_PRUNE_KEEP_MAX,
  TARKOV_SCREENSHOT_PRUNE_KEEP_MIN,
  TARKOV_SCREENSHOTS_PATH_HINT,
  loadScreenshotPrunePref,
  saveScreenshotPrunePref,
  screenshotPruneVerifyResult,
} from "@/features/guides/tarkov/model/tarkovGameLogs";
import {
  loadOfflineMapId,
  saveOfflineMapId,
  TARKOV_OFFLINE_MAP_EVENT,
} from "@/features/guides/tarkov/model/tarkovOfflineMap";
import { raidPrepMapOptions } from "@/features/guides/tarkov/model/tarkovRaidPrep";
import styles from "./TarkovGameLogsPanel.module.css";

type Perm = "unknown" | "none" | "prompt" | "granted";
type BindField = "shots" | "logs";
type Action = "" | "replace-shots" | "verify-shots" | "replace-logs" | "verify-logs";

function friendlyError(error: unknown, fallback: string): string {
  if (error instanceof DOMException) {
    if (error.name === "NotFoundError") return "找不到本机目录，请点「更换」重新选择。";
    if (error.name === "NotAllowedError" || error.name === "SecurityError") {
      return "浏览器无法读取此目录，请继续授权或重新选择目录。";
    }
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export function TarkovGameLogsPanel() {
  const supported = isFileSystemAccessSupported();
  const pathInputTitle = "浏览器选目录拿不到盘符，可在此补全完整路径";
  const handleRef = useRef<ReadableDir | null>(null);
  const shotRef = useRef<ReadableDir | null>(null);
  const [perm, setPerm] = useState<Perm>("unknown");
  const [dirName, setDirName] = useState("");
  const [shotPerm, setShotPerm] = useState<Perm>("unknown");
  const [shotCanWrite, setShotCanWrite] = useState(false);
  const [shotLabel, setShotLabel] = useState("");
  const [pruneEnabled, setPruneEnabled] = useState(() => loadScreenshotPrunePref().enabled);
  const [pruneKeepMax, setPruneKeepMax] = useState(() => loadScreenshotPrunePref().keepMax);
  const [action, setAction] = useState<Action>("");
  const [error, setError] = useState("");
  const [restoreErrors, setRestoreErrors] = useState({ logs: "", screenshots: "" });
  const [active, setActive] = useState<BindField>("shots");
  const [offlineMapId, setOfflineMapId] = useState(loadOfflineMapId);
  const savedPaths = useRef({ logs: "", screenshots: "" });

  const mapOptions = useMemo(() => raidPrepMapOptions(), []);

  useEffect(() => {
    const onOfflineMap = () => setOfflineMapId(loadOfflineMapId());
    window.addEventListener(TARKOV_OFFLINE_MAP_EVENT, onOfflineMap);
    return () => {
      window.removeEventListener(TARKOV_OFFLINE_MAP_EVENT, onOfflineMap);
    };
  }, []);

  const busy = Boolean(action);

  useEffect(() => {
    if (!supported) return;
    let cancelled = false;
    const restore = async (kind: TarkovDirectoryKind) => {
      const isShots = kind === "screenshots";
      const setPermission = isShots ? setShotPerm : setPerm;
      const handleRefForKind = isShots ? shotRef : handleRef;
      try {
        const { handle, path } = await loadTarkovDirectoryBinding(kind);
        if (cancelled) return;
        const label = path || handle?.name || "";
        savedPaths.current[kind] = label;
        handleRefForKind.current = handle;
        (isShots ? setShotLabel : setDirName)(label);
        if (!handle) {
          setPermission("none");
          return;
        }
        const query = isShots ? queryScreenshotsDirPermission : queryLogsDirPermission;
        const permission = await query(handle);
        if (cancelled) return;
        setPermission(permission === "granted" ? "granted" : "prompt");
        if (isShots && permission === "granted") {
          const canWrite = await screenshotsDirCanWrite(handle);
          if (!cancelled && shotRef.current === handle) setShotCanWrite(canWrite);
        }
      } catch (err) {
        if (cancelled) return;
        setPermission(handleRefForKind.current ? "prompt" : "none");
        setRestoreErrors((prev) => ({
          ...prev,
          [kind]: friendlyError(err, "无法恢复目录授权，请重新选择目录。"),
        }));
      }
    };
    void restore("logs");
    void restore("screenshots");
    return () => {
      cancelled = true;
    };
  }, [supported]);

  const saveDisplayPath = async (kind: TarkovDirectoryKind, path: string) => {
    if (savedPaths.current[kind] === path) return;
    try {
      await saveTarkovDirectoryDisplayPath(kind, path);
      savedPaths.current[kind] = path;
    } catch (err) {
      setError(friendlyError(err, "无法保存显示路径。"));
    }
  };

  const bindLogs = async (existingOnly: boolean): Promise<boolean> => {
    const handle = existingOnly ? handleRef.current : await pickLogsDirectory(handleRef.current);
    if (!handle) return false;
    if ((await requestLogsDirPermission(handle)) !== "granted") {
      if (existingOnly) setPerm("prompt");
      setError("浏览器没有批准读取日志目录。");
      return false;
    }
    const path = await withTarkovDirectoryTimeout(async () =>
      displayPathForResolved(
        handle,
        await resolveLogsDirDetailed(handle),
        existingOnly ? dirName : "",
      ),
    );
    await saveTarkovDirectoryBinding("logs", handle, path);
    savedPaths.current.logs = path;
    handleRef.current = handle;
    setDirName(path);
    setPerm("granted");
    return true;
  };

  const bindShots = async (existingOnly: boolean): Promise<boolean> => {
    const mode = pruneEnabled ? "readwrite" : "read";
    const handle = existingOnly
      ? shotRef.current
      : await pickScreenshotsDirectory(shotRef.current, mode);
    if (!handle) return false;
    if ((await requestScreenshotsDirPermission(handle, mode)) !== "granted") {
      if (existingOnly) {
        setShotPerm("prompt");
        setShotCanWrite(false);
      }
      setError("浏览器没有批准读取截图目录。");
      return false;
    }
    const path = await withTarkovDirectoryTimeout(async () =>
      displayPathForResolved(
        handle,
        await resolveScreenshotsDirDetailed(handle),
        existingOnly ? shotLabel : "",
      ),
    );
    await saveTarkovDirectoryBinding("screenshots", handle, path);
    savedPaths.current.screenshots = path;
    shotRef.current = handle;
    setShotLabel(path);
    setShotPerm("granted");
    const canWrite = await screenshotsDirCanWrite(handle);
    setShotCanWrite(canWrite);
    const check = screenshotPruneVerifyResult({ pruneEnabled, canWrite });
    if (!check.ok) setError(check.text);
    if (check.ok && existingOnly) message.success(check.text);
    return check.ok;
  };

  const runBind = async (nextAction: Action, work: () => Promise<boolean>) => {
    const kind = nextAction.endsWith("shots") ? "screenshots" : "logs";
    setRestoreErrors((prev) => ({ ...prev, [kind]: "" }));
    setError("");
    setAction(nextAction);
    try {
      if ((await work()) && nextAction === "verify-logs") message.success("日志目录校验通过");
    } catch (err) {
      if (!isPickerAbort(err)) {
        setError(friendlyError(err, "授权目录失败，请重新选择目录。"));
      }
    } finally {
      setAction("");
    }
  };

  if (!supported) {
    return (
      <Alert
        type="warning"
        showIcon
        message="当前浏览器不能授权本地目录"
        description="请用 Chrome 或 Edge 打开本页。Firefox / Safari 还没有完整的目录授权接口。"
      />
    );
  }

  return (
    <div className={styles.bind}>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <div className={styles.row}>
        <label className={styles.label} htmlFor="tarkov-bind-shots">
          截图目录
        </label>
        <div className={styles.field}>
          <Input
            id="tarkov-bind-shots"
            value={shotLabel}
            placeholder={TARKOV_SCREENSHOTS_PATH_HINT}
            title={pathInputTitle}
            className={`${styles.pathInput}${active === "shots" ? ` ${styles.pathOn}` : ""}`}
            onFocus={() => setActive("shots")}
            disabled={shotPerm === "unknown"}
            onChange={(event) => setShotLabel(event.target.value)}
            onBlur={() => void saveDisplayPath("screenshots", shotLabel)}
          />
          <Button
            className={styles.sideBtn}
            disabled={busy || shotPerm === "unknown"}
            loading={action === "replace-shots"}
            title="重新选择本机目录，选中上一级即可自动往下走"
            onClick={() => {
              setActive("shots");
              void runBind("replace-shots", () => bindShots(false));
            }}
          >
            更换
          </Button>
          <Button
            className={styles.sideBtn}
            type={shotPerm === "prompt" || (pruneEnabled && !shotCanWrite) ? "primary" : "default"}
            disabled={busy || shotPerm === "none" || shotPerm === "unknown"}
            loading={action === "verify-shots"}
            title={pruneEnabled ? "校验读取，并检查删除所需的写入授权" : "继续读取已保存的截图目录"}
            onClick={() => {
              setActive("shots");
              void runBind("verify-shots", () => bindShots(true));
            }}
          >
            {shotPerm === "prompt" ? "继续授权" : "校验"}
          </Button>
        </div>
        {restoreErrors.screenshots ? (
          <Alert type="warning" showIcon message={restoreErrors.screenshots} />
        ) : null}
        {shotPerm === "unknown" ? (
          <p role="status" className={styles.hint}>
            正在恢复截图目录授权…
          </p>
        ) : null}
        <div className={styles.pruneRow}>
          <label className={styles.pruneLabel} htmlFor="tarkov-shot-prune">
            <input
              id="tarkov-shot-prune"
              className={styles.pruneCheck}
              type="checkbox"
              checked={pruneEnabled}
              onChange={(event) => {
                const enabled = event.target.checked;
                const next = saveScreenshotPrunePref({
                  enabled,
                  keepMax: pruneKeepMax,
                });
                setPruneEnabled(next.enabled);
                setPruneKeepMax(next.keepMax);
                if (enabled && !shotCanWrite) {
                  message.warning(
                    "删除旧截图需要新的目录写入授权，请点「校验」或「更换」，并在弹窗里允许查看并编辑。",
                  );
                }
              }}
            />
            <span>截图多于</span>
          </label>
          <InputNumber
            className={styles.pruneInput}
            min={TARKOV_SCREENSHOT_PRUNE_KEEP_MIN}
            max={TARKOV_SCREENSHOT_PRUNE_KEEP_MAX}
            value={pruneKeepMax}
            disabled={!pruneEnabled}
            onChange={(value) => {
              const next = saveScreenshotPrunePref({
                enabled: pruneEnabled,
                keepMax: Number(value),
              });
              setPruneKeepMax(next.keepMax);
            }}
          />
          <span>张时删除旧图</span>
        </div>
        <p className={styles.hint}>
          常见位置：{TARKOV_SCREENSHOTS_PATH_HINT}
          <br />
          战局里用游戏截图键（Print
          Screen）会把坐标写进文件名。开房间后，用同一账号在手机打开该房间即可当第二块地图；队友也能看到。页面只读最新一张。请只选
          Screenshots 文件夹。
          {pruneEnabled
            ? shotCanWrite
              ? ` 已具备写入授权，超过 ${pruneKeepMax} 张游戏截图时会删掉最旧的。`
              : " 开启删除后需要写入授权：旧的只读授权不够，请点「校验」或「更换」，弹窗里选「查看并编辑」。"
            : ""}
          {shotPerm === "prompt" ? " 目录已保存，点「继续授权」即可，不用重新选文件夹。" : ""}
        </p>
      </div>
      <div className={styles.row}>
        <label className={styles.label} htmlFor="tarkov-bind-logs">
          日志目录
        </label>
        <div className={styles.field}>
          <Input
            id="tarkov-bind-logs"
            value={dirName}
            placeholder={TARKOV_LOGS_PATH_HINT}
            title={pathInputTitle}
            className={`${styles.pathInput}${active === "logs" ? ` ${styles.pathOn}` : ""}`}
            onFocus={() => setActive("logs")}
            disabled={perm === "unknown"}
            onChange={(event) => setDirName(event.target.value)}
            onBlur={() => void saveDisplayPath("logs", dirName)}
          />
          <Button
            className={styles.sideBtn}
            disabled={busy || perm === "unknown"}
            loading={action === "replace-logs"}
            title="重新选择本机目录，选中上一级即可自动往下走"
            onClick={() => {
              setActive("logs");
              void runBind("replace-logs", () => bindLogs(false));
            }}
          >
            更换
          </Button>
          <Button
            className={styles.sideBtn}
            disabled={busy || perm === "none" || perm === "unknown"}
            loading={action === "verify-logs"}
            title="重新授权并读取最新一条日志"
            onClick={() => {
              setActive("logs");
              void runBind("verify-logs", () => bindLogs(true));
            }}
          >
            校验
          </Button>
        </div>
        {restoreErrors.logs ? <Alert type="warning" showIcon message={restoreErrors.logs} /> : null}
        {perm === "unknown" ? (
          <p role="status" className={styles.hint}>
            正在恢复日志目录授权…
          </p>
        ) : null}
        <p className={styles.hint}>常见位置：{TARKOV_LOGS_PATH_HINT}</p>
      </div>
      <div className={styles.row}>
        <label className={styles.label} htmlFor="tarkov-offline-map">
          离线地图
        </label>
        <select
          id="tarkov-offline-map"
          className={styles.mapSelect}
          value={offlineMapId}
          onChange={(event) => setOfflineMapId(saveOfflineMapId(event.target.value))}
        >
          <option value="">日志有图才切</option>
          {mapOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
        <p className={styles.hint}>
          本地 / 离线战局常常没有
          Location。选好地图后，进图或离线开战时会挂截图坐标；回菜单不会强切。
        </p>
      </div>
    </div>
  );
}
