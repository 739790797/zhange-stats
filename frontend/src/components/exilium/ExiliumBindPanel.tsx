import { useQueryClient } from "@tanstack/react-query";
import { Input, Space, message } from "antd";
import { useState } from "react";
import {
  bindExiliumPassword,
  bindExiliumSms,
  sendExiliumSms,
} from "@/api/client";
import { PhoneAuthBindTemplate } from "@/components/PhoneAuthBindTemplate";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";

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
  title = "绑定追放",
  onSuccess,
  openRolePickerOnBind = true,
}: {
  title?: string;
  onSuccess?: () => void;
  openRolePickerOnBind?: boolean;
}) {
  const queryClient = useQueryClient();
  const { openPicker, modal } = useRoleMembershipPicker("exilium");
  const [graphCode, setGraphCode] = useState("");
  const [graphImage, setGraphImage] = useState<string | null>(null);

  const finishOk = async (status?: { bound?: boolean } | null) => {
    message.success("追放绑定成功");
    setGraphCode("");
    setGraphImage(null);
    if (status?.bound) {
      queryClient.setQueryData(["exilium-status"], status);
    }
    await queryClient.refetchQueries({ queryKey: ["exilium-status"] });
    await queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    onSuccess?.();
    if (openRolePickerOnBind) openPicker();
  };

  return (
    <>
      <PhoneAuthBindTemplate
        title={title}
        modes={["sms", "password"]}
        accountPlaceholder="手机号（短信）或手机号/邮箱（密码）"
        smsExtra={
          graphImage ? (
            <Space.Compact style={{ width: "100%" }}>
              <Input
                size="large"
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
                  height: 40,
                  width: 108,
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
          const status = await bindExiliumSms(phone, code);
          await finishOk(status);
        }}
        onBindPassword={async (account, password) => {
          const status = await bindExiliumPassword(account, password);
          await finishOk(status);
        }}
      />
      {modal}
    </>
  );
}
