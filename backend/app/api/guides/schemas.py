from pydantic import BaseModel, Field, field_validator


class TarkovAmmoItemOut(BaseModel):
    id: str
    name: str
    short_name: str = ""
    caliber: str
    ammo_type: str = ""
    damage: int
    penetration: int
    armor_damage: int = 0
    initial_speed: float = 0
    accuracy_modifier: float = 0
    recoil_modifier: float = 0
    light_bleed_modifier: float = 0
    heavy_bleed_modifier: float = 0
    icon_link: str = ""
    pack_icon_link: str = ""
    pack_item_id: str = ""


class TarkovAmmoDetailOut(BaseModel):
    """弹药详情：来自 items raw 的完整 item + properties。"""

    id: str
    name: str
    short_name: str = ""
    description: str = ""
    source: str | None = None
    item: dict = Field(default_factory=dict)
    properties: dict = Field(default_factory=dict)


class TarkovAmmoCatalogOut(BaseModel):
    items: list[TarkovAmmoItemOut]
    ammo_count: int
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovAmmoSyncOut(BaseModel):
    ammo_count: int
    gun_count: int = 0
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")


class TarkovItemsSyncOut(BaseModel):
    ammo_count: int
    gun_count: int
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")


class TarkovFullSyncDomainOut(BaseModel):
    id: str
    ok: bool
    error: str | None = None
    source: str | None = None
    synced_at: str | None = None


class TarkovFullSyncOut(BaseModel):
    ok_count: int
    failed_count: int
    domains: list[TarkovFullSyncDomainOut] = Field(default_factory=list)
    message: str = Field(default="ok")


class TarkovGunItemOut(BaseModel):
    id: str
    name: str
    short_name: str = ""
    caliber: str
    weapon_class: str = ""
    fire_rate: int = 0
    ergonomics: float = 0
    recoil_vertical: int = 0
    recoil_horizontal: int = 0
    effective_distance: int = 0
    fire_modes: list[str] = Field(default_factory=list)
    default_ammo_id: str = ""
    allowed_ammo_ids: list[str] = Field(default_factory=list)
    icon_link: str = ""


class TarkovGunCatalogOut(BaseModel):
    items: list[TarkovGunItemOut]
    gun_count: int
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovGunSyncOut(BaseModel):
    ammo_count: int = 0
    gun_count: int
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")


class TarkovWorkbenchPartOut(BaseModel):
    id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    ergonomics: float = 0
    recoil_modifier: float = 0
    weight: float = 0
    price_rub: int | None = None
    sighting_range: int | None = None
    mag_capacity: int | None = None
    conflicting_ids: list[str] = Field(default_factory=list)


class TarkovWorkbenchPairOut(BaseModel):
    slot_id: str = Field(max_length=64)
    item_id: str = Field(max_length=64)


class TarkovWorkbenchSlotNodeOut(BaseModel):
    id: str
    name: str
    name_id: str = ""
    required: bool = False
    parent_item_id: str = ""
    installed: TarkovWorkbenchPartOut | None = None
    children: list["TarkovWorkbenchSlotNodeOut"] = Field(default_factory=list)


class TarkovWorkbenchStatsOut(BaseModel):
    ergonomics: float = 0
    recoil_vertical: int = 0
    recoil_horizontal: int = 0
    weight: float = 0
    sighting_range: int | None = None
    mag_capacity: int | None = None
    price_rub: int | None = None
    conflicts: list[str] = Field(default_factory=list)
    overswing: bool = False
    ammo_id: str | None = None
    accuracy_moa: float | None = None
    muzzle_velocity: int | None = None
    arm_stamina: float | None = None
    evo_ergo_delta: float = 0


class TarkovWorkbenchGunOut(BaseModel):
    id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    image_link: str = ""
    preset_image_link: str = ""
    caliber: str = ""
    slots: list[TarkovWorkbenchSlotNodeOut] = Field(default_factory=list)
    factory_pairs: list[TarkovWorkbenchPairOut] = Field(default_factory=list)
    ammo: list[TarkovWorkbenchPartOut] = Field(default_factory=list)
    default_ammo_id: str = ""
    stats: TarkovWorkbenchStatsOut
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovWorkbenchAllowedIn(BaseModel):
    slot_ids: list[str] = Field(default_factory=list, max_length=200)


class TarkovWorkbenchAllowedOut(BaseModel):
    slots: dict[str, list[TarkovWorkbenchPartOut]] = Field(default_factory=dict)


class TarkovWorkbenchCalculateIn(BaseModel):
    gun_id: str = Field(max_length=64)
    pairs: list[TarkovWorkbenchPairOut] = Field(default_factory=list, max_length=200)
    ammo_id: str | None = Field(default=None, max_length=64)


class TarkovWorkbenchCalculateOut(BaseModel):
    slots: list[TarkovWorkbenchSlotNodeOut] = Field(default_factory=list)
    stats: TarkovWorkbenchStatsOut


class TarkovWorkbenchImageStatusOut(BaseModel):
    enabled: bool = True
    busy: bool = False
    message: str | None = None


class TarkovWorkbenchImageOut(BaseModel):
    kind: str
    image_url: str | None = None
    busy: bool = False
    message: str | None = None
    enabled: bool = True


class TarkovWorkbenchCommunityPreviewOut(BaseModel):
    ergonomics: float | None = None
    evo_ergo_delta: float | None = None
    recoil_vertical: int | None = None
    recoil_horizontal: int | None = None
    weight: float | None = None
    price_rub: int | None = None
    overswing: bool = False


class TarkovWorkbenchCommunityBuildOut(BaseModel):
    id: str
    name: str
    author: str = ""
    featured: bool = False
    tags: list[str] = Field(default_factory=list)
    published_at: str | None = None
    load_count: int = 0
    ammo_id: str | None = None
    pairs: list[TarkovWorkbenchPairOut] = Field(default_factory=list)
    loadable: bool = False
    dropped_pair_count: int = 0
    preview: TarkovWorkbenchCommunityPreviewOut | None = None


class TarkovWorkbenchCommunityBuildsOut(BaseModel):
    source: str
    source_url: str
    gun_id: str
    builds: list[TarkovWorkbenchCommunityBuildOut] = Field(default_factory=list)


class TarkovCatalogItemOut(BaseModel):
    id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    handbook_ids: list[str] = Field(default_factory=list)
    properties_type: str = ""
    weight: float | None = None
    width: int | None = None
    height: int | None = None
    base_price: int | None = None
    avg24h_price: int | None = None
    last_low_price: int | None = None
    properties: dict = Field(default_factory=dict)


class TarkovCatalogOut(BaseModel):
    items: list[TarkovCatalogItemOut]
    item_count: int
    page: int = 1
    page_size: int = 50
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovItemKeyLockOut(BaseModel):
    id: str = ""
    lock_type: str = ""
    needs_power: bool = False
    x: float | None = None
    y: float | None = None
    z: float | None = None
    top: float | None = None
    bottom: float | None = None


class TarkovItemKeyLockMapOut(BaseModel):
    slug: str
    name: str
    english: str = ""
    parent_slug: str = ""
    locks: list[TarkovItemKeyLockOut] = Field(default_factory=list)


class TarkovItemDetailOut(BaseModel):
    """通用物品详情：来自 items raw 的完整 item + properties。"""

    id: str
    name: str
    short_name: str = ""
    description: str = ""
    source: str | None = None
    item: dict = Field(default_factory=dict)
    properties: dict = Field(default_factory=dict)
    locks: list[TarkovItemKeyLockMapOut] = Field(default_factory=list)
    sources: "TarkovItemSourcesOut" = Field(default_factory=dict)
    uses: "TarkovItemUsesOut" = Field(default_factory=dict)


class TarkovTaskNamedRefOut(BaseModel):
    id: str
    slug: str = ""
    name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)


class TarkovTaskFailTaskRefOut(BaseModel):
    id: str
    slug: str = ""
    name: str = ""
    trader_id: str = ""
    trader_slug: str = ""
    trader_name: str = ""


class TarkovTaskTraderChipOut(BaseModel):
    id: str
    slug: str
    name: str


class TarkovTaskTraderReqOut(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    requirement_type: str = ""
    value: float = 0
    compare_method: str = ""


class TarkovTaskListItemOut(BaseModel):
    id: str
    name: str
    normalized_name: str = ""
    trader_id: str = ""
    trader_slug: str = ""
    trader_name: str = ""
    map_id: str = ""
    map_slug: str = ""
    map_name: str = ""
    min_player_level: int = 0
    min_trader_level: int = 1
    experience: int = 0
    lightkeeper_required: bool = False
    kappa_required: bool = False
    faction_name: str = "Any"
    task_image_link: str = ""
    wiki_link: str = ""
    objective_count: int = 0
    objective_types: list[str] = Field(default_factory=list)
    line_hint: str = ""
    mutex_ids: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    prereq_ids: list[str] = Field(default_factory=list)


class TarkovTaskCatalogOut(BaseModel):
    items: list[TarkovTaskListItemOut]
    task_count: int
    page: int = 1
    page_size: int = 50
    traders: list[TarkovTaskTraderChipOut] = Field(default_factory=list)
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovTaskNumberCompareOut(BaseModel):
    compare_method: str = ""
    value: float | None = None


class TarkovTaskHealthEffectOut(BaseModel):
    body_parts: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    time: TarkovTaskNumberCompareOut | None = None


class TarkovTaskAttributeOut(BaseModel):
    name: str = ""
    compare_method: str = ""
    value: float | None = None


class TarkovTaskObjectiveOut(BaseModel):
    id: str
    type: str = ""
    description: str = ""
    optional: bool = False
    count: int | None = None
    maps: list[TarkovTaskNamedRefOut] = Field(default_factory=list)
    items: list[TarkovTaskNamedRefOut] = Field(default_factory=list)
    found_in_raid: bool | None = None
    required_keys: list[list[TarkovTaskNamedRefOut]] = Field(default_factory=list)
    exit_status: list[str] = Field(default_factory=list)
    exit_name: str = ""
    zones: list["TarkovTaskZoneOut"] = Field(default_factory=list)
    possible_locations: list["TarkovTaskPossibleLocationOut"] = Field(
        default_factory=list
    )
    zone_names: list[str] = Field(default_factory=list)
    target_names: list[str] = Field(default_factory=list)
    body_parts: list[str] = Field(default_factory=list)
    shot_type: str = ""
    distance: TarkovTaskNumberCompareOut | None = None
    using_weapon: list[TarkovTaskNamedRefOut] = Field(default_factory=list)
    using_weapon_mods: list[list[TarkovTaskNamedRefOut]] = Field(default_factory=list)
    wearing: list[list[TarkovTaskNamedRefOut]] = Field(default_factory=list)
    not_wearing: list[TarkovTaskNamedRefOut] = Field(default_factory=list)
    use_any: list[TarkovTaskNamedRefOut] = Field(default_factory=list)
    contains_all: list[TarkovTaskNamedRefOut] = Field(default_factory=list)
    contains_category: list[TarkovTaskNamedRefOut] = Field(default_factory=list)
    attributes: list[TarkovTaskAttributeOut] = Field(default_factory=list)
    health_effect: TarkovTaskHealthEffectOut | None = None
    player_health_effect: TarkovTaskHealthEffectOut | None = None
    enemy_health_effect: TarkovTaskHealthEffectOut | None = None
    time_from_hour: int | None = None
    time_until_hour: int | None = None
    dog_tag_level: int | None = None
    min_durability: int | None = None
    max_durability: int | None = None
    skill_name: str = ""
    skill_level: int | None = None
    hideout_station: TarkovTaskNamedRefOut | None = None
    station_level: int | None = None
    trader: TarkovTaskNamedRefOut | None = None
    trader_level: int | None = None
    standing: TarkovTaskNumberCompareOut | None = None
    player_level: int | None = None
    related_tasks: list[TarkovTaskFailTaskRefOut] = Field(default_factory=list)
    related_status: list[str] = Field(default_factory=list)


class TarkovTaskPointOut(BaseModel):
    x: float
    y: float = 0
    z: float


class TarkovTaskZoneOut(BaseModel):
    id: str = ""
    map_id: str = ""
    map_slug: str = ""
    map_name: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None
    outline: list[TarkovTaskPointOut] = Field(default_factory=list)
    top: float | None = None
    bottom: float | None = None


class TarkovTaskPossibleLocationOut(BaseModel):
    map_id: str = ""
    map_slug: str = ""
    map_name: str = ""
    positions: list[TarkovTaskPointOut] = Field(default_factory=list)


class TarkovTaskFailConditionOut(BaseModel):
    id: str = ""
    type: str = ""
    description: str = ""
    status: list[str] = Field(default_factory=list)
    tasks: list[TarkovTaskFailTaskRefOut] = Field(default_factory=list)
    exit_status: list[str] = Field(default_factory=list)
    trader: TarkovTaskNamedRefOut | None = None


class TarkovRaidPrepTaskOut(TarkovTaskListItemOut):
    objectives: list[TarkovTaskObjectiveOut] = Field(default_factory=list)
    needed_keys: list["TarkovTaskNeededKeysOut"] = Field(default_factory=list)
    fail_conditions: list[TarkovTaskFailConditionOut] = Field(default_factory=list)
    has_map_markers: bool = False


class TarkovRaidPrepOut(BaseModel):
    map_slug: str
    map_name: str = ""
    items: list[TarkovRaidPrepTaskOut]
    task_count: int
    traders: list[TarkovTaskTraderChipOut] = Field(default_factory=list)
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovTaskRewardItemOut(BaseModel):
    id: str
    slug: str = ""
    name: str = ""
    count: int = 1
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)


class TarkovTaskStandingOut(BaseModel):
    id: str
    slug: str = ""
    name: str = ""
    standing: float = 0


class TarkovTaskOfferUnlockOut(BaseModel):
    id: str = ""
    trader: TarkovTaskNamedRefOut | None = None
    level: int = 0
    item: TarkovTaskNamedRefOut | None = None


class TarkovTaskSkillRewardOut(BaseModel):
    name: str = ""
    level: int = 0


class TarkovTaskCraftUnlockOut(BaseModel):
    id: str = ""
    station: TarkovTaskNamedRefOut | None = None
    level: int = 0
    item: TarkovTaskNamedRefOut | None = None


class TarkovTaskImageRefOut(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    image_link: str = ""
    customization_type: str = ""


class TarkovTaskFinishRewardsOut(BaseModel):
    items: list[TarkovTaskRewardItemOut] = Field(default_factory=list)
    trader_standing: list[TarkovTaskStandingOut] = Field(default_factory=list)
    offer_unlock: list[TarkovTaskOfferUnlockOut] = Field(default_factory=list)
    skill_level_reward: list[TarkovTaskSkillRewardOut] = Field(default_factory=list)
    trader_unlock: list[TarkovTaskNamedRefOut] = Field(default_factory=list)
    craft_unlock: list[TarkovTaskCraftUnlockOut] = Field(default_factory=list)
    achievement: list[TarkovTaskImageRefOut] = Field(default_factory=list)
    customization: list[TarkovTaskImageRefOut] = Field(default_factory=list)


class TarkovTaskNeededKeysOut(BaseModel):
    map: TarkovTaskNamedRefOut
    keys: list[TarkovTaskNamedRefOut] = Field(default_factory=list)


class TarkovTaskRequirementOut(TarkovTaskFailTaskRefOut):
    status: list[str] = Field(default_factory=list)


class TarkovTaskPrestigeOut(BaseModel):
    id: str = ""
    name: str = ""
    prestige_level: int = 0
    image_link: str = ""


class TarkovTaskDialogueOut(BaseModel):
    description: str = ""
    start: str = ""
    success: str = ""
    fail: str = ""


TarkovTaskObjectiveOut.model_rebuild()
TarkovRaidPrepTaskOut.model_rebuild()
TarkovRaidPrepOut.model_rebuild()


class TarkovTaskDetailOut(TarkovTaskListItemOut):
    source: str | None = None
    objectives: list[TarkovTaskObjectiveOut] = Field(default_factory=list)
    trader_requirements: list[TarkovTaskTraderReqOut] = Field(default_factory=list)
    task_requirements: list[TarkovTaskRequirementOut] = Field(default_factory=list)
    unlocks: list[TarkovTaskRequirementOut] = Field(default_factory=list)
    start_rewards: TarkovTaskFinishRewardsOut = Field(
        default_factory=TarkovTaskFinishRewardsOut
    )
    finish_rewards: TarkovTaskFinishRewardsOut = Field(
        default_factory=TarkovTaskFinishRewardsOut
    )
    fail_rewards: TarkovTaskFinishRewardsOut = Field(
        default_factory=TarkovTaskFinishRewardsOut
    )
    needed_keys: list[TarkovTaskNeededKeysOut] = Field(default_factory=list)
    fail_conditions: list[TarkovTaskFailConditionOut] = Field(default_factory=list)
    restartable: bool = False
    required_prestige: TarkovTaskPrestigeOut | None = None
    available_delay_seconds_min: int | None = None
    available_delay_seconds_max: int | None = None
    dialogue: TarkovTaskDialogueOut = Field(default_factory=TarkovTaskDialogueOut)


class TarkovTasksSyncOut(BaseModel):
    task_count: int
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")


class TarkovTraderLevelOut(BaseModel):
    level: int
    required_player_level: int = 0
    required_reputation: float = 0
    required_commerce: int = 0


class TarkovTraderOfferOut(BaseModel):
    trader_id: str
    item_id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    avg24h_price: int | None = None
    last_low_price: int | None = None
    price: int = 0
    price_rub: int = 0
    currency: str = "RUB"
    min_trader_level: int = 1
    buy_limit: int | None = None
    task_unlock_id: str = ""
    task_unlock_name: str = ""


class TarkovTraderListItemOut(BaseModel):
    id: str
    slug: str
    english: str
    chinese: str = ""
    name: str
    description: str = ""
    image_link: str = ""
    portrait_link: str = ""
    wiki_link: str = ""
    reset_time: str = ""
    currency: str = "RUB"
    levels: list[TarkovTraderLevelOut] = Field(default_factory=list)
    offer_count: int = 0


class TarkovTraderCatalogOut(BaseModel):
    items: list[TarkovTraderListItemOut]
    trader_count: int
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovTraderDetailOut(TarkovTraderListItemOut):
    items: list[TarkovTraderOfferOut] = Field(default_factory=list)
    page: int = 1
    page_size: int = 50
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovTradersSyncOut(BaseModel):
    trader_count: int
    offer_count: int = 0
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")


class TarkovBossHealthPartOut(BaseModel):
    id: str
    name: str
    max: int = 0


class TarkovBossMapOut(BaseModel):
    id: str = ""
    slug: str = ""
    name: str
    spawn_chance: str = ""


class TarkovBossSpawnPointOut(BaseModel):
    x: float
    y: float = 0
    z: float


class TarkovBossSpawnLocationOut(BaseModel):
    map: str = ""
    map_slug: str = ""
    name: str = ""
    chance: float = 0
    positions: list[TarkovBossSpawnPointOut] = Field(default_factory=list)


class TarkovBossEscortOut(BaseModel):
    slug: str = ""
    name: str = ""
    count: int = 0
    chance: float = 0
    map: str = ""
    map_slug: str = ""


class TarkovBossSpawnGroupMapOut(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    spawn_chance: str = ""


class TarkovBossSpawnGroupOut(BaseModel):
    maps: list[TarkovBossSpawnGroupMapOut] = Field(default_factory=list)
    shared_spawn_chance: str = ""
    land_label: str = ""
    locations: list[TarkovBossSpawnLocationOut] = Field(default_factory=list)
    escorts: list[TarkovBossEscortOut] = Field(default_factory=list)
    show_location_chance: bool = False


class TarkovBossGearContainedOut(BaseModel):
    item_id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    count: int = 1
    kind: str = Field(
        default="",
        description="magazine | ammo | plate | other",
    )
    damage: int | None = None
    penetration: int | None = None
    armor_damage: int | None = None
    armor_class: int | None = Field(
        default=None,
        description="防弹插板护甲等级（1–6）",
    )


class TarkovBossGearItemOut(BaseModel):
    item_id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    count: int = 1
    armor_class: int | None = Field(
        default=None,
        description="防弹插板护甲等级（1–6）",
    )
    contains: list[TarkovBossGearContainedOut] = Field(default_factory=list)


class TarkovBossGearSlotOut(BaseModel):
    key: str
    label: str
    items: list[TarkovBossGearItemOut] = Field(default_factory=list)


class TarkovBossListItemOut(BaseModel):
    id: str
    slug: str
    name: str
    kind: str = Field(
        default="boss",
        description="boss=具名 BOSS；elite=掠夺者/游荡者/邪教徒等；soldier=BEAR/USEC/守军等小兵",
    )
    behavior: str = ""
    behavior_zh: str = ""
    maps_label: str = ""
    spawn_label: str = ""
    spawn_short: str = ""
    escorts_label: str = ""
    health_total: int = 0
    portrait_link: str = ""
    poster_link: str = ""
    wiki_link: str = ""
    parent_ids: list[str] = Field(
        default_factory=list,
        description="护卫所属父级 mob id（如 bossGluhar）；具名 BOSS 为空",
    )
    spawn_groups: list[TarkovBossSpawnGroupOut] = Field(
        default_factory=list,
        description="同一套刷法（随从+落地）合并多图；地点横向、随从只写一次",
    )


class TarkovBossCatalogOut(BaseModel):
    items: list[TarkovBossListItemOut]
    boss_count: int
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovBossDetailOut(TarkovBossListItemOut):
    description: str = ""
    bio: str = ""
    health: list[TarkovBossHealthPartOut] = Field(default_factory=list)
    maps: list[TarkovBossMapOut] = Field(default_factory=list)
    spawn_locations: list[TarkovBossSpawnLocationOut] = Field(default_factory=list)
    escorts: list[TarkovBossEscortOut] = Field(default_factory=list)
    equipment_slots: list[TarkovBossGearSlotOut] = Field(
        default_factory=list,
        description="完整配装：按装备栏分组，枪内弹药/配件在 contains",
    )
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovBossesSyncOut(BaseModel):
    boss_count: int
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")


class TarkovSearchHitOut(BaseModel):
    id: str
    name: str
    extra: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    slug: str = ""


class TarkovSiteSearchOut(BaseModel):
    q: str
    items: list[TarkovSearchHitOut] = Field(default_factory=list)
    tasks: list[TarkovSearchHitOut] = Field(default_factory=list)
    traders: list[TarkovSearchHitOut] = Field(default_factory=list)
    bosses: list[TarkovSearchHitOut] = Field(default_factory=list)
    item_count: int = 0
    task_count: int = 0
    trader_count: int = 0
    boss_count: int = 0


class TarkovMapPointOut(BaseModel):
    x: float
    y: float = 0
    z: float


class TarkovMapBossLocationOut(BaseModel):
    name: str = ""
    chance: float = 0
    positions: list[TarkovMapPointOut] = Field(default_factory=list)


class TarkovMapBossOut(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    kind: str = Field(
        default="boss",
        description="boss=具名 BOSS；elite=掠夺者/游荡者/邪教徒等；soldier=BEAR/USEC/守军等小兵",
    )
    spawn_chance: int = 0
    locations: list[TarkovMapBossLocationOut] = Field(default_factory=list)


class TarkovMapExtractSwitchOut(BaseModel):
    id: str = ""
    name: str = ""


class TarkovMapItemRefOut(BaseModel):
    id: str = ""
    name: str = ""
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    handbook_ids: list[str] = Field(default_factory=list)
    count: int = 1


class TarkovMapExtractOut(BaseModel):
    id: str = ""
    name: str = ""
    faction: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None
    top: float | None = None
    bottom: float | None = None
    outline: list[TarkovTaskPointOut] = Field(default_factory=list)
    switches: list[TarkovMapExtractSwitchOut] = Field(default_factory=list)
    transfer_item: TarkovMapItemRefOut | None = None


class TarkovMapSpawnOut(BaseModel):
    """PMC / Scav / 狙击 Scav 出生点；Boss 仍走 bosses.locations。"""

    kind: str = ""
    zone_name: str = ""
    x: float
    y: float = 0
    z: float


class TarkovMapLockOut(BaseModel):
    id: str = ""
    lock_type: str = ""
    needs_power: bool = False
    key_id: str = ""
    key_name: str = ""
    key_short_name: str = ""
    key_icon: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None
    top: float | None = None
    bottom: float | None = None


class TarkovMapHazardOut(BaseModel):
    id: str = ""
    hazard_type: str = ""
    name: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None
    top: float | None = None
    bottom: float | None = None
    outline: list[TarkovTaskPointOut] = Field(default_factory=list)


class TarkovMapSwitchActivateOut(BaseModel):
    operation: str = ""
    name: str = ""
    kind: str = ""


class TarkovMapSwitchOut(BaseModel):
    id: str = ""
    name: str = ""
    switch_type: str = ""
    activated_by: str = ""
    activates: list[TarkovMapSwitchActivateOut] = Field(default_factory=list)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    top: float | None = None
    bottom: float | None = None


class TarkovMapStationaryWeaponOut(BaseModel):
    id: str = ""
    name: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None
    top: float | None = None
    bottom: float | None = None


class TarkovMapBtrStopOut(BaseModel):
    id: str = ""
    name: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None


class TarkovMapLootContainerOut(BaseModel):
    id: str = ""
    container_id: str = ""
    name: str = ""
    normalized_name: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None
    top: float | None = None
    bottom: float | None = None


class TarkovMapLootLooseOut(BaseModel):
    id: str = ""
    items: list[TarkovMapItemRefOut] = Field(default_factory=list)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    top: float | None = None
    bottom: float | None = None


class TarkovMapListItemOut(BaseModel):
    id: str
    slug: str
    name: str
    english: str = ""
    raid_duration: int = 0
    players: str = ""
    thumb_link: str = ""
    interactive_url: str = ""
    parent_slug: str = ""
    min_player_level: int = 0
    max_player_level: int = 0


class TarkovMapCatalogOut(BaseModel):
    items: list[TarkovMapListItemOut] = Field(default_factory=list)
    map_count: int = 0
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovMapVariantOut(BaseModel):
    slug: str = ""
    name: str = ""
    raid_duration: int = 0
    players: str = ""


class TarkovMapPlaceOut(BaseModel):
    id: int
    map_key: str
    kind: str
    name: str
    x: float
    z: float
    x2: float | None = None
    z2: float | None = None
    label_x: float | None = None
    label_z: float | None = None
    size: int = 80
    floor: str = ""
    top: float | None = None
    bottom: float | None = None
    sort_order: int = 0


class TarkovMapPlaceIn(BaseModel):
    kind: str = "point"
    name: str = Field(min_length=1, max_length=64)
    x: float
    z: float
    x2: float | None = None
    z2: float | None = None
    label_x: float | None = None
    label_z: float | None = None
    size: int | None = None
    floor: str = ""
    top: float | None = None
    bottom: float | None = None


class TarkovMapPlacePatchIn(BaseModel):
    kind: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=64)
    x: float | None = None
    z: float | None = None
    x2: float | None = None
    z2: float | None = None
    label_x: float | None = None
    label_z: float | None = None
    size: int | None = None
    floor: str | None = None
    top: float | None = None
    bottom: float | None = None


class TarkovMapPlaceImportIn(BaseModel):
    items: list[TarkovMapPlaceIn] = Field(default_factory=list, max_length=200)


class TarkovMapPlacesOut(BaseModel):
    map_key: str
    items: list[TarkovMapPlaceOut] = Field(default_factory=list)


class TarkovMapDetailOut(TarkovMapListItemOut):
    description: str = ""
    wiki_link: str = ""
    extracts: list[TarkovMapExtractOut] = Field(default_factory=list)
    bosses: list[TarkovMapBossOut] = Field(default_factory=list)
    spawns: list[TarkovMapSpawnOut] = Field(default_factory=list)
    locks: list[TarkovMapLockOut] = Field(default_factory=list)
    hazards: list[TarkovMapHazardOut] = Field(default_factory=list)
    switches: list[TarkovMapSwitchOut] = Field(default_factory=list)
    stationary_weapons: list[TarkovMapStationaryWeaponOut] = Field(
        default_factory=list
    )
    btr_stops: list[TarkovMapBtrStopOut] = Field(default_factory=list)
    loot_containers: list[TarkovMapLootContainerOut] = Field(default_factory=list)
    loot_loose: list[TarkovMapLootLooseOut] = Field(default_factory=list)
    variants: list[TarkovMapVariantOut] = Field(default_factory=list)
    places: list[TarkovMapPlaceOut] = Field(default_factory=list)
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovMapLootOut(BaseModel):
    loot_containers: list[TarkovMapLootContainerOut] = Field(default_factory=list)
    loot_loose: list[TarkovMapLootLooseOut] = Field(default_factory=list)
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovGuideItemRefOut(BaseModel):
    id: str
    name: str = ""
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    count: float = 1
    found_in_raid: bool = False
    flea_price: int | None = None


class TarkovHideoutStationReqOut(BaseModel):
    station_id: str = ""
    station_slug: str = ""
    station_name: str = ""
    level: int = 0


class TarkovHideoutTraderReqOut(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    level: int = 0


class TarkovHideoutSkillReqOut(BaseModel):
    skill: str = ""
    level: int = 0


class TarkovHideoutLevelOut(BaseModel):
    id: str = ""
    level: int = 0
    construction_time: int = 0
    description: str = ""
    item_requirements: list[TarkovGuideItemRefOut] = Field(default_factory=list)
    station_requirements: list[TarkovHideoutStationReqOut] = Field(default_factory=list)
    trader_requirements: list[TarkovHideoutTraderReqOut] = Field(default_factory=list)
    skill_requirements: list[TarkovHideoutSkillReqOut] = Field(default_factory=list)


class TarkovHideoutStationOut(BaseModel):
    id: str
    slug: str
    name: str
    image_link: str = ""
    level_count: int = 0
    levels: list[TarkovHideoutLevelOut] = Field(default_factory=list)


class TarkovHideoutCatalogOut(BaseModel):
    items: list[TarkovHideoutStationOut] = Field(default_factory=list)
    station_count: int = 0
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovHideoutDetailOut(TarkovHideoutStationOut):
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovBarterOut(BaseModel):
    id: str
    trader_id: str = ""
    trader_slug: str = ""
    trader_name: str = ""
    min_trader_level: int = 0
    task_unlock: str | None = None
    required_items: list[TarkovGuideItemRefOut] = Field(default_factory=list)
    offered_item: TarkovGuideItemRefOut


class TarkovTraderChipOut(BaseModel):
    slug: str
    name: str


class TarkovBarterCatalogOut(BaseModel):
    items: list[TarkovBarterOut] = Field(default_factory=list)
    barter_count: int = 0
    page: int = 1
    page_size: int = 50
    total: int = 0
    traders: list[TarkovTraderChipOut] = Field(default_factory=list)
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovCraftOut(BaseModel):
    id: str
    station_id: str = ""
    station_slug: str = ""
    station_name: str = ""
    level: int = 0
    duration: int = 0
    required_items: list[TarkovGuideItemRefOut] = Field(default_factory=list)
    product_item: TarkovGuideItemRefOut


class TarkovItemQuestRewardOut(BaseModel):
    id: str
    name: str = ""
    trader_id: str = ""
    trader_slug: str = ""
    trader_name: str = ""
    kind: str = "finish"
    count: float = 1


class TarkovItemDropSourceOut(BaseModel):
    """maps/mobs 配装反查：会掉这件物品的 Boss 或非 Boss。"""

    id: str
    slug: str = ""
    name: str = ""
    kind: str = Field(
        default="boss",
        description="boss=具名 BOSS；elite=掠夺者/游荡者/邪教徒等；soldier=BEAR/USEC/守军等小兵",
    )
    maps_label: str = ""
    portrait_link: str = ""
    parent_ids: list[str] = Field(default_factory=list)


class TarkovItemSourcesOut(BaseModel):
    """物品获取途径：从 barters / crafts / tasks / maps.mobs dump 反查，items dump 本身没有这些字段。"""

    barters: list[TarkovBarterOut] = Field(default_factory=list)
    crafts: list[TarkovCraftOut] = Field(default_factory=list)
    quest_rewards: list[TarkovItemQuestRewardOut] = Field(default_factory=list)
    drops: list[TarkovItemDropSourceOut] = Field(default_factory=list)


class TarkovItemHideoutUseOut(BaseModel):
    station_id: str = ""
    station_slug: str = ""
    station_name: str = ""
    level: int = 0
    count: float = 1


class TarkovItemTaskUseOut(BaseModel):
    id: str
    name: str = ""
    trader_id: str = ""
    trader_slug: str = ""
    trader_name: str = ""
    notes: list[str] = Field(default_factory=list)
    count: float | None = None


class TarkovItemUsesOut(BaseModel):
    """物品用途：从交换材料 / 制作材料 / 藏身处建造 / 任务目标反查。"""

    barters: list[TarkovBarterOut] = Field(default_factory=list)
    crafts: list[TarkovCraftOut] = Field(default_factory=list)
    hideout: list[TarkovItemHideoutUseOut] = Field(default_factory=list)
    tasks: list[TarkovItemTaskUseOut] = Field(default_factory=list)


TarkovItemDetailOut.model_rebuild()


class TarkovStationChipOut(BaseModel):
    slug: str
    name: str


class TarkovCraftCatalogOut(BaseModel):
    items: list[TarkovCraftOut] = Field(default_factory=list)
    craft_count: int = 0
    page: int = 1
    page_size: int = 50
    total: int = 0
    stations: list[TarkovStationChipOut] = Field(default_factory=list)
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovGuidesSyncOut(BaseModel):
    station_count: int = 0
    barter_count: int = 0
    craft_count: int = 0
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")


class TarkovLootTierItemOut(BaseModel):
    id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    width: int = 1
    height: int = 1
    slots: int = 1
    price: int = 0
    price_per_slot: int = 0
    tier: str = "E"


class TarkovLootTierCatalogOut(BaseModel):
    items: list[TarkovLootTierItemOut] = Field(default_factory=list)
    item_count: int = 0
    page: int = 1
    page_size: int = 100
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovKeyPackBarterOut(BaseModel):
    trader_slug: str = ""
    trader_name: str = ""
    min_trader_level: int = 0


class TarkovKeyPackCraftOut(BaseModel):
    station_slug: str = ""
    station_name: str = ""
    level: int = 0


class TarkovKeyPackTaskOut(BaseModel):
    id: str
    name: str = ""


class TarkovKeyPackUsedInOut(BaseModel):
    id: str
    name: str = ""
    notes: list[str] = Field(default_factory=list)


class TarkovKeyPackFleaOut(BaseModel):
    price: int | None = None


class TarkovKeyPackSourcesOut(BaseModel):
    barters: list[TarkovKeyPackBarterOut] = Field(default_factory=list)
    crafts: list[TarkovKeyPackCraftOut] = Field(default_factory=list)
    tasks: list[TarkovKeyPackTaskOut] = Field(default_factory=list)
    flea: TarkovKeyPackFleaOut | None = None


class TarkovKeyPackKeyOut(BaseModel):
    id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    lock_count: int = 0
    access: bool = False
    community: bool = False
    uses: int | None = None
    description: str = ""
    lock_types: list[str] = Field(default_factory=list)
    needs_power: bool = False
    used_in_tasks: list[TarkovKeyPackUsedInOut] = Field(default_factory=list)
    sources: TarkovKeyPackSourcesOut = Field(default_factory=TarkovKeyPackSourcesOut)


class TarkovKeyPackMapOut(BaseModel):
    slug: str
    name: str
    english: str = ""
    keys: list[TarkovKeyPackKeyOut] = Field(default_factory=list)


class TarkovKeyPacksOut(BaseModel):
    maps: list[TarkovKeyPackMapOut] = Field(default_factory=list)
    unbound: list[TarkovKeyPackKeyOut] = Field(default_factory=list)
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovRaidRoomMapIn(BaseModel):
    map: str = Field(min_length=1, max_length=64)


class TarkovRaidRoomJoinIn(BaseModel):
    game_mode: str | None = None
    password: str | None = Field(default=None, max_length=32)


class TarkovRaidRoomCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=40)
    password: str | None = Field(default=None, max_length=32)
    listed: bool = True
    game_mode: str | None = None


class TarkovRaidRoomPasswordIn(BaseModel):
    password: str | None = Field(default=None, max_length=32)


class TarkovRaidRoomGameModeIn(BaseModel):
    game_mode: str = Field(min_length=1, max_length=16)


class TarkovRaidRoomHostIn(BaseModel):
    user_id: int = Field(ge=1)


class TarkovRaidRoomClaimIn(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)


class TarkovRaidRoomClaimsIn(BaseModel):
    task_ids: list[str] = Field(default_factory=list, max_length=40)


class TarkovRaidRoomTaskProgressIn(BaseModel):
    started_ids: list[str] = Field(default_factory=list, max_length=400)
    done_ids: list[str] = Field(default_factory=list, max_length=800)


class TarkovRaidRoomOverlapTaskOut(BaseModel):
    id: str
    name: str = ""
    trader_slug: str = ""
    user_ids: list[int] = Field(default_factory=list)


class TarkovRaidRoomOverlapCellOut(BaseModel):
    user_id: int
    count: int = 0
    uploaded: bool = False


class TarkovRaidRoomMapOverlapOut(BaseModel):
    map_slug: str
    with_tasks_count: int = 0
    synced_count: int = 0
    occupant_count: int = 0
    cells: list[TarkovRaidRoomOverlapCellOut] = Field(default_factory=list)
    tasks: list[TarkovRaidRoomOverlapTaskOut] = Field(default_factory=list)


class TarkovRaidRoomMemberProgressOut(BaseModel):
    user_id: int
    uploaded: bool = False
    started_count: int = 0
    uploaded_at: str | None = None


class TarkovRaidRoomMarkIn(BaseModel):
    kind: str = Field(min_length=1, max_length=8)
    floor: str = ""
    x: float
    z: float
    x2: float | None = None
    z2: float | None = None
    points: list[list[float]] | None = None


class TarkovRaidRoomMemberOut(BaseModel):
    user_id: int
    display_name: str
    is_host: bool = False
    in_room: bool = True
    online: bool = False
    joined_at: str | None = None


class TarkovRaidRoomClaimOut(BaseModel):
    task_id: str
    user_id: int
    display_name: str
    created_at: str | None = None


class TarkovRaidRoomKeyBringOut(BaseModel):
    item_id: str
    user_id: int
    display_name: str
    created_at: str | None = None


class TarkovKeyOwnOut(BaseModel):
    item_id: str
    user_id: int
    display_name: str
    created_at: str | None = None


class TarkovKeyOwnsOut(BaseModel):
    item_ids: list[str] = Field(default_factory=list)


class TarkovKeyOwnsIn(BaseModel):
    item_ids: list[str] = Field(default_factory=list, max_length=400)


class TarkovKeyOcrMatchOut(BaseModel):
    id: str
    name: str = ""
    short_name: str = ""
    icon_link: str = ""
    ocr_text: str = ""
    confidence: str = "fuzzy"


class TarkovKeyOcrBoxOut(BaseModel):
    x: float
    y: float
    width: float
    height: float
    label: str = ""
    item_id: str = ""
    kind: str = "miss"


class TarkovKeyOcrOverlayOut(BaseModel):
    width: int
    height: int
    boxes: list[TarkovKeyOcrBoxOut] = Field(default_factory=list)


class TarkovKeyOcrOut(BaseModel):
    matches: list[TarkovKeyOcrMatchOut] = Field(default_factory=list)
    tile_count: int = 0
    overlay: TarkovKeyOcrOverlayOut | None = None
    engines: list[str] = Field(default_factory=list)


class TarkovRaidPrepOcrMatchOut(BaseModel):
    id: str
    name: str = ""
    ocr_text: str = ""
    trader_slug: str = ""
    trader_name: str = ""


class TarkovRaidPrepOcrOut(BaseModel):
    matches: list[TarkovRaidPrepOcrMatchOut] = Field(default_factory=list)
    width: int = 0
    height: int = 0
    widescreen: bool = False
    preferred_size: bool = False
    engines: list[str] = Field(default_factory=list)


class TarkovCollectionTaskOut(BaseModel):
    id: str
    name: str = ""
    normalized_name: str = ""
    trader_slug: str = ""
    trader_name: str = ""


class TarkovCollectionItemOut(BaseModel):
    id: str
    name: str = ""
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    handbook_ids: list[str] = Field(default_factory=list)
    width: int = 1
    height: int = 1
    found_in_raid: bool | None = None
    count: int = 1
    objective_id: str = ""


class TarkovCollectionOut(BaseModel):
    task: TarkovCollectionTaskOut | None = None
    grid_width: int = 3
    grid_height: int = 4
    items: list[TarkovCollectionItemOut] = Field(default_factory=list)
    item_count: int = 0
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovCollectionOwnsOut(BaseModel):
    item_ids: list[str] = Field(default_factory=list)


class TarkovCollectionOwnsIn(BaseModel):
    item_ids: list[str] = Field(default_factory=list, max_length=200)


class TarkovCollectionPlacementOut(BaseModel):
    item_id: str
    col: int
    row: int
    rotated: bool = False


class TarkovCollectionLayoutOut(BaseModel):
    placements: list[TarkovCollectionPlacementOut] = Field(default_factory=list)
    saved: bool = False


class TarkovCollectionPlacementIn(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    col: int
    row: int
    rotated: bool = False


class TarkovCollectionLayoutIn(BaseModel):
    placements: list[TarkovCollectionPlacementIn] = Field(
        default_factory=list, max_length=200
    )


class TarkovTaskObjectiveDonePair(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    objective_id: str = Field(min_length=1, max_length=64)


class TarkovTaskDonesOut(BaseModel):
    task_ids: list[str] = Field(default_factory=list)
    started_ids: list[str] = Field(default_factory=list)
    objective_dones: list[TarkovTaskObjectiveDonePair] = Field(default_factory=list)


class TarkovTaskDonesIn(BaseModel):
    task_ids: list[str] = Field(default_factory=list, max_length=800)
    started_ids: list[str] | None = Field(default=None, max_length=800)
    objective_dones: list[TarkovTaskObjectiveDonePair] | None = Field(
        default=None, max_length=8000
    )
    replace: bool = False


class TarkovRaidLogIn(BaseModel):
    folder: str = ""
    raid_id: str = ""
    location: str = ""
    map_id: str = ""
    map_label: str = ""
    raid_mode: str = ""
    session_mode: str = ""
    started_at: str = ""
    ended_at: str = ""
    reconnected: bool = False
    aborted: bool = False


class TarkovRaidLogsIn(BaseModel):
    raids: list[TarkovRaidLogIn] = Field(default_factory=list, max_length=500)


class TarkovRaidLogsImportOut(BaseModel):
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    total: int = 0


class TarkovRaidLogOut(TarkovRaidLogIn):
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TarkovRaidLogsOut(BaseModel):
    items: list[TarkovRaidLogOut] = Field(default_factory=list)


class TarkovRaidRoomObjectiveDoneOut(BaseModel):
    task_id: str
    objective_id: str
    user_id: int
    display_name: str
    created_at: str | None = None


class TarkovRaidRoomMarkOut(BaseModel):
    id: int
    kind: str
    floor: str = ""
    x: float
    z: float
    x2: float | None = None
    z2: float | None = None
    points: list[list[float]] | None = None
    author_user_id: int
    author_display_name: str = ""
    created_at: str | None = None


class TarkovRaidRoomOccupantOut(BaseModel):
    user_id: int
    display_name: str
    is_host: bool = False
    online: bool = False


class TarkovRaidRoomLobbyItemOut(BaseModel):
    public_id: str
    title: str = ""
    map_slug: str = ""
    game_mode: str = "pvp"
    listed: bool = True
    has_password: bool = False
    host_user_id: int | None = None
    host_display_name: str = ""
    member_count: int = 0
    max_members: int = 8
    is_member: bool = False
    created_at: str | None = None
    occupants: list[TarkovRaidRoomOccupantOut] = Field(default_factory=list)


class TarkovRaidRoomLobbyOut(BaseModel):
    items: list[TarkovRaidRoomLobbyItemOut] = Field(default_factory=list)
    page: int = 1
    page_size: int = 10
    total: int = 0
    mine: TarkovRaidRoomLobbyItemOut | None = None


class TarkovRaidRoomMineOut(BaseModel):
    item: TarkovRaidRoomLobbyItemOut | None = None


class TarkovRaidRoomDetailOut(TarkovRaidRoomLobbyItemOut):
    is_host: bool = False
    is_member: bool = False
    can_edit: bool = False
    members: list[TarkovRaidRoomMemberOut] = Field(default_factory=list)
    claims: list[TarkovRaidRoomClaimOut] = Field(default_factory=list)
    key_brings: list[TarkovRaidRoomKeyBringOut] = Field(default_factory=list)
    key_owns: list[TarkovKeyOwnOut] = Field(default_factory=list)
    objective_dones: list[TarkovRaidRoomObjectiveDoneOut] = Field(
        default_factory=list
    )
    marks: list[TarkovRaidRoomMarkOut] = Field(default_factory=list)
    task_progress: list[TarkovRaidRoomMemberProgressOut] = Field(
        default_factory=list
    )
    map_overlap: list[TarkovRaidRoomMapOverlapOut] = Field(default_factory=list)


class TarkovRaidPrepObjectiveDoneIn(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    objective_id: str = Field(min_length=1, max_length=64)


class TarkovRaidRoomObjectiveDonesIn(BaseModel):
    items: list[TarkovRaidPrepObjectiveDoneIn] = Field(
        default_factory=list, max_length=80
    )


def _clip_str_ids(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen or len(text) > 64:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


class TarkovUserRaidPrepStateIn(BaseModel):
    selected: list[str] = Field(default_factory=list, max_length=40)
    objective_dones: list[TarkovRaidPrepObjectiveDoneIn] = Field(
        default_factory=list, max_length=200
    )
    key_brings: list[str] = Field(default_factory=list, max_length=80)

    @field_validator("selected", mode="before")
    @classmethod
    def _clip_selected(cls, value: object) -> list[str]:
        return _clip_str_ids(value, 40)

    @field_validator("key_brings", mode="before")
    @classmethod
    def _clip_key_brings(cls, value: object) -> list[str]:
        return _clip_str_ids(value, 80)

    @field_validator("objective_dones", mode="before")
    @classmethod
    def _clip_objective_dones(cls, value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        out: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            task_id = str(item.get("task_id") or "").strip()
            objective_id = str(item.get("objective_id") or "").strip()
            if (
                not task_id
                or not objective_id
                or len(task_id) > 64
                or len(objective_id) > 64
            ):
                continue
            key = (task_id, objective_id)
            if key in seen:
                continue
            seen.add(key)
            out.append({"task_id": task_id, "objective_id": objective_id})
            if len(out) >= 200:
                break
        return out


class TarkovUserRaidPrepStateOut(BaseModel):
    map: str = ""
    game_mode: str = "pvp"
    selected: list[str] = Field(default_factory=list)
    objective_dones: list[TarkovRaidPrepObjectiveDoneIn] = Field(
        default_factory=list
    )
    key_brings: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class TarkovGoonTrackerOut(BaseModel):
    """社区上报的三狗最近出现地图（PVP / PVE 分开）。"""

    game_mode: str = "pvp"
    map_slug: str = ""
    map_name: str = ""
    map_english: str = ""
    seen_at: str | None = None
    report_id: str = ""
    source: str = "tarkov-stammtisch"
    source_url: str = ""
