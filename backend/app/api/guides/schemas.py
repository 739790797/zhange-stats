from pydantic import BaseModel, Field


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


class TarkovItemDetailOut(BaseModel):
    """通用物品详情：来自 items raw 的完整 item + properties。"""

    id: str
    name: str
    short_name: str = ""
    description: str = ""
    source: str | None = None
    item: dict = Field(default_factory=dict)
    properties: dict = Field(default_factory=dict)


class TarkovTaskNamedRefOut(BaseModel):
    id: str
    slug: str = ""
    name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)


class TarkovTaskTraderChipOut(BaseModel):
    id: str
    slug: str
    name: str


class TarkovTaskTraderReqOut(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    requirement_type: str = ""
    value: int = 0
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
    experience: int = 0
    kappa_required: bool = False
    lightkeeper_required: bool = False
    faction_name: str = "Any"
    task_image_link: str = ""
    wiki_link: str = ""
    objective_count: int = 0
    progress_status: str | None = None


class TarkovTaskCatalogOut(BaseModel):
    items: list[TarkovTaskListItemOut]
    task_count: int
    page: int = 1
    page_size: int = 50
    traders: list[TarkovTaskTraderChipOut] = Field(default_factory=list)
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None
    progress_bound: bool = False
    progress_ready: bool = False


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


class TarkovTaskRequirementOut(BaseModel):
    id: str
    name: str = ""
    status: list[str] = Field(default_factory=list)
    met: bool | None = None


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


class TarkovTaskFinishRewardsOut(BaseModel):
    items: list[TarkovTaskRewardItemOut] = Field(default_factory=list)
    trader_standing: list[TarkovTaskStandingOut] = Field(default_factory=list)


class TarkovTaskNeededKeysOut(BaseModel):
    map: TarkovTaskNamedRefOut
    keys: list[TarkovTaskNamedRefOut] = Field(default_factory=list)


class TarkovTaskDetailOut(TarkovTaskListItemOut):
    source: str | None = None
    objectives: list[TarkovTaskObjectiveOut] = Field(default_factory=list)
    task_requirements: list[TarkovTaskRequirementOut] = Field(default_factory=list)
    successor_tasks: list[TarkovTaskRequirementOut] = Field(default_factory=list)
    trader_requirements: list[TarkovTaskTraderReqOut] = Field(default_factory=list)
    finish_rewards: TarkovTaskFinishRewardsOut = Field(
        default_factory=TarkovTaskFinishRewardsOut
    )
    needed_keys: list[TarkovTaskNeededKeysOut] = Field(default_factory=list)
    restartable: bool = False
    progress_bound: bool = False
    progress_ready: bool = False


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


class TarkovBossSpawnLocationOut(BaseModel):
    map: str = ""
    map_slug: str = ""
    name: str = ""
    chance: float = 0


class TarkovBossEscortOut(BaseModel):
    slug: str = ""
    name: str = ""
    nickname: str = ""
    count: int = 0
    chance: float = 0
    map: str = ""
    map_slug: str = ""


class TarkovBossLootOut(BaseModel):
    item_id: str
    name: str
    short_name: str = ""
    icon_link: str = ""
    types: list[str] = Field(default_factory=list)
    flea_price: int | None = None
    trader_slug: str = ""
    trader_name: str = ""
    trader_price: int | None = None
    trader_currency: str = "RUB"


class TarkovBossListItemOut(BaseModel):
    id: str
    slug: str
    name: str
    nickname: str = ""
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
    unique_loot: list[TarkovBossLootOut] = Field(default_factory=list)
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


class TarkovTrackerBindIn(BaseModel):
    token: str = Field(min_length=8, max_length=64)


class TarkovTrackerStatusOut(BaseModel):
    bound: bool
    game_mode: str = ""
    game_mode_label: str = ""
    display_name: str = ""
    player_level: int = 0
    pmc_faction: str = ""
    tasks_complete: int = 0
    tasks_failed: int = 0
    token_suffix: str = ""
    last_synced_at: str | None = None
    last_error: str | None = None


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
    spawn_chance: int = 0
    locations: list[TarkovMapBossLocationOut] = Field(default_factory=list)


class TarkovMapExtractOut(BaseModel):
    id: str = ""
    name: str = ""
    faction: str = ""
    x: float | None = None
    y: float | None = None
    z: float | None = None


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


class TarkovMapDetailOut(TarkovMapListItemOut):
    description: str = ""
    wiki_link: str = ""
    extracts: list[TarkovMapExtractOut] = Field(default_factory=list)
    bosses: list[TarkovMapBossOut] = Field(default_factory=list)
    variants: list[TarkovMapVariantOut] = Field(default_factory=list)
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
