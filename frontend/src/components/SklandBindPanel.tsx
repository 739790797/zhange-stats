import { useQueryClient } from "@tanstack/react-query";
import { Button, Spin, Typography, message } from "antd";
import { useEffect, useRef, useState } from "react";
import {
  bindSklandPassword,
  bindSklandSms,
  pollSklandQrBind,
  sendSklandSms,
  startSklandQrBind,
} from "@/api/client";
import type { SklandQrStart } from "@/api/types";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";

function apiError(e: unknown, fallback: string) {
  const detail =
    e &&
    typeof e === "object" &&
    "response" in e &&
    (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  if (detail) return String(detail);
  const msg = String((e as Error)?.message || "");
  // axios 在连不上代理/后端时常见文案，避免误以为是「二维码本身坏了」
  if (/network error/i.test(msg) || msg.includes("Failed to fetch")) {
    return "无法连接后端（开发服务可能已停或端口不对），请刷新页面或重启前后端";
  }
  return msg || fallback;
}

export function SklandBindPanel({
  title = "绑定森空岛",
  defaultMode = "qr",
  onSuccess,
}: {
  title?: string;
  defaultMode?: "qr" | "sms" | "password";
  onSuccess?: () => void;
}) {
  const queryClient = useQueryClient();
  const [qr, setQr] = useState<SklandQrStart | null>(null);
  const [qrHint, setQrHint] = useState("请使用森空岛 App 扫码");
  const [qrLoading, setQrLoading] = useState(false);
  const pollTimer = useRef<number | null>(null);
  const qrDone = useRef(false);
  const modeRef = useRef<"qr" | "sms" | "password">(defaultMode);

  const clearPollTimer = () => {
    if (pollTimer.current != null) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["skland-status"] });
    queryClient.invalidateQueries({ queryKey: ["profile-me"] });
  };

  const finishOk = (msg = "森空岛绑定成功") => {
    message.success(msg);
    invalidate();
    onSuccess?.();
  };

  const startQrSession = async () => {
    clearPollTimer();
    setQrLoading(true);
    setQrHint("请使用森空岛 App 扫码");
    qrDone.current = false;
    try {
      const session = await startSklandQrBind();
      setQr(session);
      setQrHint("请使用森空岛 App 扫码，并在手机上确认登录");
      pollTimer.current = window.setInterval(async () => {
        if (qrDone.current || modeRef.current !== "qr") return;
        try {
          const poll = await pollSklandQrBind(session.scan_id);
          if (poll.status === "waiting") {
            setQrHint(poll.message || "等待扫码…");
            return;
          }
          if (poll.status === "scanned") {
            setQrHint(poll.message || "已扫码，请在 App 内确认");
            return;
          }
          if (poll.status === "ok") {
            qrDone.current = true;
            clearPollTimer();
            finishOk(poll.message || "森空岛绑定成功");
            return;
          }
          if (poll.status === "expired" || poll.status === "error") {
            clearPollTimer();
            setQrHint(poll.message || "二维码已失效，请刷新");
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

  useEffect(() => {
    if (defaultMode === "qr") void startQrSession();
    return () => clearPollTimer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <PhoneAuthBindTemplate
      title={title}
      description="支持扫码、短信验证码或账号密码登录鹰角通行证，用于明日方舟 / 终末地签到。"
      modes={["qr", "sms", "password"]}
      defaultMode={defaultMode}
      onModeChange={(mode) => {
        modeRef.current = mode;
        if (mode === "qr") {
          void startQrSession();
        } else {
          clearPollTimer();
        }
      }}
      onSendSms={async (phone) => {
        await sendSklandSms(phone);
      }}
      onBindSms={async (phone, code) => {
        await bindSklandSms(phone, code);
        finishOk();
      }}
      onBindPassword={async (phone, password) => {
        await bindSklandPassword(phone, password);
        finishOk();
      }}
      qrPanel={
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
                alt="森空岛登录二维码"
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
            <Button onClick={() => void startQrSession()} loading={qrLoading}>
              刷新二维码
            </Button>
          </div>
        </div>
      }
    />
  );
}
