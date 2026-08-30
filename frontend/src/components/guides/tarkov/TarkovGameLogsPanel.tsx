import { Alert, Button, Input, Spin, message } from "antd";
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
  readLogsIndex,
  requestLogsDirPermission,
  resolveScreenshotsDirDetailed,
  saveLogsDir,
  saveLogsDisplayPath,
  saveScreenshotsDir,
  saveScreenshotsDisplayPath,
  type ReadableDir,
} from "@/lib/tarkovGameLogAccess";
import {
  TARKOV_LOGS_PATH_HINT,
  TARKOV_SCREENSHOTS_PATH_HINT,
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
  const [shotLabel, setShotLabel] = useState("");
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
      if (!storedShot) {
        setShotPerm("none");
        return;
      }
      shotRef.current = storedShot;
      setShotLabel(storedShotPath || storedShot.name);
      const shotCurrent = await queryLogsDirPermission(storedShot);
      if (cancelled) return;
      if (shotCurrent === "granted") {
        try {
          await loadShots(storedShot);
          setShotPerm("granted");
        } catch {
          if (!cancelled) setShotPerm("prompt");
        }
        return;
      }
      setShotPerm("prompt");
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

  const bindShots = async (opts: {
    existingOnly?: boolean;
  }): Promise<boolean> => {
    if (opts.existingOnly) {
      if (!shotRef.current) return false;
      const next = await ensureGranted(shotRef.current);
      if (next === "granted") {
        await saveScreenshotsDir(shotRef.current);
        await loadShots(shotRef.current);
        setShotPerm("granted");
        return true;
      }
      setShotPerm("prompt");
      setError("浏览器没有批准读取截图目录。");
      return false;
    }
    try {
      const picked = await pickScreenshotsDirectory(shotRef.current);
      const next = await ensureGranted(picked);
      if (next !== "granted") {
        setError("浏览器没有批准读取截图目录。");
        return false;
      }
      shotRef.current = picked;
      await saveScreenshotsDir(picked);
      await loadShots(picked);
      setShotPerm("granted");
      return true;
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
        message.success(
          nextAction === "verify-shots" ? "截图目录校验通过" : "日志目录校验通过",
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
            type={shotPerm === "prompt" ? "primary" : "default"}
            disabled={busy || shotPerm === "none"}
            loading={action === "verify-shots"}
            title="继续读取已保存的截图目录"
            onClick={() => {
              setActive("shots");
              void runBind("verify-shots", () => bindShots({ existingOnly: true }));
            }}
          >
            {shotPerm === "prompt" ? "继续授权" : "校验"}
          </Button>
        </div>
        <p className={styles.hint}>
          常见位置：{TARKOV_SCREENSHOTS_PATH_HINT}
          <br />
          战局里用游戏截图键（Print Screen）会把坐标写进文件名，开房间时队友能在地图上看到你的点。
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
