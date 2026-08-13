import { useQueryClient } from "@tanstack/react-query";
import { Button, Spin, Typography, message } from "antd";
import { useEffect, useRef, useState } from "react";
import {
  bindSklandPassword,
  bindSklandSms,
  fetchSklandStatus,
  pollSklandQrBind,
  sendSklandSms,
  startSklandQrBind,
} from "@/api/client";
import type { SklandQrStart, SklandStatus } from "@/api/types";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";
import {
  preferredPhoneAuthMode,
  type PhoneAuthMode,
} from "@/lib/phoneAuth";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import { apiError } from "@/lib/apiError";

const SKLAND_MODES: PhoneAuthMode[] = ["qr", "sms", "password"];
const STATUS_KEY = ["skland-status"] as const;

export function SklandBindPanel({
  title = "绑定森空岛",
  onSuccess,
  openRolePickerOnBind = true,
}: {
  title?: string;
  onSuccess?: () => void;
  /** 绑定成功后是否在本组件内打开角色树；个人中心由父级托管时应为 false */
  openRolePickerOnBind?: boolean;
}) {
  const queryClient = useQueryClient();
  const { openPicker, modal } = useRoleMembershipPicker("skland");
  const resolvedDefault = preferredPhoneAuthMode(SKLAND_MODES);
  const [qr, setQr] = useState<SklandQrStart | null>(null);
  const [qrHint, setQrHint] = useState("请使用森空岛 App 扫码");
  const [qrLoading, setQrLoading] = useState(false);
  const pollTimer = useRef<number | null>(null);
  const qrDone = useRef(false);
  const modeRef = useRef<PhoneAuthMode>(resolvedDefault);

  const clearPollTimer = () => {
    if (pollTimer.current != null) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const finishOk = async (
    status?: SklandStatus | null,
    msg = "森空岛绑定成功",
  ) => {
    // 取消进行中的 status，避免「绑定前失效态」晚到覆盖「绑定成功」结果
    await queryClient.cancelQueries({ queryKey: STATUS_KEY });
    let next = status;
    // 无状态、或绑定接口返回的 token_ok=false：再拉一次权威 status
    if (!next?.bound || next.token_ok === false) {
      next = await fetchSklandStatus(true, true);
    }
    if (next?.bound) {
      queryClient.setQueryData(STATUS_KEY, next);
    }
    if (next?.bound && next.token_ok === false) {
      message.warning(
        next.token_error || "绑定已写入，但凭证校验未通过，请稍后刷新或重试",
      );
    } else {
      message.success(msg);
    }
    await queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    onSuccess?.();
    if (openRolePickerOnBind && next?.bound && next.token_ok !== false) {
      openPicker();
    }
  };

  const QR_HINT_WAITING = "请使用森空岛 App 扫码，并在手机上确认登录";

  const startQrSession = async () => {
    clearPollTimer();
    setQrLoading(true);
    setQrHint(QR_HINT_WAITING);
    qrDone.current = false;
    try {
      const session = await startSklandQrBind();
      setQr(session);
      setQrHint(QR_HINT_WAITING);
      pollTimer.current = window.setInterval(async () => {
        if (qrDone.current || modeRef.current !== "qr") return;
        try {
          const poll = await pollSklandQrBind(session.scan_id);
          if (poll.status === "waiting") {
            return;
          }
          if (poll.status === "scanned") {
            setQrHint(poll.message || "已扫码，请在 App 内确认");
            return;
          }
          if (poll.status === "ok") {
            qrDone.current = true;
            clearPollTimer();
            await finishOk(null, poll.message || "森空岛绑定成功");
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
    if (resolvedDefault === "qr") void startQrSession();
    return () => clearPollTimer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <PhoneAuthBindTemplate
        title={title}
        modes={SKLAND_MODES}
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
          const status = await bindSklandSms(phone, code);
          await finishOk(status);
        }}
        onBindPassword={async (phone, password) => {
          const status = await bindSklandPassword(phone, password);
          await finishOk(status);
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
      {modal}
    </>
  );
}
