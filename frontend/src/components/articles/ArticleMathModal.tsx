import { Button, Input, Modal, Radio, Space, message } from "antd";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import { recognizeArticleMath } from "@/api/articlesApi";
import { apiError } from "@/lib/apiError";
import { normalizeArticleMath, renderArticleMathHtml } from "@/lib/articleMath";
import {
  isNearWhiteCanvas,
  MATH_RECOGNIZE_ACCEPT,
  rejectMathRecognizeFile,
} from "@/lib/articleMathRecognize";
import styles from "./TavernEdit.module.css";

function paintBlankPad(canvas: HTMLCanvasElement) {
  const rect = canvas.getBoundingClientRect();
  if (rect.width < 8 || rect.height < 8) return;
  const dpr = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "#111";
  ctx.lineWidth = 2.6 * dpr;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
}

function canvasPoint(
  canvas: HTMLCanvasElement,
  event: { clientX: number; clientY: number },
) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * canvas.width,
    y: ((event.clientY - rect.top) / rect.height) * canvas.height,
  };
}

function exportPadFile(canvas: HTMLCanvasElement): Promise<File | null> {
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    if (isNearWhiteCanvas(data)) return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        resolve(null);
        return;
      }
      resolve(new File([blob], "formula.png", { type: "image/png" }));
    }, "image/png");
  });
}

export function ArticleMathModal({
  open,
  latex,
  display,
  onCancel,
  onOk,
}: {
  open: boolean;
  latex: string;
  display: boolean;
  onCancel: () => void;
  onOk: (next: { latex: string; display: boolean }) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const drawing = useRef(false);
  const dirtyRef = useRef(false);
  const [draft, setDraft] = useState(latex);
  const [block, setBlock] = useState(display);
  const [padDirty, setPadDirty] = useState(false);
  const [upload, setUpload] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDraft(latex);
    setBlock(display);
    setPadDirty(false);
    setUpload(null);
    setBusy(false);
    dirtyRef.current = false;
    let observer: ResizeObserver | undefined;
    let frame = 0;
    const attach = () => {
      const canvas = canvasRef.current;
      if (!canvas) {
        frame = requestAnimationFrame(attach);
        return;
      }
      paintBlankPad(canvas);
      observer = new ResizeObserver(() => {
        if (dirtyRef.current) return;
        paintBlankPad(canvas);
      });
      observer.observe(canvas);
    };
    frame = requestAnimationFrame(attach);
    return () => {
      cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [open, latex, display]);

  const insert = () => {
    const next = normalizeArticleMath(draft);
    if (!next) return;
    onOk({ latex: next, display: block });
  };

  const clearPad = () => {
    const canvas = canvasRef.current;
    if (canvas) paintBlankPad(canvas);
    dirtyRef.current = false;
    setPadDirty(false);
  };

  const pickUpload = (file: File | undefined) => {
    if (!file) return;
    const reject = rejectMathRecognizeFile(file);
    if (reject) {
      message.error(reject);
      return;
    }
    setUpload(file);
  };

  const recognize = async () => {
    const canvas = canvasRef.current;
    let file: File | null = null;
    if (padDirty && canvas) file = await exportPadFile(canvas);
    if (!file && upload) file = upload;
    if (!file) {
      message.warning("请先手写或上传公式图片");
      return;
    }
    const reject = rejectMathRecognizeFile(file);
    if (reject) {
      message.error(reject);
      return;
    }
    setBusy(true);
    try {
      const out = await recognizeArticleMath(file);
      setDraft(out.latex);
    } catch (err) {
      message.error(apiError(err, "识别失败"));
    } finally {
      setBusy(false);
    }
  };

  const onPointerDown = (event: PointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0 && event.pointerType === "mouse") return;
    const canvas = event.currentTarget;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.setPointerCapture(event.pointerId);
    drawing.current = true;
    const { x, y } = canvasPoint(canvas, event);
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const onPointerMove = (event: PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const canvas = event.currentTarget;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const { x, y } = canvasPoint(canvas, event);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y);
    if (!dirtyRef.current) {
      dirtyRef.current = true;
      setPadDirty(true);
    }
  };

  const onPointerUp = (event: PointerEvent<HTMLCanvasElement>) => {
    drawing.current = false;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* already released */
    }
  };

  const preview = renderArticleMathHtml(draft, block);
  const canInsert = Boolean(normalizeArticleMath(draft));

  return (
    <Modal
      title="公式"
      open={open}
      onCancel={onCancel}
      destroyOnClose
      width="min(720px, calc(100vw - 24px))"
      footer={
        <Space>
          <Button onClick={onCancel}>取消</Button>
          <Button type="primary" disabled={!canInsert} onClick={insert}>
            插入
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" className={styles.mathDialog} size="middle">
        <div className={styles.mathDialogBar}>
          <Radio.Group
            value={block ? "block" : "inline"}
            onChange={(event) => setBlock(event.target.value === "block")}
          >
            <Radio.Button value="inline">行内</Radio.Button>
            <Radio.Button value="block">独立成段</Radio.Button>
          </Radio.Group>
          <Button onClick={clearPad}>清空画板</Button>
          <Button onClick={() => fileRef.current?.click()}>上传图片</Button>
          <Button
            type="primary"
            loading={busy}
            disabled={!padDirty && !upload}
            onClick={() => void recognize()}
          >
            识别
          </Button>
        </div>
        <div className={styles.mathPadWrap}>
          <canvas
            ref={canvasRef}
            className={styles.mathPad}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          />
          {!padDirty ? (
            <div className={styles.mathPadHint}>
              {upload
                ? `已选 ${upload.name}，也可在白板上手写后再识别`
                : "在白板上手写公式，或上传印刷/手写图片"}
            </div>
          ) : null}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept={MATH_RECOGNIZE_ACCEPT}
          className={styles.fileInput}
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            pickUpload(file);
          }}
        />
        <Input.TextArea
          value={draft}
          rows={4}
          placeholder="识别结果会填到这里，也可直接改 LaTeX"
          onChange={(event) => setDraft(event.target.value)}
          onPressEnter={(event) => {
            if (!event.shiftKey && canInsert) {
              event.preventDefault();
              insert();
            }
          }}
        />
        <div className={styles.mathPreview}>
          {preview.error ? (
            <span
              className={
                draft.trim() ? styles.mathPreviewError : styles.mutedHint
              }
            >
              {draft.trim() ? preview.error : "预览"}
            </span>
          ) : (
            <span dangerouslySetInnerHTML={{ __html: preview.html }} />
          )}
        </div>
      </Space>
    </Modal>
  );
}
