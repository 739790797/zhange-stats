import type { PlatformIconName } from "@/components/PlatformIcon";

/** 攻略区侧栏导航（受 platform_features 开关控制） */
export const GUIDE_NAV: {
  path: string;
  label: string;
  icon: PlatformIconName;
  featureId: string;
}[] = [
  {
    path: "/guides/tarkov",
    label: "逃离塔科夫",
    icon: "tarkov",
    featureId: "guides.tarkov",
  },
];
