import { theme, type ThemeConfig } from "antd";
import { TARKOV_TOKENS } from "@zhange-base/src/tokens.js";

const { color, font, antd } = TARKOV_TOKENS;

/** 塔科夫攻略暗色主题。由 `TarkovThemed` / GuideShell 套一层，详情页不要再包。 */
export const TARKOV_ANTD_DARK: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: color.accent,
    colorLink: color.accent,
    colorInfo: color.accent,
    colorBgBase: color.bg,
    colorBgContainer: color.panel,
    colorBgElevated: color.panelHover,
    colorBorder: color.border,
    colorBorderSecondary: color.border,
    colorText: color.text,
    colorTextSecondary: color.textMuted,
    colorTextTertiary: color.textTertiary,
    borderRadius: antd.borderRadius,
    fontFamily: font.sans,
  },
  components: {
    Table: {
      headerBg: color.surfaceStrong,
      headerColor: color.textWarm,
      rowHoverBg: color.panelHover,
      borderColor: color.border,
      headerSplitColor: color.border,
      headerSortHoverBg: color.panelHover,
      headerSortActiveBg: color.panelHover,
      bodySortBg: color.surfaceStrong,
      fixedHeaderSortActiveBg: color.panelHover,
    },
    Card: {
      colorBgContainer: color.panel,
      colorBorderSecondary: color.border,
    },
    Input: {
      colorBgContainer: color.control,
      activeBorderColor: color.accent,
    },
    Tag: {
      defaultBg: color.surfaceStrong,
      defaultColor: color.textWarm,
    },
    Descriptions: {
      labelBg: color.surfaceStrong,
    },
    Button: {
      defaultBg: color.panel,
      defaultBorderColor: color.border,
      defaultColor: color.textWarm,
    },
  },
};
