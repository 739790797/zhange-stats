import { useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import { useRef } from "react";
import {
  bindTaygedoPassword,
  bindTaygedoSms,
  sendTaygedoSms,
} from "@/api/client";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";

export function TaygedoBindPanel({
  title = "绑定塔吉多",
  onSuccess,
}: {
  title?: string;
  onSuccess?: () => void;
}) {
  const queryClient = useQueryClient();
  const deviceIdRef = useRef("");

  const finishOk = async (status?: { bound?: boolean } | null) => {
    message.success("塔吉多绑定成功");
    if (status?.bound) {
      queryClient.setQueryData(["taygedo-status"], status);
    }
    await queryClient.refetchQueries({ queryKey: ["taygedo-status"] });
    await queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    onSuccess?.();
  };

  return (
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
  );
}
