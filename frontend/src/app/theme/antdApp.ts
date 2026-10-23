import type { ThemeConfig } from "antd";
import { BRAND_NAVY } from "@/shared/styles/tokens";


export const antdAppTheme: ThemeConfig = {
  token: {
    colorPrimary: BRAND_NAVY,
    colorLink: BRAND_NAVY,
    colorPrimaryHover: "#2c3a4d",
    colorPrimaryActive: "#121821",
    borderRadius: 6,
    fontFamily:
      '"Source Han Sans SC", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  components: {
    Button: {
      primaryShadow: "none",
      defaultShadow: "none",
    },
    Modal: {
      margin: 12,
    },
  },
};

/** 系统减动时关掉 antd 进出场（Modal / Drawer / Collapse 等）。 */
export function antdThemeWithMotion(enableMotion: boolean): ThemeConfig {
  return {
    ...antdAppTheme,
    token: {
      ...antdAppTheme.token,
      motion: enableMotion,
    },
  };
}
