export type PhoneAuthMode = "qr" | "sms" | "password";

/** 默认选中优先级：扫码 > 短信验证码 > 账号密码 */
const PHONE_AUTH_MODE_PRIORITY: PhoneAuthMode[] = ["qr", "sms", "password"];

export function preferredPhoneAuthMode(modes: PhoneAuthMode[]): PhoneAuthMode {
  return PHONE_AUTH_MODE_PRIORITY.find((m) => modes.includes(m)) ?? modes[0];
}

export function orderedPhoneAuthModes(modes: PhoneAuthMode[]): PhoneAuthMode[] {
  return PHONE_AUTH_MODE_PRIORITY.filter((m) => modes.includes(m));
}
