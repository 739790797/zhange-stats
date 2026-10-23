export const RARITY_COLOR: Record<number, string> = {
  6: "#f5a623",
  5: "#9b59d0",
  4: "#49b3e6",
  3: "#7dce82",
};

export const SKILL_COLS: { key: string; label: string; match: string[] }[] = [
  {
    key: "normal_attack",
    label: "普攻",
    match: ["skill_type_normal_attack", "normal_attack"],
  },
  {
    key: "normal_skill",
    label: "战技",
    match: ["normal_skill", "skill_type_normal_skill"],
  },
  {
    key: "combo_skill",
    label: "连携技",
    match: ["combo_skill", "skill_type_combo_skill"],
  },
  {
    key: "ultimate_skill",
    label: "终结技",
    match: ["ultimate_skill", "skill_type_ultimate_skill"],
  },
];

/** 按干员属性统一技能底色（同角色四技能同色，对齐小黑盒） */
export const PROPERTY_SKILL_BG: Record<string, string> = {
  灼热: "#c45c3e",
  寒冷: "#5b9fd4",
  自然: "#7cb342",
  电磁: "#d4a017",
  物理: "#8a9099",
};

export const EQUIP_SLOTS: { slot: string; label: string }[] = [
  { slot: "bodyEquip", label: "护甲" },
  { slot: "armEquip", label: "护手" },
  { slot: "firstAccessory", label: "配件·一" },
  { slot: "secondAccessory", label: "配件·二" },
];

export const ROW_GRID =
  "minmax(160px, 1.2fr) minmax(120px, 0.9fr) repeat(4, minmax(64px, 0.55fr)) 24px";
