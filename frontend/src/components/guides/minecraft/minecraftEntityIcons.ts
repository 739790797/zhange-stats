/** 原版实体图标：优先 Mojang 刷怪蛋 / 物品贴图（经 mcasset.cloud 镜像）。 */

const ASSET_VERSION = "1.21.5";
const ASSET_ROOT = `https://assets.mcasset.cloud/${ASSET_VERSION}/assets/minecraft`;

function itemTexture(name: string) {
  return `${ASSET_ROOT}/textures/item/${name}.png`;
}

function blockTexture(name: string) {
  return `${ASSET_ROOT}/textures/block/${name}.png`;
}

/** 无刷怪蛋或刷怪蛋不合适的实体 → 官方物品/方块贴图 */
const TEXTURE_OVERRIDE: Record<string, string> = {
  player: "https://mc-heads.net/avatar/Steve/32",
  item: itemTexture("hopper"),
  experience_orb: itemTexture("experience_bottle"),
  item_frame: itemTexture("item_frame"),
  glow_item_frame: itemTexture("glow_item_frame"),
  armor_stand: itemTexture("armor_stand"),
  painting: itemTexture("painting"),
  leash_knot: itemTexture("lead"),
  minecart: itemTexture("minecart"),
  chest_minecart: itemTexture("chest_minecart"),
  furnace_minecart: itemTexture("furnace_minecart"),
  hopper_minecart: itemTexture("hopper_minecart"),
  tnt_minecart: itemTexture("tnt_minecart"),
  command_block_minecart: itemTexture("command_block_minecart"),
  spawner_minecart: itemTexture("chest_minecart"),
  boat: itemTexture("oak_boat"),
  arrow: itemTexture("arrow"),
  spectral_arrow: itemTexture("spectral_arrow"),
  trident: itemTexture("trident"),
  snowball: itemTexture("snowball"),
  egg: itemTexture("egg"),
  ender_pearl: itemTexture("ender_pearl"),
  eye_of_ender: itemTexture("ender_eye"),
  potion: itemTexture("potion"),
  experience_bottle: itemTexture("experience_bottle"),
  firework_rocket: itemTexture("firework_rocket"),
  fireball: itemTexture("fire_charge"),
  small_fireball: itemTexture("fire_charge"),
  dragon_fireball: itemTexture("dragon_breath"),
  wither_skull: itemTexture("wither_skeleton_skull"),
  fishing_bobber: itemTexture("fishing_rod"),
  wind_charge: itemTexture("wind_charge"),
  breeze_wind_charge: itemTexture("wind_charge"),
  end_crystal: itemTexture("end_crystal"),
  tnt: blockTexture("tnt_side"),
  falling_block: blockTexture("sand"),
  area_effect_cloud: itemTexture("lingering_potion"),
  lightning_bolt: itemTexture("lightning_rod"),
  interaction: itemTexture("name_tag"),
  marker: itemTexture("structure_void"),
  block_display: itemTexture("armor_stand"),
  item_display: itemTexture("item_frame"),
  text_display: itemTexture("name_tag"),
};

function entityPath(id: string): string {
  const i = id.indexOf(":");
  return i >= 0 ? id.slice(i + 1) : id;
}

function entityNamespace(id: string): string {
  const i = id.indexOf(":");
  return i >= 0 ? id.slice(0, i) : "minecraft";
}

/** 返回可展示的图标 URL；模组实体返回 null。 */
export function entityIconUrl(entityId: string): string | null {
  const path = entityPath(entityId);
  if (!path) return null;
  if (entityNamespace(entityId) !== "minecraft") return null;

  const override = TEXTURE_OVERRIDE[path];
  if (override) return override;

  if (
    path.endsWith("_chest_boat") ||
    path.endsWith("_chest_raft") ||
    path.endsWith("_boat") ||
    path.endsWith("_raft")
  ) {
    return itemTexture(path);
  }
  if (path.endsWith("_minecart")) {
    return itemTexture(path);
  }

  return itemTexture(`${path}_spawn_egg`);
}
