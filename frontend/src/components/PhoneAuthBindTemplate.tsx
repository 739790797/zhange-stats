import { Button, Input, Segmented, Space, Typography, message } from "antd";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { apiError } from "@/lib/apiError";
import {
  orderedPhoneAuthModes,
  preferredPhoneAuthMode,
  type PhoneAuthMode,
} from "@/lib/phoneAuth";

const MODE_LABEL: Record<PhoneAuthMode, string> = {
  qr: "扫码",
  sms: "短信验证码",
  password: "账号密码",
} as const;

/** 与登录页一致：Ant Design large = 40px 高 */
const CONTROL_SIZE = "large" as const;

export function PhoneAuthBindTemplate({
  title,
  description,
  modes,
  submitText = "登录并绑定",
  qrPanel,
  accountPlaceholder = "手机号",
  smsExtra,
  onModeChange,
  onPhoneChange,
  onSendSms,
  onBindSms,
  onBindPassword,
}: {
  title?: string;
  description?: ReactNode;
  modes: PhoneAuthMode[];
  submitText?: string;
  /** 扫码模式内容；仅当 modes 含 qr 时使用 */
  qrPanel?: ReactNode;
  accountPlaceholder?: string;
  /** 短信模式下额外字段（如图形验证码） */
  smsExtra?: ReactNode;
  onModeChange?: (mode: PhoneAuthMode) => void;
  /** 手机号变更时回调（如塔吉多清 deviceId） */
  onPhoneChange?: (phone: string, prevPhone: string) => void;
  /** 返回 false 表示未真正发出短信（如需先填图形验证码），不进入冷却 */
  onSendSms: (phone: string) => Promise<boolean | void>;
  onBindSms: (phone: string, code: string) => Promise<void>;
  onBindPassword: (phone: string, password: string) => Promise<void>;
}) {
  const modeOptions = orderedPhoneAuthModes(modes);
  const initial = preferredPhoneAuthMode(modeOptions);
  const [mode, setMode] = useState<PhoneAuthMode>(initial);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [smsCooldown, setSmsCooldown] = useState(0);
  const [sendingSms, setSendingSms] = useState(false);
  const [binding, setBinding] = useState(false);
  const smsTimer = useRef<number | null>(null);

  const clearSmsTimer = () => {
    if (smsTimer.current != null) {
      window.clearInterval(smsTimer.current);
      smsTimer.current = null;
    }
  };

  const startSmsCooldown = (seconds = 60) => {
    clearSmsTimer();
    setSmsCooldown(seconds);
    smsTimer.current = window.setInterval(() => {
      setSmsCooldown((prev) => {
        if (prev <= 1) {
          clearSmsTimer();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  useEffect(() => () => clearSmsTimer(), []);

  const changeMode = (next: PhoneAuthMode) => {
    setMode(next);
    onModeChange?.(next);
  };

  const sendSms = async () => {
    if (!phone.trim()) {
      message.warning("请填写手机号");
      return;
    }
    setSendingSms(true);
    try {
      const sent = await onSendSms(phone.trim());
      if (sent === false) {
        return;
      }
      startSmsCooldown(60);
      message.success("验证码已发送");
    } catch (e: unknown) {
      message.error(apiError(e, "发送验证码失败"));
    } finally {
      setSendingSms(false);
    }
  };

  const bindSms = async () => {
    if (!phone.trim() || !code.trim()) {
      message.warning("请填写手机号与验证码");
      return;
    }
    setBinding(true);
    try {
      await onBindSms(phone.trim(), code.trim());
    } catch (e: unknown) {
      message.error(apiError(e, "绑定失败"));
    } finally {
      setBinding(false);
    }
  };

  const bindPassword = async () => {
    if (!phone.trim() || !password) {
      message.warning("请填写手机号与密码");
      return;
    }
    setBinding(true);
    try {
      await onBindPassword(phone.trim(), password);
    } catch (e: unknown) {
      message.error(apiError(e, "绑定失败"));
    } finally {
      setBinding(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      {title ? (
        <Typography.Title
          level={5}
          style={{ marginTop: 0, marginBottom: description ? 8 : 16 }}
        >
          {title}
        </Typography.Title>
      ) : null}
      {description ? (
        <Typography.Paragraph
          type="secondary"
          style={{ marginBottom: 16, textAlign: "center", maxWidth: 420 }}
        >
          {description}
        </Typography.Paragraph>
      ) : null}

      {/* 与登录页同宽约 360–420；large 控件对齐 Ant Design 登录表单规范 */}
      <div style={{ width: "100%", maxWidth: 360 }}>
        {modeOptions.length > 1 ? (
          <Segmented
            block
            size={CONTROL_SIZE}
            style={{ marginBottom: 16 }}
            value={mode}
            onChange={(v) => changeMode(v as PhoneAuthMode)}
            options={modeOptions.map((m) => ({
              label: MODE_LABEL[m],
              value: m,
            }))}
          />
        ) : null}

        {mode === "qr" ? (
          qrPanel
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (binding) return;
              if (mode === "sms") void bindSms();
              else void bindPassword();
            }}
          >
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Input
                size={CONTROL_SIZE}
                placeholder={accountPlaceholder}
                value={phone}
                onChange={(e) => {
                  const next = e.target.value;
                  onPhoneChange?.(next, phone);
                  setPhone(next);
                }}
                autoComplete="username"
              />
              {mode === "sms" ? (
                <>
                  {smsExtra}
                  <Space.Compact style={{ width: "100%" }}>
                    <Input
                      size={CONTROL_SIZE}
                      placeholder="短信验证码"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      autoComplete="one-time-code"
                      inputMode="numeric"
                    />
                    <Button
                      size={CONTROL_SIZE}
                      htmlType="button"
                      loading={sendingSms}
                      disabled={smsCooldown > 0 || sendingSms}
                      onClick={() => void sendSms()}
                    >
                      {smsCooldown > 0 ? `${smsCooldown}s` : "获取验证码"}
                    </Button>
                  </Space.Compact>
                  <Button
                    type="primary"
                    size={CONTROL_SIZE}
                    htmlType="submit"
                    block
                    loading={binding}
                  >
                    {submitText}
                  </Button>
                </>
              ) : (
                <>
                  <Input.Password
                    size={CONTROL_SIZE}
                    placeholder="密码"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                  <Button
                    type="primary"
                    size={CONTROL_SIZE}
                    htmlType="submit"
                    block
                    loading={binding}
                  >
                    {submitText}
                  </Button>
                </>
              )}
            </Space>
          </form>
        )}
      </div>
    </div>
  );
}
