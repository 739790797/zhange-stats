import { Button, Spin, Typography } from "antd";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { apiError } from "@/lib/apiError";
import type { PhoneAuthMode } from "@/lib/phoneAuth";

export type QrBindPoll = {
  status: string;
  message?: string | null;
};

export type QrBindStart = {
  scan_id: string;
  qr_image?: string | null;
};

type Options = {
  waitingHint: string;
  imageAlt: string;
  initialMode: PhoneAuthMode;
  start: () => Promise<QrBindStart>;
  poll: (scanId: string) => Promise<QrBindPoll>;
  onBound: (message?: string | null) => Promise<void>;
};

/** 扫码绑定：start / poll / 定时器。短信与极验仍留在各 BindPanel。 */
export function useQrBindSession({
  waitingHint,
  imageAlt,
  initialMode,
  start,
  poll,
  onBound,
}: Options) {
  const [qr, setQr] = useState<QrBindStart | null>(null);
  const [qrHint, setQrHint] = useState(waitingHint);
  const [qrLoading, setQrLoading] = useState(false);
  const pollTimer = useRef<number | null>(null);
  const qrDone = useRef(false);
  const modeRef = useRef<PhoneAuthMode>(initialMode);
  const onBoundRef = useRef(onBound);
  onBoundRef.current = onBound;

  const clearPollTimer = () => {
    if (pollTimer.current != null) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const startQrSession = async () => {
    clearPollTimer();
    setQrLoading(true);
    setQrHint(waitingHint);
    qrDone.current = false;
    try {
      const session = await start();
      setQr(session);
      setQrHint(waitingHint);
      pollTimer.current = window.setInterval(async () => {
        if (qrDone.current || modeRef.current !== "qr") return;
        try {
          const result = await poll(session.scan_id);
          if (result.status === "waiting") return;
          if (result.status === "scanned") {
            setQrHint(result.message || "已扫码，请在 App 内确认");
            return;
          }
          if (result.status === "ok") {
            qrDone.current = true;
            clearPollTimer();
            await onBoundRef.current(result.message);
            return;
          }
          if (result.status === "expired" || result.status === "error") {
            clearPollTimer();
            setQrHint(result.message || "二维码已失效，请刷新");
          }
        } catch (e: unknown) {
          clearPollTimer();
          setQrHint(apiError(e, "扫码状态查询失败"));
        }
      }, 2000);
    } catch (e: unknown) {
      setQr(null);
      setQrHint(apiError(e, "生成二维码失败"));
    } finally {
      setQrLoading(false);
    }
  };

  const onModeChange = (mode: PhoneAuthMode) => {
    modeRef.current = mode;
    if (mode === "qr") void startQrSession();
    else clearPollTimer();
  };

  useEffect(() => {
    if (initialMode === "qr") void startQrSession();
    return () => clearPollTimer();
    // 仅挂载时拉一次二维码
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const qrPanel: ReactNode = (
    <div style={{ textAlign: "center" }}>
      <div
        style={{
          width: 220,
          height: 220,
          margin: "0 auto 12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#fafafa",
          border: "1px solid rgba(0,0,0,0.06)",
          borderRadius: 8,
        }}
      >
        {qrLoading ? (
          <Spin tip="生成中" />
        ) : qr?.qr_image ? (
          <img
            src={qr.qr_image}
            alt={imageAlt}
            width={200}
            height={200}
            style={{ display: "block" }}
          />
        ) : (
          <Typography.Text type="secondary">二维码不可用</Typography.Text>
        )}
      </div>
      <Typography.Text type="secondary">{qrHint}</Typography.Text>
      <div style={{ marginTop: 12 }}>
        <Button
          size="small"
          loading={qrLoading}
          onClick={() => void startQrSession()}
        >
          刷新二维码
        </Button>
      </div>
    </div>
  );

  return { qrPanel, onModeChange };
}
