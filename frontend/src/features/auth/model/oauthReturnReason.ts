/**
 * QQ / Steam 回跳只带固定 reason 码（码表见 docs/security.md「OAuth 回跳参数」）。
 * 界面只认这些码的固定文案；URL 里的任何其他参数原文都不展示。
 */
export type OauthReturnFlow = "qq_login" | "qq_bind" | "steam_bind";

const FLOW_LABEL: Record<OauthReturnFlow, string> = {
  qq_login: "QQ 登录",
  qq_bind: "QQ 绑定",
  steam_bind: "Steam 绑定",
};

const FALLBACK: Record<OauthReturnFlow, string> = {
  qq_login: "QQ 登录失败，请重试",
  qq_bind: "绑定失败，请重试",
  steam_bind: "绑定失败，请重试",
};

function providerOf(flow: OauthReturnFlow): string {
  return flow === "steam_bind" ? "Steam" : "QQ";
}

function reasonText(flow: OauthReturnFlow, reason: string): string | null {
  const provider = providerOf(flow);
  switch (reason) {
    case "state_invalid":
      return "授权已过期或无效，请重新发起";
    case "browser_mismatch":
      return "请在发起授权的同一个浏览器里完成（不要换浏览器或清除 Cookie）";
    case "upstream_error":
      return `${provider} 接口暂时不可用，请稍后重试`;
    case "server_error":
      return "服务器出错，请稍后重试";
    case "missing_code":
      return "QQ 没有返回授权码，请重试";
    case "account_create_failed":
      return "无法自动创建账号，请联系管理员";
    case "user_not_found":
      return "发起绑定的账号已不存在";
    case "member_not_found":
      return "要绑定的成员已不存在";
    case "forbidden":
      return "只有管理员可以给其他成员绑定";
    case "already_bound":
      return `该 ${provider} 账号已绑定在其他成员上`;
    case "verify_failed":
      return "Steam 登录校验未通过，请重新发起";
    case "expired":
      return "Steam 登录已超时，请重新发起";
    case "replayed":
      return "这次 Steam 登录回执已经用过，请重新发起";
    case "steam_private":
      return "Steam 资料未公开，请在 Steam 隐私设置里公开个人资料后重试";
    case "steam_not_found":
      return "找不到该 Steam 账号";
    case "feature_disabled":
      return "Steam 功能已关闭";
    default:
      return null;
  }
}

/** 失败回跳的提示文案；未知码或无码给通用文案。 */
export function oauthFailureMessage(
  flow: OauthReturnFlow,
  reason: string | null | undefined,
): string {
  const code = (reason || "").trim();
  if (code === "cancelled") return `已取消 ${FLOW_LABEL[flow]}`;
  const text = code ? reasonText(flow, code) : null;
  return text ? `${FLOW_LABEL[flow]}失败：${text}` : FALLBACK[flow];
}

/** 回跳处理完要从地址栏去掉的参数（含旧版带原文的 detail / name）。 */
export const OAUTH_RETURN_PARAMS = ["reason", "detail", "name"] as const;
