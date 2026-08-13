import type { PlatformIconName } from "@/components/PlatformIcon";

/** 攻略区侧栏：一点进大厅；栏目在页内顶栏。 */

export type GuideNavLeaf = {
  kind: "leaf";
  path: string;
  label: string;
  featureId: string;
  icon?: PlatformIconName;
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
    kind: "leaf",
    path: "/guides/tarkov",
    label: "逃离塔科夫",
    featureId: "guides.tarkov",
    icon: "tarkov",
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
