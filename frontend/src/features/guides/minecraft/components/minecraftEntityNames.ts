/** 原版实体 id path → 中文名（对齐常见 Wiki 译名） */
export const MINECRAFT_ENTITY_ZH: Record<string, string> = {
  player: "玩家",

  // 掉落
  item: "掉落物",
  experience_orb: "经验球",

  // 友好 / 中立
  allay: "悦灵",
  armadillo: "犰狳",
  axolotl: "美西螈",
  bat: "蝙蝠",
  bee: "蜜蜂",
  camel: "骆驼",
  cat: "猫",
  chicken: "鸡",
  cod: "鳕鱼",
  cow: "牛",
  dolphin: "海豚",
  donkey: "驴",
  fox: "狐狸",
  frog: "青蛙",
  glow_squid: "发光鱿鱼",
  goat: "山羊",
  horse: "马",
  iron_golem: "铁傀儡",
  llama: "羊驼",
  mooshroom: "哞菇",
  mule: "骡",
  ocelot: "豹猫",
  panda: "熊猫",
  parrot: "鹦鹉",
  pig: "猪",
  polar_bear: "北极熊",
  rabbit: "兔子",
  salmon: "鲑鱼",
  sheep: "羊",
  skeleton_horse: "骷髅马",
  sniffer: "嗅探兽",
  snow_golem: "雪傀儡",
  squid: "鱿鱼",
  strider: "炽足兽",
  tadpole: "蝌蚪",
  trader_llama: "行商羊驼",
  tropical_fish: "热带鱼",
  turtle: "海龟",
  villager: "村民",
  wandering_trader: "流浪商人",
  wolf: "狼",
  zombie_horse: "僵尸马",

  // 敌对
  blaze: "烈焰人",
  bogged: "沼骸",
  breeze: "旋风人",
  cave_spider: "洞穴蜘蛛",
  creaking: "嘎枝",
  creeper: "苦力怕",
  drowned: "溺尸",
  elder_guardian: "远古守卫者",
  ender_dragon: "末影龙",
  enderman: "末影人",
  endermite: "末影螨",
  evoker: "唤魔者",
  ghast: "恶魂",
  giant: "巨人",
  guardian: "守卫者",
  hoglin: "疣猪兽",
  husk: "尸壳",
  illusioner: "幻术师",
  magma_cube: "岩浆怪",
  phantom: "幻翼",
  piglin: "猪灵",
  piglin_brute: "猪灵蛮兵",
  pillager: "掠夺者",
  ravager: "劫掠兽",
  shulker: "潜影贝",
  silverfish: "蠹虫",
  skeleton: "骷髅",
  slime: "史莱姆",
  spider: "蜘蛛",
  stray: "流浪者",
  vex: "恼鬼",
  vindicator: "卫道士",
  warden: "监守者",
  witch: "女巫",
  wither: "凋灵",
  wither_skeleton: "凋灵骷髅",
  zoglin: "僵尸疣猪兽",
  zombie: "僵尸",
  zombie_villager: "僵尸村民",
  zombified_piglin: "僵尸猪灵",

  // 弹射物
  arrow: "箭",
  spectral_arrow: "光灵箭",
  trident: "三叉戟",
  snowball: "雪球",
  egg: "鸡蛋",
  ender_pearl: "末影珍珠",
  eye_of_ender: "末影之眼",
  potion: "药水",
  experience_bottle: "附魔之瓶",
  firework_rocket: "烟花火箭",
  fireball: "火球",
  small_fireball: "小火球",
  dragon_fireball: "龙火球",
  wither_skull: "凋灵之首",
  shulker_bullet: "潜影贝导弹",
  llama_spit: "羊驼唾沫",
  fishing_bobber: "浮标",
  wind_charge: "风弹",
  breeze_wind_charge: "旋风人风弹",
  evoker_fangs: "唤魔者尖牙",

  // 载具
  minecart: "矿车",
  chest_minecart: "运输矿车",
  command_block_minecart: "命令方块矿车",
  furnace_minecart: "动力矿车",
  hopper_minecart: "漏斗矿车",
  spawner_minecart: "刷怪笼矿车",
  tnt_minecart: "TNT矿车",
  boat: "船",
  oak_boat: "橡木船",
  spruce_boat: "云杉船",
  birch_boat: "白桦船",
  jungle_boat: "丛林船",
  acacia_boat: "金合欢船",
  dark_oak_boat: "深色橡木船",
  mangrove_boat: "红树船",
  cherry_boat: "樱花船",
  bamboo_raft: "竹筏",
  pale_oak_boat: "苍白橡木船",
  oak_chest_boat: "橡木运输船",
  spruce_chest_boat: "云杉运输船",
  birch_chest_boat: "白桦运输船",
  jungle_chest_boat: "丛林运输船",
  acacia_chest_boat: "金合欢运输船",
  dark_oak_chest_boat: "深色橡木运输船",
  mangrove_chest_boat: "红树运输船",
  cherry_chest_boat: "樱花运输船",
  bamboo_chest_raft: "竹运输筏",
  pale_oak_chest_boat: "苍白橡木运输船",

  // 装饰 / 其它
  armor_stand: "盔甲架",
  item_frame: "物品展示框",
  glow_item_frame: "发光物品展示框",
  painting: "画",
  leash_knot: "拴绳结",
  block_display: "方块展示",
  item_display: "物品展示",
  text_display: "文本展示",
  interaction: "交互实体",
  marker: "标记",
  area_effect_cloud: "区域效果云",
  end_crystal: "末影水晶",
  lightning_bolt: "闪电",
  tnt: "TNT",
  falling_block: "下落的方块",
};

function entityPath(id: string): string {
  const i = id.indexOf(":");
  return i >= 0 ? id.slice(i + 1) : id;
}

function entityNamespace(id: string): string {
  const i = id.indexOf(":");
  return i >= 0 ? id.slice(0, i) : "minecraft";
}

/** 实体展示名：原版走中文表，模组保留 path；未知原版用启发式后缀。 */
export function entityTypeLabel(id: string, fallbackName?: string): string {
  const path = entityPath(id);
  const hit = MINECRAFT_ENTITY_ZH[path];
  if (hit) return hit;

  if (path.endsWith("_chest_boat") || path.endsWith("_chest_raft")) return "运输船";
  if (path.endsWith("_boat") || path.endsWith("_raft")) return "船";
  if (path.endsWith("_minecart")) return "矿车";
  if (path.endsWith("_fireball")) return "火球";
  if (path.endsWith("_bullet")) return "弹射物";

  if (entityNamespace(id) !== "minecraft") {
    return fallbackName || path || id;
  }
  return fallbackName || path || id;
}
