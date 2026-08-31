import { Alert, Button, Input, InputNumber, Spin, message } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  displayPathForResolved,
  isFileSystemAccessSupported,
  isPickerAbort,
  loadStoredLogsDir,
  loadStoredLogsPath,
  loadStoredScreenshotsDir,
  loadStoredScreenshotsPath,
  pickLogsDirectory,
  pickScreenshotsDirectory,
  queryLogsDirPermission,
  queryScreenshotsDirPermission,
  readLogsIndex,
  requestLogsDirPermission,
  requestScreenshotsDirPermission,
  resolveScreenshotsDirDetailed,
  saveLogsDir,
  saveLogsDisplayPath,
  saveScreenshotsDir,
  saveScreenshotsDisplayPath,
  screenshotsDirCanWrite,
  type ReadableDir,
} from "@/lib/tarkovGameLogAccess";
import {
  TARKOV_LOGS_PATH_HINT,
  TARKOV_SCREENSHOT_PRUNE_KEEP_MAX,
  TARKOV_SCREENSHOT_PRUNE_KEEP_MIN,
  TARKOV_SCREENSHOTS_PATH_HINT,
  loadScreenshotPrunePref,
  saveScreenshotPrunePref,
  screenshotPruneVerifyResult,
} from "@/lib/tarkovGameLogs";
import styles from "./TarkovGameLogsPanel.module.css";

type Perm = "unknown" | "none" | "prompt" | "granted";
type BindField = "shots" | "logs";
type Action =
  | ""
  | "replace-shots"
  | "verify-shots"
  | "replace-logs"
  | "verify-logs";

function friendlyError(error: unknown, fallback: string): string {
  if (isPickerAbort(error)) return "";
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export function TarkovGameLogsPanel() {
  const supported = isFileSystemAccessSupported();
  const handleRef = useRef<ReadableDir | null>(null);
  const shotRef = useRef<ReadableDir | null>(null);
  const [perm, setPerm] = useState<Perm>("unknown");
  const [dirName, setDirName] = useState("");
  const [shotPerm, setShotPerm] = useState<Perm>("unknown");
  const [shotCanWrite, setShotCanWrite] = useState(false);
  const [shotLabel, setShotLabel] = useState("");
  const [pruneEnabled, setPruneEnabled] = useState(
    () => loadScreenshotPrunePref().enabled,
  );
  const [pruneKeepMax, setPruneKeepMax] = useState(
    () => loadScreenshotPrunePref().keepMax,
  );
  const [action, setAction] = useState<Action>("");
  const [error, setError] = useState("");
  const [active, setActive] = useState<BindField>("shots");
  const dirNameRef = useRef("");
  const shotLabelRef = useRef("");

  const busy = Boolean(action);
  dirNameRef.current = dirName;
  shotLabelRef.current = shotLabel;

  const ensureGranted = useCallback(async (handle: ReadableDir) => {
    const current = await queryLogsDirPermission(handle);
    if (current === "granted") return "granted" as const;
    return requestLogsDirPermission(handle);
  }, []);

  const loadSessions = useCallback(async (handle: ReadableDir) => {
    const { resolved } = await readLogsIndex(handle);
    const nextPath = await displayPathForResolved(
      handle,
      resolved,
      dirNameRef.current,
    );
    setDirName(nextPath);
    await saveLogsDisplayPath(nextPath);
  }, []);

  const loadShots = useCallback(async (handle: ReadableDir) => {
    const resolved = await resolveScreenshotsDirDetailed(handle);
    const nextPath = await displayPathForResolved(
      handle,
      resolved,
      shotLabelRef.current,
    );
    setShotLabel(nextPath);
    await saveScreenshotsDisplayPath(nextPath);
  }, []);

  const bootGranted = useCallback(
    async (handle: ReadableDir) => {
      handleRef.current = handle;
      setPerm("granted");
      await loadSessions(handle);
    },
    [loadSessions],
  );

  useEffect(() => {
    if (!supported) {
      setPerm("none");
      setShotPerm("none");
      return;
    }
    let cancelled = false;
    void (async () => {
      const [stored, storedShot, storedPath, storedShotPath] = await Promise.all([
        loadStoredLogsDir(),
        loadStoredScreenshotsDir(),
        loadStoredLogsPath(),
        loadStoredScreenshotsPath(),
      ]);
      if (cancelled) return;
      if (!stored) {
        setPerm("none");
      } else {
        handleRef.current = stored;
        setDirName(storedPath || stored.name);
        const current = await queryLogsDirPermission(stored);
        if (cancelled) return;
        if (current === "granted") {
          try {
            await bootGranted(stored);
          } catch (err) {
            if (!cancelled) {
              setPerm("prompt");
              setError(friendlyError(err, "无法读取已授权目录"));
            }
          }
        } else {
          setPerm("prompt");
        }
      }
      const prune = loadScreenshotPrunePref();
      if (!cancelled) {
        setPruneEnabled(prune.enabled);
        setPruneKeepMax(prune.keepMax);
      }
      if (!storedShot) {
        setShotPerm("none");
        setShotCanWrite(false);
        return;
      }
      shotRef.current = storedShot;
      setShotLabel(storedShotPath || storedShot.name);
      const shotCurrent = await queryScreenshotsDirPermission(storedShot);
      if (cancelled) return;
      if (shotCurrent === "granted") {
        try {
          await loadShots(storedShot);
          setShotPerm("granted");
          setShotCanWrite(await screenshotsDirCanWrite(storedShot));
        } catch {
          if (!cancelled) {
            setShotPerm("prompt");
            setShotCanWrite(false);
          }
        }
        return;
      }
      setShotPerm("prompt");
      setShotCanWrite(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [supported, bootGranted, loadShots]);

  const bindLogs = async (opts: {
    existingOnly?: boolean;
  }): Promise<boolean> => {
    if (opts.existingOnly) {
      if (!handleRef.current) return false;
      const next = await ensureGranted(handleRef.current);
      if (next === "granted") {
        await saveLogsDir(handleRef.current);
        await bootGranted(handleRef.current);
        return true;
      }
      setPerm("prompt");
      setError("浏览器没有批准读取该目录。");
      return false;
    }
    try {
      const picked = await pickLogsDirectory(handleRef.current);
      const next = await ensureGranted(picked);
      if (next !== "granted") {
        setError("浏览器没有批准读取该目录。");
        return false;
      }
      await saveLogsDir(picked);
      await bootGranted(picked);
      return true;
    } catch (err) {
      if (isPickerAbort(err)) return false;
      throw err;
    }
  };

  const finishShotBind = async (handle: ReadableDir): Promise<boolean> => {
    await saveScreenshotsDir(handle);
    await loadShots(handle);
    const canWrite = await screenshotsDirCanWrite(handle);
    setShotPerm("granted");
    setShotCanWrite(canWrite);
    const check = screenshotPruneVerifyResult({
      pruneEnabled: loadScreenshotPrunePref().enabled,
      canWrite,
    });
    if (!check.ok) {
      setError(check.text);
      return false;
    }
    return true;
  };

  const bindShots = async (opts: {
    existingOnly?: boolean;
  }): Promise<boolean> => {
    if (opts.existingOnly) {
      if (!shotRef.current) return false;
      const next = await requestScreenshotsDirPermission(shotRef.current);
      if (next === "granted") {
        return finishShotBind(shotRef.current);
      }
      setShotPerm("prompt");
      setShotCanWrite(false);
      setError("浏览器没有批准读取截图目录。");
      return false;
    }
    try {
      const picked = await pickScreenshotsDirectory(shotRef.current);
      const next = await requestScreenshotsDirPermission(picked);
      if (next !== "granted") {
        setError("浏览器没有批准读取截图目录。");
        return false;
      }
      shotRef.current = picked;
      return finishShotBind(picked);
    } catch (err) {
      if (isPickerAbort(err)) return false;
      throw err;
    }
  };

  const runBind = async (nextAction: Action, work: () => Promise<boolean>) => {
    if (!supported) return;
    setError("");
    setAction(nextAction);
    try {
      const ok = await work();
      if (ok && (nextAction === "verify-shots" || nextAction === "verify-logs")) {
        const shotOk = screenshotPruneVerifyResult({
          pruneEnabled: loadScreenshotPrunePref().enabled,
          canWrite: shotRef.current
            ? await screenshotsDirCanWrite(shotRef.current)
            : false,
        });
        message.success(
          nextAction === "verify-shots"
            ? shotOk.text
            : "日志目录校验通过",
        );
      }
    } catch (err) {
      const text = friendlyError(err, "授权目录失败");
      if (text) setError(text);
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

  if (perm === "unknown") {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
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
            title="浏览器选目录拿不到盘符，可在此补全完整路径"
            className={`${styles.pathInput}${active === "shots" ? ` ${styles.pathOn}` : ""}`}
            onFocus={() => setActive("shots")}
            onChange={(event) => setShotLabel(event.target.value)}
            onBlur={() => {
              void saveScreenshotsDisplayPath(shotLabelRef.current);
            }}
          />
          <Button
            className={styles.sideBtn}
            disabled={busy}
            loading={action === "replace-shots"}
            title="重新选择本机目录，选中上一级即可自动往下走"
            onClick={() => {
              setActive("shots");
              void runBind("replace-shots", () => bindShots({}));
            }}
          >
            更换
          </Button>
          <Button
            className={styles.sideBtn}
            type={
              shotPerm === "prompt" || (pruneEnabled && !shotCanWrite)
                ? "primary"
                : "default"
            }
            disabled={busy || shotPerm === "none"}
            loading={action === "verify-shots"}
            title={
              pruneEnabled
                ? "校验读取，并检查删除所需的写入授权"
                : "继续读取已保存的截图目录"
            }
            onClick={() => {
              setActive("shots");
              void runBind("verify-shots", () => bindShots({ existingOnly: true }));
            }}
          >
            {shotPerm === "prompt" ? "继续授权" : "校验"}
          </Button>
        </div>
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
          战局里用游戏截图键（Print Screen）会把坐标写进文件名，开房间时队友能在地图上看到你的点。页面只读最新一张。请只选 Screenshots 文件夹。
          {pruneEnabled
            ? shotCanWrite
              ? ` 已具备写入授权，超过 ${pruneKeepMax} 张游戏截图时会删掉最旧的。`
              : " 开启删除后需要写入授权：旧的只读授权不够，请点「校验」或「更换」，弹窗里选「查看并编辑」。"
            : ""}
          {shotPerm === "prompt"
            ? " 目录已保存，点「继续授权」即可，不用重新选文件夹。"
            : ""}
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
            title="浏览器选目录拿不到盘符，可在此补全完整路径"
            className={`${styles.pathInput}${active === "logs" ? ` ${styles.pathOn}` : ""}`}
            onFocus={() => setActive("logs")}
            onChange={(event) => setDirName(event.target.value)}
            onBlur={() => {
              void saveLogsDisplayPath(dirNameRef.current);
            }}
          />
          <Button
            className={styles.sideBtn}
            disabled={busy}
            loading={action === "replace-logs"}
            title="重新选择本机目录，选中上一级即可自动往下走"
            onClick={() => {
              setActive("logs");
              void runBind("replace-logs", () => bindLogs({}));
            }}
          >
            更换
          </Button>
          <Button
            className={styles.sideBtn}
            disabled={busy || perm === "none"}
            loading={action === "verify-logs"}
            title="重新授权并读取最新一条日志"
            onClick={() => {
              setActive("logs");
              void runBind("verify-logs", () => bindLogs({ existingOnly: true }));
            }}
          >
            校验
          </Button>
        </div>
        <p className={styles.hint}>常见位置：{TARKOV_LOGS_PATH_HINT}</p>
      </div>
    </div>
  );
}
