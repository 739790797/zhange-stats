import { useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import {
  bindSklandPassword,
  bindSklandSms,
  fetchSklandStatus,
  pollSklandQrBind,
  sendSklandSms,
  startSklandQrBind,
} from "@/api/client";
import type { SklandStatus } from "@/api/types";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";
import { preferredPhoneAuthMode, type PhoneAuthMode } from "@/lib/phoneAuth";
import { useQrBindSession } from "@/hooks/useQrBindSession";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";

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

  const finishOk = async (
    status?: SklandStatus | null,
    msg = "森空岛绑定成功",
  ) => {
    await queryClient.cancelQueries({ queryKey: STATUS_KEY });
    let next = status;
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

  const { qrPanel, onModeChange } = useQrBindSession({
    waitingHint: "请使用森空岛 App 扫码，并在手机上确认登录",
    imageAlt: "森空岛登录二维码",
    initialMode: resolvedDefault,
    start: startSklandQrBind,
    poll: pollSklandQrBind,
    onBound: async (msg) => {
      await finishOk(null, msg || "森空岛绑定成功");
    },
  });

  return (
    <>
      <PhoneAuthBindTemplate
        title={title}
        modes={SKLAND_MODES}
        onModeChange={onModeChange}
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
        qrPanel={qrPanel}
      />
      {modal}
    </>
  );
}
