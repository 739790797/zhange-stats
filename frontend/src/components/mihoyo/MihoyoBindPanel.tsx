import { useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import {
  bindMihoyoPassword,
  bindMihoyoSms,
  fetchMihoyoStatus,
  pollMihoyoQrBind,
  sendMihoyoSms,
  startMihoyoQrBind,
} from "@/api/client";
import type { MihoyoStatus } from "@/api/types";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";
import { useQrBindSession } from "@/hooks/useQrBindSession";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import { prefetchGeetest4, runGeetest4 } from "@/lib/geetest4";
import { preferredPhoneAuthMode, type PhoneAuthMode } from "@/lib/phoneAuth";
import { useRef } from "react";

const MIHOYO_MODES: PhoneAuthMode[] = ["qr", "sms", "password"];
const STATUS_KEY = ["mihoyo-status"] as const;

export function MihoyoBindPanel({
  title = "绑定米游社",
  onSuccess,
  openRolePickerOnBind = true,
}: {
  title?: string;
  onSuccess?: () => void;
  openRolePickerOnBind?: boolean;
}) {
  const queryClient = useQueryClient();
  const { openPicker, modal } = useRoleMembershipPicker("mihoyo");
  const resolvedDefault = preferredPhoneAuthMode(MIHOYO_MODES);
  const smsMmtKey = useRef<string | null>(null);

  const finishOk = async (
    _status?: MihoyoStatus | null,
    msg = "米游社绑定成功",
  ) => {
    await queryClient.cancelQueries({ queryKey: STATUS_KEY });
    const next = await fetchMihoyoStatus(true, true);
    queryClient.setQueryData(STATUS_KEY, next);
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

  const { qrPanel, onModeChange } = useQrBindSession({
    waitingHint: "请使用米游社 App 扫码，并在手机上确认登录",
    imageAlt: "米游社登录二维码",
    initialMode: resolvedDefault,
    start: startMihoyoQrBind,
    poll: pollMihoyoQrBind,
    onBound: async (msg) => {
      await finishOk(null, msg || "米游社绑定成功");
    },
  });

  return (
    <>
      <PhoneAuthBindTemplate
        title={title}
        modes={MIHOYO_MODES}
        accountPlaceholder="手机号或邮箱"
        onModeChange={onModeChange}
        onPhoneChange={() => {
          smsMmtKey.current = null;
        }}
        onSendSms={async (phone) => {
          let data = await sendMihoyoSms(phone);
          if (data.need_geetest) {
            message.info(data.message || "请完成人机验证");
            const captchaId = data.captcha_id;
            if (!captchaId) {
              throw new Error("缺少人机验证参数");
            }
            void prefetchGeetest4(captchaId);
            const validate = await runGeetest4(captchaId);
            data = await sendMihoyoSms(
              phone,
              JSON.stringify(validate),
              data.mmt_key || undefined,
            );
            if (data.need_geetest) {
              throw new Error(data.message || "人机验证未通过，请重试");
            }
          }
          if (!data.ok) {
            throw new Error(data.message || "发送失败");
          }
          smsMmtKey.current = data.mmt_key || null;
        }}
        onBindSms={async (phone, code) => {
          const status = await bindMihoyoSms(phone, code);
          await finishOk(status);
        }}
        onBindPassword={async (account, password) => {
          let data = await bindMihoyoPassword(account, password);
          if (data.need_geetest) {
            message.info(data.message || "请完成人机验证");
            const captchaId = data.captcha_id;
            if (!captchaId) {
              throw new Error("缺少人机验证参数");
            }
            void prefetchGeetest4(captchaId);
            const validate = await runGeetest4(captchaId);
            data = await bindMihoyoPassword(
              account,
              password,
              JSON.stringify(validate),
              data.mmt_key || undefined,
            );
            if (data.need_geetest) {
              throw new Error(data.message || "人机验证未通过，请重试");
            }
          }
          if (!data.ok || !data.status) {
            throw new Error(data.message || "绑定失败");
          }
          await finishOk(data.status);
        }}
        qrPanel={qrPanel}
      />
      {modal}
    </>
  );
}
