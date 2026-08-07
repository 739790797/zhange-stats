import { useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import { useRef } from "react";
import {
  bindTaygedoPassword,
  bindTaygedoSms,
  sendTaygedoSms,
} from "@/api/client";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";

export function TaygedoBindPanel({
  title = "绑定塔吉多",
  onSuccess,
  openRolePickerOnBind = true,
}: {
  title?: string;
  onSuccess?: () => void;
  openRolePickerOnBind?: boolean;
}) {
  const queryClient = useQueryClient();
  const { openPicker, modal } = useRoleMembershipPicker("taygedo");
  const deviceIdRef = useRef("");

  const finishOk = async (status?: { bound?: boolean } | null) => {
    message.success("塔吉多绑定成功");
    if (status?.bound) {
      queryClient.setQueryData(["taygedo-status"], status);
    }
    await queryClient.refetchQueries({ queryKey: ["taygedo-status"] });
    await queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    onSuccess?.();
    if (openRolePickerOnBind) openPicker();
  };

  return (
    <>
      <PhoneAuthBindTemplate
        title={title}
        modes={["sms", "password"]}
        onPhoneChange={(next, prev) => {
          if (deviceIdRef.current && next.trim() !== prev.trim()) {
            deviceIdRef.current = "";
          }
        }}
        onSendSms={async (phone) => {
          const data = await sendTaygedoSms(phone, deviceIdRef.current || null);
          deviceIdRef.current = data.device_id;
        }}
        onBindSms={async (phone, code) => {
          if (!deviceIdRef.current) {
            throw new Error("请先获取短信验证码");
          }
          const status = await bindTaygedoSms(phone, code, deviceIdRef.current);
          await finishOk(status);
        }}
        onBindPassword={async (phone, password) => {
          const status = await bindTaygedoPassword(phone, password);
          await finishOk(status);
        }}
      />
      {modal}
    </>
  );
}
