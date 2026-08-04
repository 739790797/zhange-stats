import { useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import { useEffect } from "react";
import { bindKujiequSms, sendKujiequSms } from "@/api/client";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";
import {
  KUJIEQU_GEETEST_CAPTCHA_ID,
  prefetchGeetest4,
  runGeetest4,
} from "@/lib/geetest4";

export function KujiequBindPanel({
  title = "绑定库街区",
  onSuccess,
}: {
  title?: string;
  onSuccess?: () => void;
}) {
  const queryClient = useQueryClient();

  useEffect(() => {
    void prefetchGeetest4(KUJIEQU_GEETEST_CAPTCHA_ID);
  }, []);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["kujiequ-status"] });
    queryClient.invalidateQueries({ queryKey: ["profile-me"] });
  };

  const finishOk = () => {
    message.success("库街区绑定成功");
    invalidate();
    onSuccess?.();
  };

  return (
    <PhoneAuthBindTemplate
      title={title}
      description="使用手机号短信验证码登录库街区。发送验证码时如需人机验证，将弹出官方极验（滑块/点选）。绑定后可自动完成社区与鸣潮 / 战双签到。"
      modes={["sms"]}
      defaultMode="sms"
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
        await bindKujiequSms(phone, code);
        finishOk();
      }}
      onBindPassword={async () => {
        throw new Error("库街区仅支持短信验证码绑定");
      }}
    />
  );
}
