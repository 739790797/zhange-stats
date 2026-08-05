import { Divider, message } from "antd";
import { useState, type CSSProperties } from "react";
import { startQqOAuthBind, startQqOAuthLogin } from "@/api/client";
import qqLoginBtn from "@/assets/qq_login_btn.png";
import { apiError } from "@/lib/apiError";

type Props = {
  /** login：未登录 QQ 登录；bind：个人中心绑定 QQ */
  mode?: "login" | "bind";
  /** 分隔线文案；传 null 不显示分隔线 */
  dividerText?: string | null;
  /** bind 模式下管理员代绑成员 */
  memberId?: number;
  disabled?: boolean;
  /** 外层额外样式 */
  style?: CSSProperties;
};

/** 官方 Connect_logo 样式按钮（未改图）。 */
export function QqLoginButton({
  mode = "login",
  dividerText = "其他登录方式",
  memberId,
  disabled,
  style,
}: Props) {
  const [loading, setLoading] = useState(false);

  const onClick = async () => {
    if (loading || disabled) return;
    setLoading(true);
    try {
      const { url } =
        mode === "bind"
          ? await startQqOAuthBind(memberId)
          : await startQqOAuthLogin();
      window.location.href = url;
    } catch (e: unknown) {
      message.error(
        apiError(e, mode === "bind" ? "无法跳转 QQ 绑定" : "无法跳转 QQ 登录"),
      );
      setLoading(false);
    }
  };

  const btn = (
    <button
      type="button"
      onClick={onClick}
      disabled={loading || disabled}
      aria-label={mode === "bind" ? "QQ登录绑定" : "QQ登录"}
      style={{
        border: "none",
        background: "transparent",
        padding: 0,
        cursor: loading || disabled ? "not-allowed" : "pointer",
        opacity: loading || disabled ? 0.65 : 1,
        lineHeight: 0,
      }}
    >
      <img
        src={qqLoginBtn}
        alt={mode === "bind" ? "QQ登录" : "QQ登录"}
        width={120}
        height={24}
        style={{ display: "block", width: 120, height: 24 }}
      />
    </button>
  );

  if (dividerText == null) {
    return <div style={style}>{btn}</div>;
  }

  return (
    <div style={{ marginTop: 20, ...style }}>
      <Divider plain style={{ margin: "0 0 16px", fontSize: 13, color: "#8c8c8c" }}>
        {dividerText}
      </Divider>
      <div style={{ textAlign: "center" }}>{btn}</div>
    </div>
  );
}
