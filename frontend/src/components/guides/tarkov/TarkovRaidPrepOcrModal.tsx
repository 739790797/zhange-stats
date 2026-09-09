import { Modal, Spin } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  recognizeTarkovRaidPrep,
  type TarkovRaidPrepOcrMatch,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { formatKeyOcrEngines } from "@/lib/tarkovOcr";
import { newRaidPrepOcrIds } from "@/lib/tarkovRaidPrepOcr";
import { RAID_PREP_MAX_SELECTED, tarkovReadableName } from "@/lib/tarkovRaidPrep";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { traderDisplayName } from "@/lib/tarkovHomeNav";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovRaidPrepPanel.module.css";

type Phase = "idle" | "working" | "done";

type Props = {
  open: boolean;
  onClose: () => void;
  mapSlug: string;
  selectedIds: string[];
  /** 用户确认后的任务 id（已过滤未勾选项）；由调用方合并进已有勾选。 */
  onConfirm: (taskIds: string[]) => void | Promise<void>;
  maxSelected?: number;
};

export function TarkovRaidPrepOcrModal({
  open,
  onClose,
  mapSlug,
  selectedIds,
  onConfirm,
  maxSelected = RAID_PREP_MAX_SELECTED,
}: Props) {
  const user = useAuthStore((s) => s.user);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [progress, setProgress] = useState("正在识别任务名…");
  const [matches, setMatches] = useState<TarkovRaidPrepOcrMatch[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setPhase("idle");
    setError("");
    setHint("");
    setProgress("正在识别任务名…");
    setMatches([]);
    setChecked({});
    setSubmitting(false);
  }, []);

  useEffect(() => {
    if (!open) reset();
  }, [open, reset]);

  const runRecognize = useCallback(
    async (file: Blob) => {
      if (!user) {
        setError("登录后才能截图识别");
        return;
      }
      const slug = (mapSlug || "").trim();
      if (!slug) {
        setError("请先选择地图");
        return;
      }
      setPhase("working");
      setError("");
      setHint("");
      setProgress("正在识别任务名…");
      setMatches([]);
      setChecked({});
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      try {
        const result = await recognizeTarkovRaidPrep(file, slug, {
          signal: ac.signal,
        });
        if (ac.signal.aborted) return;
        if (!result.widescreen) {
          setPhase("done");
          setMatches([]);
          setHint("请使用游戏内任务页的全屏截图（建议 1920×1080 或 2560×1440）");
          return;
        }
        const hits = result.matches || [];
        setMatches(hits);
        const next: Record<string, boolean> = {};
        for (const hit of hits) next[hit.id] = true;
        setChecked(next);
        setPhase("done");
        const engineHint = formatKeyOcrEngines(result.engines);
        const sizeHint = result.preferred_size
          ? ""
          : `当前 ${result.width}×${result.height}，建议使用 1920×1080 或 2560×1440`;
        const parts = [
          engineHint ? `已用 ${engineHint}` : "",
          sizeHint,
        ].filter(Boolean);
        if (!hits.length) {
          setHint(
            sizeHint ||
              "未识别到可勾选的任务。请使用任务页全屏截图后重试。",
          );
        } else if (parts.length) {
          setHint(parts.join(" · "));
        }
      } catch (err) {
        if (ac.signal.aborted) return;
        setPhase("idle");
        setError(apiError(err, "识别失败，请重试"));
      }
    },
    [mapSlug, user],
  );

  useEffect(() => {
    if (!open) return undefined;
    const onPaste = (event: ClipboardEvent) => {
      if (phase === "working" || submitting) return;
      const target = event.target;
      if (target instanceof HTMLElement) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable) {
          return;
        }
      }
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
      setError(apiError(err, "勾选失败，请重试"));
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
          <p className={styles.ocrPasteHint}>
            {user ? "Ctrl+V粘贴截图进行识别" : "登录后才能截图识别"}
          </p>
          <p className={styles.ocrMeta}>
            截图只进本站内存。按系统「文字识别」里为局前任务勾选的引擎对照当前地图任务名，不存盘。
          </p>
          {error ? <p className={styles.ocrError}>{error}</p> : null}
        </div>
      ) : null}

      {phase === "working" ? (
        <div className={styles.ocrWorking}>
          <Spin />
          <p className={styles.ocrMeta}>{progress}</p>
        </div>
      ) : null}

      {phase === "done" && matches.length === 0 ? (
        <div className={styles.ocrEmpty}>
          <p className={styles.ocrLead}>
            {hint || "未识别到可勾选的任务。请使用任务页全屏截图后重试。"}
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
