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

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["taygedo-status"] });
    queryClient.invalidateQueries({ queryKey: ["profile-me"] });
  };

  const finishOk = () => {
    message.success("塔吉多绑定成功");
    invalidate();
    onSuccess?.();
  };

  return (
    <PhoneAuthBindTemplate
      title={title}
      description="使用手机号验证码或密码登录塔吉多账号。通常单设备在线，App 重新登录后站内凭证会失效，需重新绑定。"
      modes={["sms", "password"]}
      defaultMode="sms"
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
        await bindTaygedoSms(phone, code, deviceIdRef.current);
        finishOk();
      }}
      onBindPassword={async (phone, password) => {
        await bindTaygedoPassword(phone, password);
        finishOk();
      }}
    />
  );
}
