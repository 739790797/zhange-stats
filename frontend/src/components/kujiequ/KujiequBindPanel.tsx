import { useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import { useEffect } from "react";
import { bindKujiequSms, sendKujiequSms } from "@/api/client";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import {
  KUJIEQU_GEETEST_CAPTCHA_ID,
  prefetchGeetest4,
  runGeetest4,
} from "@/lib/geetest4";

export function KujiequBindPanel({
  title = "绑定库街区",
  onSuccess,
  openRolePickerOnBind = true,
}: {
  title?: string;
  onSuccess?: () => void;
  openRolePickerOnBind?: boolean;
}) {
  const queryClient = useQueryClient();
  const { openPicker, modal } = useRoleMembershipPicker("kujiequ");

  useEffect(() => {
    void prefetchGeetest4(KUJIEQU_GEETEST_CAPTCHA_ID);
  }, []);

  const finishOk = async (status?: { bound?: boolean } | null) => {
    message.success("库街区绑定成功");
    if (status?.bound) {
      queryClient.setQueryData(["kujiequ-status"], status);
    }
    await queryClient.refetchQueries({ queryKey: ["kujiequ-status"] });
    await queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    onSuccess?.();
    if (openRolePickerOnBind) openPicker();
  };

  return (
    <>
      <PhoneAuthBindTemplate
        title={title}
        modes={["sms"]}
        onSendSms={async (phone) => {
          let data = await sendKujiequSms(phone);
          if (data.need_geetest) {
            message.info(data.message || "请完成人机验证");
            const captchaId = data.captcha_id || KUJIEQU_GEETEST_CAPTCHA_ID;
            const validate = await runGeetest4(captchaId);
            data = await sendKujiequSms(phone, JSON.stringify(validate));
            if (data.need_geetest) {
              throw new Error(data.message || "人机验证未通过，请重试");
            }
          }
          if (!data.ok) {
            throw new Error(data.message || "发送失败");
          }
        }}
        onBindSms={async (phone, code) => {
          const status = await bindKujiequSms(phone, code);
          await finishOk(status);
        }}
        onBindPassword={async () => {
          throw new Error("库街区仅支持短信验证码绑定");
        }}
      />
      {modal}
    </>
  );
}
