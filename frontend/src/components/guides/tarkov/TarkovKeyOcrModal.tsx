import { Modal, Spin } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { formatOcrProgress, newOcrIds } from "@/lib/tarkovOcr";
import {
  preloadTarkovOcrWorker,
  terminateTarkovOcrWorker,
} from "@/lib/tarkovOcrEngine";
import {
  type TarkovKeyOcrCatalogKey,
  type TarkovKeyOcrMatch,
} from "@/lib/tarkovKeyOcr";
import { paintKeyOcrOverlay, type TarkovKeyOcrOverlay } from "@/lib/tarkovKeyOcrOverlay";
import { recognizeKeyboxScreenshot } from "@/lib/tarkovKeyOcrRecognize";
import ocr from "./TarkovRaidPrepPanel.module.css";

type Phase = "idle" | "working" | "done";

type Props = {
  open: boolean;
  onClose: () => void;
  catalog: TarkovKeyOcrCatalogKey[];
  ownedIds: string[];
  onConfirm: (itemIds: string[]) => void | Promise<void>;
};

export function TarkovKeyOcrModal({
  open,
  onClose,
  catalog,
  ownedIds,
  onConfirm,
}: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [progress, setProgress] = useState("识别中…");
  const [matches, setMatches] = useState<TarkovKeyOcrMatch[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [overlay, setOverlay] = useState<TarkovKeyOcrOverlay | null>(null);
  const previewUrlRef = useRef("");

  const dropPreview = useCallback(() => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = "";
    setPreviewUrl("");
    setOverlay(null);
  }, []);

  const reset = useCallback(() => {
    setPhase("idle");
    setError("");
    setHint("");
    setProgress("识别中…");
    setMatches([]);
    setChecked({});
    setSubmitting(false);
    dropPreview();
  }, [dropPreview]);

  useEffect(() => {
    if (!open) {
      reset();
      void terminateTarkovOcrWorker();
      return;
    }
    preloadTarkovOcrWorker();
  }, [open, reset]);

  const applyMatches = useCallback((hits: TarkovKeyOcrMatch[], emptyHint: string) => {
    setMatches(hits);
    const next: Record<string, boolean> = {};
    for (const hit of hits) next[hit.id] = true;
    setChecked(next);
    setPhase("done");
    setError("");
    setHint(hits.length ? "" : emptyHint);
  }, []);

  const runRecognize = useCallback(
    async (file: Blob) => {
      setPhase("working");
      setError("");
      setHint("");
      setProgress("正在加载识别引擎…");
      setMatches([]);
      setChecked({});
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      const url = URL.createObjectURL(file);
      previewUrlRef.current = url;
      setPreviewUrl(url);
      setOverlay(null);
      try {
        const result = await recognizeKeyboxScreenshot(file, catalog, {
          onProgress: (status, pct) => {
            setProgress(formatOcrProgress(status, pct));
          },
          onOverlay: (next) => setOverlay(next),
        });
        applyMatches(result.matches, "未识别到目录里的钥匙。请 Ctrl+V 再贴一张钥匙格截图。");
      } catch (err) {
        setPhase("idle");
        setError(err instanceof Error ? err.message : "识别失败，请重试");
      }
    },
    [applyMatches, catalog],
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
    (row) => checked[row.id] && !ownedIds.includes(row.id),
  ).length;
  const confirmIds = matches.filter((row) => checked[row.id]).map((row) => row.id);
  const willAdd = newOcrIds(ownedIds, confirmIds);

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
              ? `确认我有 ${willAdd.length} 把`
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
      width={previewUrl ? 860 : 480}
      destroyOnClose
      classNames={{ body: ocr.ocrModalBody }}
    >
      {phase === "idle" ? (
        <div className={ocr.ocrIdle}>
          <p className={ocr.ocrPasteHint}>Ctrl+V粘贴截图进行识别</p>
          {error ? <p className={ocr.ocrError}>{error}</p> : null}
        </div>
      ) : null}

      {phase === "working" ? (
        <div className={`${ocr.ocrWorking} ${ocr.ocrKeyWorking}`}>
          {previewUrl ? <KeyOcrOverlayPreview src={previewUrl} overlay={overlay} /> : <Spin />}
          <div className={ocr.ocrWorkingMeta}>
            {previewUrl ? <Spin size="small" /> : null}
            <p className={ocr.ocrMeta}>{progress}</p>
          </div>
          <p className={ocr.ocrMeta}>中英模型从本站加载，无需访问外网</p>
        </div>
      ) : null}

      {phase === "done" && matches.length === 0 ? (
        <div className={ocr.ocrEmpty}>
          {previewUrl ? <KeyOcrOverlayPreview src={previewUrl} overlay={overlay} /> : null}
          <p className={ocr.ocrLead}>
            {hint || "未识别到可勾选的钥匙。请截钥匙格后重试。"}
          </p>
          {error ? <p className={ocr.ocrError}>{error}</p> : null}
        </div>
      ) : null}

      {phase === "done" && matches.length > 0 ? (
        <div className={ocr.ocrResult}>
          {previewUrl ? <KeyOcrOverlayPreview src={previewUrl} overlay={overlay} /> : null}
          {hint ? <p className={ocr.ocrMeta}>{hint}</p> : null}
          <p className={ocr.ocrLead}>
            识别到 {matches.length} 把钥匙
            {selectedNewCount ? `，其中 ${selectedNewCount} 把可新增` : "（均已拥有）"}
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
                    {row.icon_link ? (
                      <img
                        src={row.icon_link}
                        alt=""
                        width={28}
                        height={28}
                        style={{ objectFit: "contain", flex: "none" }}
                      />
                    ) : null}
                    <span className={ocr.ocrItemName}>
                      {row.name}
                      {row.short_name ? ` · ${row.short_name}` : ""}
                    </span>
                    {row.confidence === "fuzzy" ? (
                      <span className={ocr.ocrItemTag}>模糊</span>
                    ) : null}
                    {already ? <span className={ocr.ocrItemTag}>已有</span> : null}
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
    return () => {
      cancelled = true;
      window.removeEventListener("resize", onResize);
    };
  }, [src, overlay]);

  return (
    <div ref={wrapRef} className={ocr.ocrOverlay}>
      <canvas ref={canvasRef} className={ocr.ocrOverlayCanvas} />
      <p className={ocr.ocrLegend}>
        <span className={ocr.ocrLegendHit}>绿字会勾选</span>
        <span className={ocr.ocrLegendWhole}>蓝字整图补上的勾选</span>
        <span className={ocr.ocrLegendBand}>黄框是读过的短名条</span>
      </p>
    </div>
  );
}
