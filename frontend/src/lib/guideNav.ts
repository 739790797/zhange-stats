import type { PlatformIconName } from "@/components/PlatformIcon";

/** 攻略区侧栏树：按上游 API 域分级（tarkov.dev Query 顶层）。 */

export type GuideNavLeaf = {
  kind: "leaf";
  path: string;
  label: string;
  featureId: string;
};

export type GuideNavGroup = {
  kind: "group";
  key: string;
  label: string;
  featureId: string;
  icon?: PlatformIconName;
  children: GuideNavNode[];
};

export type GuideNavNode = GuideNavLeaf | GuideNavGroup;

export const GUIDE_NAV: GuideNavNode[] = [
  {
    kind: "group",
    key: "guides-tarkov",
    label: "逃离塔科夫",
    featureId: "guides.tarkov",
    icon: "tarkov",
    children: [
      {
        kind: "group",
        key: "guides-tarkov-items",
        label: "物品",
        featureId: "guides.tarkov",
        children: [
          {
            kind: "leaf",
            path: "/guides/tarkov/items/ammo",
            label: "弹药",
            featureId: "guides.tarkov",
          },
          {
            kind: "leaf",
            path: "/guides/tarkov/items/guns",
            label: "枪械",
            featureId: "guides.tarkov",
          },
        ],
      },
      {
        kind: "leaf",
        path: "/guides/tarkov/tasks",
        label: "任务",
        featureId: "guides.tarkov",
      },
      {
        kind: "leaf",
        path: "/guides/tarkov/maps",
        label: "地图",
        featureId: "guides.tarkov",
      },
    ],
  },
];

export function flattenGuideLeaves(nodes: GuideNavNode[] = GUIDE_NAV): GuideNavLeaf[] {
  const out: GuideNavLeaf[] = [];
  for (const node of nodes) {
    if (node.kind === "leaf") out.push(node);
    else out.push(...flattenGuideLeaves(node.children));
  }
  return out;
}

export const GUIDE_LEAF_PATHS = flattenGuideLeaves().map((n) => n.path);
