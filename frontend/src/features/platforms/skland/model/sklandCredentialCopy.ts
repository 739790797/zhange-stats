/** 森空岛凭证失效的用户可见说明（绑定 / 门禁共用）。 */

export const SKLAND_APP_LOGOUT_HINT =
  "请勿在森空岛 App 内退出登录，否则站内凭证会失效。";

export function sklandBindDescription(tokenBroken: boolean): string {
  if (tokenBroken) {
    return `请重新绑定后再试。${SKLAND_APP_LOGOUT_HINT}`;
  }
  return SKLAND_APP_LOGOUT_HINT;
}
