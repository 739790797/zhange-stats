import { Modal } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  recognizeTarkovKeyOwns,
  type TarkovKeyOcr,
  type TarkovKeyOcrMatch,
} from "@/api/guidesApi";
import { TarkovGuideItemCell } from "@/components/guides/tarkov/TarkovGuideItemCell";
import { apiError } from "@/lib/apiError";
import {
  paintKeyOcrOverlay,
  type TarkovKeyOcrOverlay,
} from "@/lib/tarkovKeyOcrOverlay";
import type { KeyOcrProgress } from "@/lib/tarkovKeyOcrProgress";
import { newOcrIds, formatKeyOcrEngines } from "@/lib/tarkovOcr";
import { useAuthStore } from "@/stores/authStore";
import ocr from "./TarkovRaidPrepPanel.module.css";

const IDLE_PROGRESS: KeyOcrProgress = {
  message: "正在用多个 OCR 交叉识别短名…",
  percent: 0,
};

type Phase = "idle" | "working" | "done";

type Props = {
  open: boolean;
  onClose: () => void;
  ownedIds: string[];
  onConfirm: (itemIds: string[]) => void | Promise<void>;
};

export function TarkovKeyOcrModal({
  open,
  onClose,
  ownedIds,
  onConfirm,
}: Props) {
  const user = useAuthStore((s) => s.user);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [matches, setMatches] = useState<TarkovKeyOcrMatch[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [overlay, setOverlay] = useState<TarkovKeyOcrOverlay | null>(null);
  const [progress, setProgress] = useState<KeyOcrProgress>(IDLE_PROGRESS);
  const previewUrlRef = useRef("");
  const abortRef = useRef<AbortController | null>(null);

  const dropPreview = useCallback(() => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = "";
    setPreviewUrl("");
    setOverlay(null);
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setPhase("idle");
    setError("");
    setHint("");
    setMatches([]);
    setChecked({});
    setSubmitting(false);
    setProgress(IDLE_PROGRESS);
    dropPreview();
  }, [dropPreview]);

  useEffect(() => {
    if (!open) reset();
  }, [open, reset]);

  const runRecognize = useCallback(
    async (file: Blob) => {
      if (!user) {
        setError("登录后才能截图识别");
        return;
      }
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      const url = URL.createObjectURL(file);
      previewUrlRef.current = url;
      setPreviewUrl(url);
      setOverlay(null);
      setPhase("working");
      setError("");
      setHint("");
      setMatches([]);
      setChecked({});
      setProgress(IDLE_PROGRESS);
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      try {
        const result: TarkovKeyOcr = await recognizeTarkovKeyOwns(file, {
          signal: ac.signal,
          onProgress: (row) => {
            if (!ac.signal.aborted) setProgress(row);
          },
        });
        if (ac.signal.aborted) return;
        const hits = result.matches || [];
        setMatches(hits);
        const next: Record<string, boolean> = {};
        for (const hit of hits) next[hit.id] = hit.confidence !== "fuzzy";
        setChecked(next);
        setOverlay(result.overlay ?? null);
        setPhase("done");
        const engineHint = formatKeyOcrEngines(result.engines);
        if (!hits.length) {
          setHint("未识别到钥匙短名。请截游戏内钥匙箱或钥匙工具后再试。");
        } else {
          const parts: string[] = [];
          if (engineHint) parts.push(`已用 ${engineHint} 交叉验证`);
          if (result.tile_count > 1) {
            parts.push(`按 ${result.tile_count} 块正方形切图`);
          }
          setHint(parts.join(" · "));
        }
      } catch (err) {
        if (ac.signal.aborted) return;
        setPhase("idle");
        setError(apiError(err, "识别失败，请重试"));
        dropPreview();
      }
    },
    [dropPreview, user],
  );

  useEffect(() => {
    if (!open) return undefined;
    const onPaste = (event: ClipboardEvent) => {
      const target = event.target;
      if (target instanceof HTMLElement) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable) {
          return;
        }
      }
      const item = [...(event.clipboardData?.items || [])].find((row) =>
        row.type.startsWith("image/"),
      );
      const file = item?.getAsFile();
      if (!file) return;
      event.preventDefault();
      void runRecognize(file);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [open, runRecognize]);

  const willAdd = newOcrIds(
    ownedIds,
    matches.filter((row) => checked[row.id]).map((row) => row.id),
  );
  const selectedNewCount = willAdd.length;

  const handleConfirm = async () => {
    if (!willAdd.length) return;
    setSubmitting(true);
    try {
      await onConfirm(willAdd);
      onClose();
    } catch (err) {
      setError(apiError(err, "勾选失败，请重试"));
      setSubmitting(false);
    }
  };

  const preview = previewUrl ? (
    <KeyOcrOverlayPreview src={previewUrl} overlay={overlay} />
  ) : null;

  const footer =
    phase === "done" && matches.length > 0 ? (
      <div className={ocr.ocrFooter}>
        <button
          type="button"
          className={ocr.dockChip}
          disabled={submitting}
          onClick={reset}
        >
          重新识别
        </button>
        <button
          type="button"
          className={ocr.dockChip}
          disabled={submitting}
          onClick={onClose}
        >
          取消
        </button>
        <button
          type="button"
          className={`${ocr.dockChip} ${ocr.dockChipOn}`}
          disabled={submitting || willAdd.length === 0}
          onClick={() => void handleConfirm()}
        >
          {submitting
            ? "处理中…"
            : willAdd.length
              ? `确认标记 ${willAdd.length} 把`
              : "没有可新增的钥匙"}
        </button>
      </div>
    ) : phase === "done" ? (
      <div className={ocr.ocrFooter}>
        <button type="button" className={ocr.dockChip} onClick={onClose}>
          关闭
        </button>
        <button
          type="button"
          className={`${ocr.dockChip} ${ocr.dockChipOn}`}
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
      width={previewUrl ? 860 : 520}
      destroyOnClose
      classNames={{ body: ocr.ocrModalBody }}
    >
      {phase === "idle" ? (
        <div className={ocr.ocrIdle}>
          <p className={ocr.ocrPasteHint}>
            {user
              ? "Ctrl+V 粘贴游戏内钥匙箱截图"
              : "登录后才能截图识别"}
          </p>
          <p className={ocr.ocrMeta}>
            截图只进本站内存。按系统「文字识别」里为钥匙箱勾选的引擎交叉识别短名，不存盘。确认后才写入「我有」。模型由任务配置「识别模型更新」维护。
          </p>
          {error ? <p className={ocr.ocrError}>{error}</p> : null}
        </div>
      ) : null}

      {phase === "working" ? (
        <div className={`${ocr.ocrWorking} ${ocr.ocrKeyWorking}`}>
          {preview}
          <div className={ocr.ocrProgress}>
            <div className={ocr.ocrProgressRow}>
              <p className={ocr.ocrMeta}>
                {progress.message || IDLE_PROGRESS.message}
              </p>
              <span className={ocr.ocrProgressPct}>{progress.percent}%</span>
            </div>
            <div
              className={ocr.ocrProgressTrack}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress.percent}
            >
              <div
                className={ocr.ocrProgressFill}
                style={{ width: `${progress.percent}%` }}
              />
            </div>
          </div>
          <p className={ocr.ocrMeta}>低频功能优先准确，CPU 上可能需要一分钟</p>
        </div>
      ) : null}

      {phase === "done" && matches.length === 0 ? (
        <div className={ocr.ocrEmpty}>
          {preview}
          <p className={ocr.ocrLead}>{hint || "未识别到钥匙。"}</p>
          {error ? <p className={ocr.ocrError}>{error}</p> : null}
        </div>
      ) : null}

      {phase === "done" && matches.length > 0 ? (
        <div className={ocr.ocrResult}>
          {preview}
          {hint ? <p className={ocr.ocrMeta}>{hint}</p> : null}
          <p className={ocr.ocrLead}>
            识别到 {matches.length} 把钥匙
            {selectedNewCount ? `，其中 ${selectedNewCount} 把可新增` : "（均已标记）"}
          </p>
          <ul className={ocr.ocrList}>
            {matches.map((row) => {
              const already = ownedIds.includes(row.id);
              return (
                <li key={row.id} className={ocr.ocrItem}>
                  <label className={ocr.ocrItemLabel}>
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
                    <TarkovGuideItemCell
                      item={{
                        id: row.id,
                        name: row.name,
                        short_name: row.short_name,
                        icon_link: row.icon_link,
                      }}
                      showCount={false}
                    />
                    {already ? (
                      <span className={ocr.ocrItemTag}>已有</span>
                    ) : row.confidence === "fuzzy" ? (
                      <span className={ocr.ocrItemTag}>模糊</span>
                    ) : null}
                  </label>
                </li>
              );
            })}
          </ul>
          {error ? <p className={ocr.ocrError}>{error}</p> : null}
        </div>
      ) : null}
    </Modal>
  );
}

function KeyOcrOverlayPreview({
  src,
  overlay,
}: {
  src: string;
  overlay: TarkovKeyOcrOverlay | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return undefined;
    const image = new Image();
    let cancelled = false;
    const draw = () => {
      if (cancelled) return;
      const maxW = wrap.clientWidth || overlay?.width || image.naturalWidth;
      const srcW = overlay?.width || image.naturalWidth;
      const srcH = overlay?.height || image.naturalHeight;
      if (!srcW || !srcH) return;
      const scale = maxW / srcW;
      const dpr = window.devicePixelRatio || 1;
      const cssW = Math.max(1, Math.round(srcW * scale));
      const cssH = Math.max(1, Math.round(srcH * scale));
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      canvas.style.width = `${cssW}px`;
      canvas.style.height = `${cssH}px`;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(image, 0, 0, cssW, cssH);
      if (overlay) paintKeyOcrOverlay(ctx, overlay, scale);
    };
    image.onload = draw;
    image.src = src;
    const onResize = () => draw();
    window.addEventListener("resize", onResize);
    const observer =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(onResize)
        : null;
    observer?.observe(wrap);
    return () => {
      cancelled = true;
      window.removeEventListener("resize", onResize);
      observer?.disconnect();
    };
  }, [src, overlay]);

  return (
    <div ref={wrapRef} className={ocr.ocrOverlay}>
      <canvas ref={canvasRef} className={ocr.ocrOverlayCanvas} />
      {overlay?.boxes?.length ? (
        <p className={ocr.ocrLegend}>
          <span className={ocr.ocrLegendHit}>绿框命中短名</span>
          <span className={ocr.ocrLegendBand}>黄框模糊匹配</span>
          <span className={ocr.ocrLegendEmpty}>灰框读到但未入库</span>
        </p>
      ) : null}
    </div>
  );
}
