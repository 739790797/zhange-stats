/** 运行环境「环境」卡片里需要先确认再保存的开关。 */
export type RuntimeEnvFlags = {
  app_env: string;
  csp_enforce: boolean;
  trust_x_forwarded_for: boolean;
  rate_limit_enabled: boolean;
};

export function isProductionEnv(value: string | null | undefined): boolean {
  const v = (value || "").trim().toLowerCase();
  return v === "production" || v === "prod";
}

/**
 * 本次保存真正切到高风险状态的项与后果；空数组表示不用确认。
 * after 是实际要提交的字段（环境变量锁定的项不在里面）。
 */
export function runtimeEnvRiskNotes(
  before: RuntimeEnvFlags,
  after: Partial<RuntimeEnvFlags>,
): string[] {
  const notes: string[] = [];
  if (
    after.app_env !== undefined &&
    isProductionEnv(after.app_env) &&
    !isProductionEnv(before.app_env)
  ) {
    notes.push(
      "切到 production：重启后按生产口径体检，管理员弱口令、ALLOW_EMAIL_CODE_LOG 等不过关会拒绝启动；会话 Cookie 一律带 Secure，只用 HTTP 访问将无法保持登录。",
    );
  }
  if (after.csp_enforce === true && !before.csp_enforce) {
    notes.push(
      "强制 CSP：策略外的脚本、样式、连接会被浏览器直接拦截（此前只上报）。请先确认 CSP 上报日志里没有误杀联机 WS、地图、KaTeX、极验。",
    );
  }
  if (after.trust_x_forwarded_for === true && !before.trust_x_forwarded_for) {
    notes.push(
      "信任 X-Forwarded-For：仅当站点在可信反向代理之后才打开；直连时任何人都能伪造该头冒充别的 IP，绕过限流。",
    );
  }
  if (after.rate_limit_enabled === false && before.rate_limit_enabled) {
    notes.push("关闭接口限流：登录、注册、发码等接口不再限次，只适合临时排障或压测。");
  }
  return notes;
}
