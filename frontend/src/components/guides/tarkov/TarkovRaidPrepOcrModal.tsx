import { Modal, Spin } from "antd";
import { useCallback, useEffect, useState } from "react";
import type { TarkovRaidPrepTask } from "@/api/guidesApi";
import {
  formatRaidPrepOcrProgress,
  isPreferredRaidPrepOcrSize,
  matchRaidPrepTasksFromOcr,
  newRaidPrepOcrIds,
  type RaidPrepOcrMatch,
} from "@/lib/tarkovRaidPrepOcr";
import {
  preloadRaidPrepOcrWorker,
  recognizeRaidPrepTaskScreenshot,
  terminateRaidPrepOcrWorker,
} from "@/lib/tarkovRaidPrepOcrEngine";
import { RAID_PREP_MAX_SELECTED, tarkovReadableName } from "@/lib/tarkovRaidPrep";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { traderDisplayName } from "@/lib/tarkovHomeNav";
import styles from "./TarkovRaidPrepPanel.module.css";

type Phase = "idle" | "working" | "done";

type Props = {
  open: boolean;
  onClose: () => void;
  catalog: Array<
    Pick<
      TarkovRaidPrepTask,
      | "id"
      | "name"
      | "normalized_name"
      | "map_name"
      | "trader_slug"
      | "trader_name"
    >
  >;
  selectedIds: string[];
  /** 用户确认后的任务 id（已过滤未勾选项）；由调用方合并进已有勾选。 */
  onConfirm: (taskIds: string[]) => void | Promise<void>;
  maxSelected?: number;
};

export function TarkovRaidPrepOcrModal({
  open,
  onClose,
  catalog,
  selectedIds,
  onConfirm,
  maxSelected = RAID_PREP_MAX_SELECTED,
}: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [progress, setProgress] = useState("识别中…");
  const [matches, setMatches] = useState<RaidPrepOcrMatch[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);

  const reset = useCallback(() => {
    setPhase("idle");
    setError("");
    setHint("");
    setProgress("识别中…");
    setMatches([]);
    setChecked({});
    setSubmitting(false);
  }, []);

  useEffect(() => {
    if (!open) {
      reset();
      void terminateRaidPrepOcrWorker();
      return;
    }
    preloadRaidPrepOcrWorker();
  }, [open, reset]);

  const runRecognize = useCallback(
    async (file: Blob) => {
      setPhase("working");
      setError("");
      setHint("");
      setProgress("正在加载识别引擎…");
      setMatches([]);
      setChecked({});
      try {
        const result = await recognizeRaidPrepTaskScreenshot(file, {
          onProgress: (status, pct) => {
            setProgress(formatRaidPrepOcrProgress(status, pct));
          },
        });
        if (!result.widescreen) {
          setPhase("done");
          setMatches([]);
          setError("");
          setHint("请使用游戏内任务页的全屏截图（建议 1920×1080 或 2560×1440）");
          return;
        }
        if (!isPreferredRaidPrepOcrSize(result.width, result.height)) {
          setHint(
            `当前 ${result.width}×${result.height}，建议使用 1920×1080 或 2560×1440`,
          );
        }
        const hits = matchRaidPrepTasksFromOcr({
          lines: result.lines,
          catalog,
        });
        // 已勾选的也展示，默认勾上；确认时由 merge 去重
        setMatches(hits);
        const next: Record<string, boolean> = {};
        for (const hit of hits) next[hit.id] = true;
        setChecked(next);
        setPhase("done");
      } catch (err) {
        setPhase("idle");
        setError(err instanceof Error ? err.message : "识别失败，请重试");
      }
    },
    [catalog],
  );

  useEffect(() => {
    if (!open) return undefined;
    const onPaste = (event: ClipboardEvent) => {
      if (phase === "working" || submitting) return;
      const items = event.clipboardData?.items;
      if (items) {
        for (const item of items) {
          if (item.type.startsWith("image/")) {
            const file = item.getAsFile();
            if (file) {
              event.preventDefault();
              void runRecognize(file);
              return;
            }
          }
        }
      }
      event.preventDefault();
      setError("请 Ctrl+V 粘贴截图");
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [open, phase, runRecognize, submitting]);

  const selectedNewCount = matches.filter(
    (row) => checked[row.id] && !selectedIds.includes(row.id),
  ).length;
  const roomLeft = Math.max(0, maxSelected - selectedIds.length);
  const confirmIds = matches
    .filter((row) => checked[row.id])
    .map((row) => row.id);
  const willAdd = newRaidPrepOcrIds(selectedIds, confirmIds).slice(0, roomLeft);

  const handleConfirm = async () => {
    if (!willAdd.length) {
      onClose();
      return;
    }
    setSubmitting(true);
    try {
      await onConfirm(willAdd);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "勾选失败，请重试");
      setSubmitting(false);
    }
  };

  const footer =
    phase === "done" && matches.length > 0 ? (
      <div className={styles.ocrFooter}>
        <button
          type="button"
          className={styles.dockChip}
          disabled={submitting}
          onClick={reset}
        >
          重新识别
        </button>
        <button
          type="button"
          className={styles.dockChip}
          disabled={submitting}
          onClick={onClose}
        >
          取消
        </button>
        <button
          type="button"
          className={`${styles.dockChip} ${styles.dockChipOn}`}
          disabled={submitting || willAdd.length === 0}
          onClick={() => void handleConfirm()}
        >
          {submitting
            ? "处理中…"
            : willAdd.length
              ? `确认勾选 ${willAdd.length} 项`
              : "没有可新增的任务"}
        </button>
      </div>
    ) : phase === "done" ? (
      <div className={styles.ocrFooter}>
        <button type="button" className={styles.dockChip} onClick={onClose}>
          关闭
        </button>
        <button
          type="button"
          className={`${styles.dockChip} ${styles.dockChipOn}`}
          onClick={reset}
        >
          重新识别
        </button>
      </div>
    ) : null;

  return (
    <Modal
      title="截图识别"
      open={open}
      onCancel={onClose}
      footer={footer}
      width={480}
      destroyOnClose
      classNames={{ body: styles.ocrModalBody }}
    >
      {phase === "idle" ? (
        <div className={styles.ocrIdle}>
          <p className={styles.ocrPasteHint}>Ctrl+V粘贴截图进行识别</p>
          {error ? <p className={styles.ocrError}>{error}</p> : null}
        </div>
      ) : null}

      {phase === "working" ? (
        <div className={styles.ocrWorking}>
          <Spin />
          <p className={styles.ocrMeta}>{progress}</p>
          <p className={styles.ocrMeta}>中英模型从本站加载，无需访问外网</p>
        </div>
      ) : null}

      {phase === "done" && matches.length === 0 ? (
        <div className={styles.ocrEmpty}>
          <p className={styles.ocrLead}>
            {hint ||
              "未识别到可勾选的任务。请使用任务页全屏截图后重试。"}
          </p>
          {error ? <p className={styles.ocrError}>{error}</p> : null}
        </div>
      ) : null}

      {phase === "done" && matches.length > 0 ? (
        <div className={styles.ocrResult}>
          {hint ? <p className={styles.ocrMeta}>{hint}</p> : null}
          <p className={styles.ocrLead}>
            识别到 {matches.length} 个任务
            {selectedNewCount
              ? `，其中 ${Math.min(selectedNewCount, roomLeft)} 个可新增`
              : "（均已勾选）"}
            {selectedIds.length >= maxSelected
              ? `；已达上限 ${maxSelected}`
              : ""}
          </p>
          <ul className={styles.ocrList}>
            {matches.map((row) => {
              const already = selectedIds.includes(row.id);
              return (
                <li key={row.id} className={styles.ocrItem}>
                  <label className={styles.ocrItemLabel}>
                    <input
                      type="checkbox"
                      checked={Boolean(checked[row.id])}
                      disabled={already}
                      onChange={(event) =>
                        setChecked((current) => ({
                          ...current,
                          [row.id]: event.target.checked,
                        }))
                      }
                    />
                    {row.trader_slug ? (
                      <TarkovTraderThumb
                        slug={row.trader_slug}
                        size={28}
                        title={traderDisplayName(
                          row.trader_slug,
                          row.trader_name || row.trader_slug,
                        )}
                      />
                    ) : null}
                    <span className={styles.ocrItemName}>
                      {tarkovReadableName(row.name, row.id) || row.name}
                    </span>
                    {already ? (
                      <span className={styles.ocrItemTag}>已选</span>
                    ) : null}
                  </label>
                </li>
              );
            })}
          </ul>
          {error ? <p className={styles.ocrError}>{error}</p> : null}
        </div>
      ) : null}
    </Modal>
  );
}
