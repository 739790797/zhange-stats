import { theme, type ThemeConfig } from "antd";

/** 塔科夫攻略暗色主题。由 `TarkovThemed` / GuideShell 套一层，详情页不要再包。 */
export const TARKOV_ANTD_DARK: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: "#c8932a",
    colorLink: "#c8932a",
    colorInfo: "#c8932a",
    colorBgBase: "#161710",
    colorBgContainer: "#22241a",
    colorBgElevated: "#2b2d22",
    colorBorder: "#3a3d30",
    colorBorderSecondary: "#3a3d30",
    colorText: "#eee9d6",
    colorTextSecondary: "#b0ae9a",
    colorTextTertiary: "#8a8878",
    borderRadius: 2,
    fontFamily:
      '"IBM Plex Sans", "Noto Sans SC", "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif',
  },
  components: {
    Table: {
      headerBg: "#1c1e16",
      headerColor: "#c8c4a8",
      rowHoverBg: "#2b2d22",
      borderColor: "#3a3d30",
      headerSplitColor: "#3a3d30",
      headerSortHoverBg: "#2b2d22",
      headerSortActiveBg: "#2b2d22",
      bodySortBg: "#1c1e16",
      fixedHeaderSortActiveBg: "#2b2d22",
    },
    Card: {
      colorBgContainer: "#22241a",
      colorBorderSecondary: "#3a3d30",
    },
    Input: {
      colorBgContainer: "#1a1b14",
      activeBorderColor: "#c8932a",
    },
    Tag: {
      defaultBg: "#1c1e16",
      defaultColor: "#c8c4a8",
    },
    Descriptions: {
      labelBg: "#1c1e16",
    },
    Button: {
      defaultBg: "#22241a",
      defaultBorderColor: "#3a3d30",
      defaultColor: "#c8c4a8",
    },
  },
};
