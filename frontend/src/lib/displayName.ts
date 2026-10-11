/** 与后端 DISPLAY_NAME_MARKUP_ERROR 同文案；后端仍会再拦一次。 */
export const DISPLAY_NAME_MARKUP_ERROR = "显示名不能包含 < 或 >";

export const DISPLAY_NAME_MAX_LENGTH = 64;

export function displayNameError(value: string | null | undefined): string | null {
  if (/[<>]/.test(value || "")) return DISPLAY_NAME_MARKUP_ERROR;
  return null;
}

/** 显示名输入框的 antd 规则；必填另配 required。 */
export const displayNameRules = [
  { max: DISPLAY_NAME_MAX_LENGTH, message: `最多 ${DISPLAY_NAME_MAX_LENGTH} 字` },
  {
    validator: async (_rule: unknown, value: unknown) => {
      const error = displayNameError(typeof value === "string" ? value : "");
      if (error) throw new Error(error);
    },
  },
];
