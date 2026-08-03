import { useQueryClient } from "@tanstack/react-query";
import { Input, Space, Typography, message } from "antd";
import { useState } from "react";
import {
  bindExiliumPassword,
  bindExiliumSms,
  sendExiliumSms,
} from "@/api/client";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";

function asImageSrc(raw: string) {
  const text = (raw || "").trim();
  if (!text) return "";
  if (text.startsWith("data:") || text.startsWith("http")) return text;
  if (text.startsWith("<svg") || text.startsWith("<?xml")) {
    return `data:image/svg+xml;utf8,${encodeURIComponent(text)}`;
  }
  return `data:image/png;base64,${text}`;
}

export function ExiliumBindPanel({
  title = "绑定追放社区",
  onSuccess,
}: {
  title?: string;
  onSuccess?: () => void;
}) {
  const queryClient = useQueryClient();
  const [graphCode, setGraphCode] = useState("");
  const [graphImage, setGraphImage] = useState<string | null>(null);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["exilium-status"] });
    queryClient.invalidateQueries({ queryKey: ["profile-me"] });
  };

  const finishOk = () => {
    message.success("追放社区绑定成功");
    setGraphCode("");
    setGraphImage(null);
    invalidate();
    onSuccess?.();
  };

  return (
    <PhoneAuthBindTemplate
      title={title}
      description={
        <>
          使用追放官方社区（
          <Typography.Link href="https://gf2-bbs.exiliumgf.com/" target="_blank">
            gf2-bbs.exiliumgf.com
          </Typography.Link>
          ）账号绑定：支持手机号验证码，或手机号 / 邮箱 + 密码。绑定后可自动每日签到。
        </>
      }
      modes={["sms", "password"]}
      defaultMode="password"
      accountPlaceholder="手机号（短信）或手机号/邮箱（密码）"
      smsExtra={
        graphImage ? (
          <Space.Compact style={{ width: "100%" }}>
            <Input
              placeholder="图形验证码"
              value={graphCode}
              onChange={(e) => setGraphCode(e.target.value)}
              style={{ flex: 1 }}
            />
            <img
              src={asImageSrc(graphImage)}
              alt="图形验证码"
              title="点击可刷新：清空后重新获取短信"
              onClick={() => {
                setGraphImage(null);
                setGraphCode("");
              }}
              style={{
                height: 32,
                width: 100,
                objectFit: "contain",
                cursor: "pointer",
                background: "#f5f5f5",
                border: "1px solid #d9d9d9",
                borderLeft: "none",
              }}
            />
          </Space.Compact>
        ) : null
      }
      onPhoneChange={() => {
        setGraphCode("");
        setGraphImage(null);
      }}
      onSendSms={async (phone) => {
        const data = await sendExiliumSms(phone, graphCode || null);
        if (data.need_graph_captcha && data.graph_captcha_image) {
          setGraphImage(data.graph_captcha_image);
          message.info(data.message || "请输入图形验证码后重新发送");
          return false;
        }
        if (!data.ok) {
          throw new Error(data.message || "发送失败");
        }
        setGraphImage(null);
        setGraphCode("");
      }}
      onBindSms={async (phone, code) => {
        await bindExiliumSms(phone, code);
        finishOk();
      }}
      onBindPassword={async (account, password) => {
        await bindExiliumPassword(account, password);
        finishOk();
      }}
    />
  );
}
