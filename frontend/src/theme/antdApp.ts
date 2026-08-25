import type { ThemeConfig } from "antd";

/** 主应用品牌海军蓝。塔科夫攻略用 `TARKOV_ANTD_DARK`，勿把该色写进 Button style。 */
export const BRAND_NAVY = "#1a2332";

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
  },
};
