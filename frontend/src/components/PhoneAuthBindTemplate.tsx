import { Button, Input, Segmented, Space, Typography, message } from "antd";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

export type PhoneAuthMode = "qr" | "sms" | "password";

const MODE_LABEL: Record<PhoneAuthMode, string> = {
  qr: "扫码",
  sms: "短信验证码",
  password: "账号密码",
};

export function PhoneAuthBindTemplate({
  title,
  description,
  modes,
  defaultMode,
  submitText = "登录并绑定",
  qrPanel,
  onModeChange,
  onPhoneChange,
  onSendSms,
  onBindSms,
  onBindPassword,
}: {
  title?: string;
  description: ReactNode;
  modes: PhoneAuthMode[];
  defaultMode?: PhoneAuthMode;
  submitText?: string;
  /** 扫码模式内容；仅当 modes 含 qr 时使用 */
  qrPanel?: ReactNode;
  onModeChange?: (mode: PhoneAuthMode) => void;
  /** 手机号变更时回调（如塔吉多清 deviceId） */
  onPhoneChange?: (phone: string, prevPhone: string) => void;
  onSendSms: (phone: string) => Promise<void>;
  onBindSms: (phone: string, code: string) => Promise<void>;
  onBindPassword: (phone: string, password: string) => Promise<void>;
}) {
  const initial =
    defaultMode && modes.includes(defaultMode) ? defaultMode : modes[0];
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

  return (
    <div>
      {title ? (
        <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
          {title}
        </Typography.Text>
      ) : null}
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        {description}
      </Typography.Paragraph>
      {/* Align with Login/Register (~420px); avoid full-bleed inputs in wide cards */}
      <div style={{ width: "100%", maxWidth: 420 }}>
        {modes.length > 1 ? (
          <Segmented
            block
            style={{ marginBottom: 12 }}
            value={mode}
            onChange={(v) => changeMode(v as PhoneAuthMode)}
            options={modes.map((m) => ({ label: MODE_LABEL[m], value: m }))}
          />
        ) : null}

        {mode === "qr" ? (
          qrPanel
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Input
              placeholder="手机号"
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
                <Space.Compact style={{ width: "100%" }}>
                  <Input
                    placeholder="短信验证码"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    autoComplete="one-time-code"
                    inputMode="numeric"
                  />
                  <Button
                    loading={sendingSms}
                    disabled={smsCooldown > 0 || sendingSms}
                    onClick={async () => {
                      if (!phone.trim()) {
                        message.warning("请填写手机号");
                        return;
                      }
                      setSendingSms(true);
                      try {
                        await onSendSms(phone.trim());
                        startSmsCooldown(60);
                        message.success("验证码已发送");
                      } catch (e: unknown) {
                        const detail =
                          e &&
                          typeof e === "object" &&
                          "response" in e &&
                          (e as { response?: { data?: { detail?: string } } })
                            .response?.data?.detail;
                        message.error(
                          String(detail || (e as Error)?.message || "发送验证码失败"),
                        );
                      } finally {
                        setSendingSms(false);
                      }
                    }}
                  >
                    {smsCooldown > 0 ? `${smsCooldown}s` : "获取验证码"}
                  </Button>
                </Space.Compact>
                <Button
                  type="primary"
                  block
                  loading={binding}
                  onClick={async () => {
                    if (!phone.trim() || !code.trim()) {
                      message.warning("请填写手机号与验证码");
                      return;
                    }
                    setBinding(true);
                    try {
                      await onBindSms(phone.trim(), code.trim());
                    } catch (e: unknown) {
                      const detail =
                        e &&
                        typeof e === "object" &&
                        "response" in e &&
                        (e as { response?: { data?: { detail?: string } } })
                          .response?.data?.detail;
                      message.error(
                        String(detail || (e as Error)?.message || "绑定失败"),
                      );
                    } finally {
                      setBinding(false);
                    }
                  }}
                >
                  {submitText}
                </Button>
              </>
            ) : (
              <>
                <Input.Password
                  placeholder="密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <Button
                  type="primary"
                  block
                  loading={binding}
                  onClick={async () => {
                    if (!phone.trim() || !password) {
                      message.warning("请填写手机号与密码");
                      return;
                    }
                    setBinding(true);
                    try {
                      await onBindPassword(phone.trim(), password);
                    } catch (e: unknown) {
                      const detail =
                        e &&
                        typeof e === "object" &&
                        "response" in e &&
                        (e as { response?: { data?: { detail?: string } } })
                          .response?.data?.detail;
                      message.error(
                        String(detail || (e as Error)?.message || "绑定失败"),
                      );
                    } finally {
                      setBinding(false);
                    }
                  }}
                >
                  {submitText}
                </Button>
              </>
            )}
          </Space>
        )}
      </div>
    </div>
  );
}
