"""雨中冒险 2 图鉴响应。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Ror2StatOut(BaseModel):
    label: str
    value: str = ""
    stack: str = ""
    add: str = ""
    source_key: str | None = Field(default=None, exclude=True)
    stack_zh: str = Field(default="", exclude=True)


class Ror2ItemOut(BaseModel):
    name: str
    rarity: str = ""
    rarity_zh: str = Field(default="", exclude=True)
    quote: str = ""
    description: str = ""
    lore: str = ""
    categories: list[str] = Field(default_factory=list)
    unlock: str = ""
    expansion: str = ""
    internal_name: str = ""
    code: str = ""
    corrupt: str = ""
    uncorrupt: str = ""
    boss: str = ""
    cooldown: str = ""
    name_zh: str = ""
    description_zh: str = ""
    lore_zh: str = ""
    quote_zh: str = ""
    unlock_zh: str = ""
    wiki_url: str
    image_url: str | None = None
    stats: list[Ror2StatOut] = Field(default_factory=list)


class Ror2SurvivorOut(BaseModel):
    name: str
    umbra: str = ""
    description: str = ""
    unlock: str = ""
    expansion: str = ""
    phrase_escape: str = ""
    phrase_vanish: str = ""
    name_zh: str = ""
    description_zh: str = ""
    umbra_zh: str = ""
    unlock_zh: str = ""
    phrase_escape_zh: str = ""
    phrase_vanish_zh: str = ""
    health: float | None = None
    health_per_level: float | None = None
    damage: float | None = None
    damage_per_level: float | None = None
    regen: float | None = None
    regen_per_level: float | None = None
    speed: float | None = None
    acceleration: float | None = None
    mass: float | None = None
    armor: float | None = None
    wiki_url: str
    image_url: str | None = None


class Ror2MonsterOut(BaseModel):
    name: str
    kind: str = ""
    role: str = ""
    expansion: str = ""
    boss_name: str = ""
    boss_name_zh: str = ""
    internal_name: str = ""
    name_zh: str = ""
    categories: list[str] = Field(default_factory=list)
    is_ally: bool = False
    do_not_count: bool = False
    is_subtype: bool = False
    health: float | None = None
    health_per_level: float | None = None
    damage: float | None = None
    damage_per_level: float | None = None
    regen: float | None = None
    regen_per_level: float | None = None
    speed: float | None = None
    armor: float | None = None
    wiki_url: str
    image_url: str | None = None


class Ror2DroneOut(BaseModel):
    name: str
    kind: str = ""
    quote: str = ""
    quote_zh: str = ""
    description: str = ""
    description_zh: str = ""
    internal_name: str = ""
    name_zh: str = ""
    rarity: str = ""
    type2: str = ""
    cost: str = ""
    health: float | None = None
    health_per_level: float | None = None
    damage: float | None = None
    damage_per_level: float | None = None
    regen: float | None = None
    regen_per_level: float | None = None
    speed: float | None = None
    armor: float | None = None
    wiki_url: str
    image_url: str | None = None


class Ror2EnvironmentOut(BaseModel):
    name: str
    stage: str = ""
    subtitle: str = ""
    subtitle_zh: str = ""
    description: str = ""
    description_zh: str = ""
    name_zh: str = ""
    soundtrack: str = ""
    lunar_seer: str = ""
    expansion: str = ""
    wiki_url: str
    image_url: str | None = None


class Ror2ChallengeOut(BaseModel):
    name: str
    name_zh: str = ""
    kind: str = ""
    description: str = ""
    description_zh: str = ""
    unlock: list[str] = Field(default_factory=list)
    coins: str = ""
    expansion: str = ""
    wiki_url: str


class Ror2InteractableOut(BaseModel):
    name: str
    name_zh: str = ""
    category: str = ""
    effect: str = ""
    effect_zh: str = ""
    expansion: str = ""
    cost: str = ""
    link: str = ""
    location: list[str] = Field(default_factory=list)
    wiki_url: str
    image_url: str | None = None


class Ror2ArtifactOut(BaseModel):
    name: str
    name_zh: str = ""
    description: str = ""
    description_zh: str = ""
    code: list[str] = Field(default_factory=list)
    expansion: str = ""
    unlock: str = ""
    unlock_zh: str = ""
    wiki_url: str
    image_url: str | None = None


class Ror2CatalogOut(BaseModel):
    source: str
    fetched_at: str
    items: list[Ror2ItemOut]
    equipment: list[Ror2ItemOut]
    survivors: list[Ror2SurvivorOut]
    monsters: list[Ror2MonsterOut] = Field(default_factory=list)
    drones: list[Ror2DroneOut] = Field(default_factory=list)
    environments: list[Ror2EnvironmentOut] = Field(default_factory=list)
    challenges: list[Ror2ChallengeOut] = Field(default_factory=list)
    interactables: list[Ror2InteractableOut] = Field(default_factory=list)
    artifacts: list[Ror2ArtifactOut] = Field(default_factory=list)


class Ror2WikiItemOut(BaseModel):
    text: str = ""
    text_zh: str = ""
    children: list[Ror2WikiItemOut] = Field(default_factory=list)


class Ror2WikiBlockOut(BaseModel):
    kind: str
    text: str = ""
    text_zh: str = ""
    items: list[Ror2WikiItemOut] = Field(default_factory=list)
    images: list[Ror2GalleryImageOut] = Field(default_factory=list)


class Ror2GalleryImageOut(BaseModel):
    image_url: str
    spin_url: str | None = None
    caption: str = ""
    caption_zh: str = ""
    expansion: str = ""


class Ror2SkillOut(BaseModel):
    name: str
    skill_type: str = ""
    cooldown: str = ""
    proc: str = ""
    description: str = ""
    name_zh: str = ""
    description_zh: str = ""
    notes: list[Ror2WikiItemOut] = Field(default_factory=list)
    unlock: str = ""
    unlock_zh: str = ""
    image_url: str | None = None


class Ror2SkillGroupOut(BaseModel):
    skill_type: str
    skills: list[Ror2SkillOut] = Field(default_factory=list)


class Ror2HistoryOut(BaseModel):
    version: str
    items: list[Ror2WikiItemOut] = Field(default_factory=list)


class Ror2SurvivorDetailOut(BaseModel):
    name: str
    name_zh: str = ""
    summary: str = ""
    summary_zh: str = ""
    umbra: str = ""
    umbra_zh: str = ""
    phrase_escape: str = ""
    phrase_escape_zh: str = ""
    phrase_vanish: str = ""
    phrase_vanish_zh: str = ""
    expansion: str = ""
    health: float | None = None
    health_per_level: float | None = None
    regen: float | None = None
    regen_per_level: float | None = None
    damage: float | None = None
    damage_per_level: float | None = None
    speed: float | None = None
    acceleration: float | None = None
    mass: float | None = None
    armor: float | None = None
    image_url: str | None = None
    wiki_url: str
    lore: str = ""
    lore_zh: str = ""
    skills: list[Ror2SkillGroupOut] = Field(default_factory=list)
    behaviors: list[Ror2WikiBlockOut] = Field(default_factory=list)
    tips: list[Ror2WikiBlockOut] = Field(default_factory=list)
    trivia: list[Ror2WikiBlockOut] = Field(default_factory=list)
    gallery: list[Ror2GalleryImageOut] = Field(default_factory=list)
    history: list[Ror2HistoryOut] = Field(default_factory=list)


Ror2WikiItemOut.model_rebuild()
Ror2WikiBlockOut.model_rebuild()


class Ror2TextOut(BaseModel):
    """Wiki 来源文本的显示值、当前原文和真实 Weblate context。"""

    text: str
    original: str
    token: str | None = None


class Ror2StatResponse(BaseModel):
    label: str
    value: str = ""
    stack: Ror2TextOut
    add: str = ""


class Ror2WikiColumnOut(BaseModel):
    id: str
    label: Ror2TextOut


class Ror2WikiTableOut(BaseModel):
    id: str
    caption: Ror2TextOut | None = None
    columns: list[Ror2WikiColumnOut] = Field(default_factory=list)


class Ror2WikiSectionOut(BaseModel):
    id: str
    level: int
    title: Ror2TextOut
    tables: list[Ror2WikiTableOut] = Field(default_factory=list)


class Ror2WikiArticleOut(BaseModel):
    id: str
    title: Ror2TextOut
    sections: list[Ror2WikiSectionOut] = Field(default_factory=list)


class Ror2ItemResponse(BaseModel):
    name: Ror2TextOut
    rarity: Ror2TextOut
    quote: Ror2TextOut
    description: Ror2TextOut
    lore: Ror2TextOut
    categories: list[str] = Field(default_factory=list)
    unlock: Ror2TextOut
    expansion: str = ""
    internal_name: str = ""
    code: str = ""
    corrupt: str = ""
    uncorrupt: str = ""
    boss: str = ""
    cooldown: str = ""
    wiki_url: str
    image_url: str | None = None
    stats: list[Ror2StatResponse] = Field(default_factory=list)


class Ror2SurvivorResponse(BaseModel):
    name: Ror2TextOut
    umbra: Ror2TextOut
    description: Ror2TextOut
    unlock: Ror2TextOut
    expansion: str = ""
    phrase_escape: Ror2TextOut
    phrase_vanish: Ror2TextOut
    health: float | None = None
    health_per_level: float | None = None
    damage: float | None = None
    damage_per_level: float | None = None
    regen: float | None = None
    regen_per_level: float | None = None
    speed: float | None = None
    acceleration: float | None = None
    mass: float | None = None
    armor: float | None = None
    wiki_url: str
    image_url: str | None = None


class Ror2MonsterResponse(BaseModel):
    name: Ror2TextOut
    kind: str = ""
    role: str = ""
    expansion: str = ""
    boss_name: Ror2TextOut
    internal_name: str = ""
    categories: list[str] = Field(default_factory=list)
    is_ally: bool = False
    do_not_count: bool = False
    is_subtype: bool = False
    health: float | None = None
    health_per_level: float | None = None
    damage: float | None = None
    damage_per_level: float | None = None
    regen: float | None = None
    regen_per_level: float | None = None
    speed: float | None = None
    armor: float | None = None
    wiki_url: str
    image_url: str | None = None


class Ror2DroneResponse(BaseModel):
    name: Ror2TextOut
    kind: str = ""
    quote: Ror2TextOut
    description: Ror2TextOut
    internal_name: str = ""
    rarity: str = ""
    type2: str = ""
    cost: str = ""
    health: float | None = None
    health_per_level: float | None = None
    damage: float | None = None
    damage_per_level: float | None = None
    regen: float | None = None
    regen_per_level: float | None = None
    speed: float | None = None
    armor: float | None = None
    wiki_url: str
    image_url: str | None = None


class Ror2EnvironmentResponse(BaseModel):
    name: Ror2TextOut
    stage: str = ""
    subtitle: Ror2TextOut
    description: Ror2TextOut
    soundtrack: str = ""
    lunar_seer: str = ""
    expansion: str = ""
    wiki_url: str
    image_url: str | None = None


class Ror2ChallengeResponse(BaseModel):
    name: Ror2TextOut
    kind: str = ""
    description: Ror2TextOut
    unlock: list[Ror2TextOut] = Field(default_factory=list)
    coins: str = ""
    expansion: str = ""
    wiki_url: str


class Ror2InteractableResponse(BaseModel):
    name: Ror2TextOut
    category: str = ""
    effect: Ror2TextOut
    expansion: str = ""
    cost: str = ""
    link: str = ""
    location: list[str] = Field(default_factory=list)
    wiki_url: str
    image_url: str | None = None


class Ror2ArtifactResponse(BaseModel):
    name: Ror2TextOut
    description: Ror2TextOut
    code: list[str] = Field(default_factory=list)
    expansion: str = ""
    unlock: Ror2TextOut
    wiki_url: str
    image_url: str | None = None


class Ror2CatalogResponse(BaseModel):
    source: str
    fetched_at: str
    items: list[Ror2ItemResponse]
    equipment: list[Ror2ItemResponse]
    survivors: list[Ror2SurvivorResponse]
    monsters: list[Ror2MonsterResponse] = Field(default_factory=list)
    drones: list[Ror2DroneResponse] = Field(default_factory=list)
    environments: list[Ror2EnvironmentResponse] = Field(default_factory=list)
    challenges: list[Ror2ChallengeResponse] = Field(default_factory=list)
    interactables: list[Ror2InteractableResponse] = Field(default_factory=list)
    artifacts: list[Ror2ArtifactResponse] = Field(default_factory=list)
    wiki_articles: list[Ror2WikiArticleOut] = Field(default_factory=list)


class Ror2WikiItemResponse(BaseModel):
    text: Ror2TextOut
    children: list[Ror2WikiItemResponse] = Field(default_factory=list)


class Ror2WikiBlockResponse(BaseModel):
    kind: str
    text: Ror2TextOut
    items: list[Ror2WikiItemResponse] = Field(default_factory=list)
    images: list[Ror2GalleryImageResponse] = Field(default_factory=list)


class Ror2GalleryImageResponse(BaseModel):
    image_url: str
    spin_url: str | None = None
    caption: Ror2TextOut
    expansion: str = ""


class Ror2SkillResponse(BaseModel):
    name: Ror2TextOut
    skill_type: Ror2TextOut
    cooldown: str = ""
    proc: str = ""
    description: Ror2TextOut
    notes: list[Ror2WikiItemResponse] = Field(default_factory=list)
    unlock: Ror2TextOut
    image_url: str | None = None


class Ror2SkillGroupResponse(BaseModel):
    skill_type: Ror2TextOut
    skills: list[Ror2SkillResponse] = Field(default_factory=list)


class Ror2HistoryResponse(BaseModel):
    version: Ror2TextOut
    items: list[Ror2WikiItemResponse] = Field(default_factory=list)


class Ror2SurvivorDetailResponse(BaseModel):
    name: Ror2TextOut
    summary: Ror2TextOut
    umbra: Ror2TextOut
    phrase_escape: Ror2TextOut
    phrase_vanish: Ror2TextOut
    expansion: str = ""
    health: float | None = None
    health_per_level: float | None = None
    regen: float | None = None
    regen_per_level: float | None = None
    damage: float | None = None
    damage_per_level: float | None = None
    speed: float | None = None
    acceleration: float | None = None
    mass: float | None = None
    armor: float | None = None
    image_url: str | None = None
    wiki_url: str
    lore: Ror2TextOut
    skills: list[Ror2SkillGroupResponse] = Field(default_factory=list)
    behaviors: list[Ror2WikiBlockResponse] = Field(default_factory=list)
    tips: list[Ror2WikiBlockResponse] = Field(default_factory=list)
    trivia: list[Ror2WikiBlockResponse] = Field(default_factory=list)
    gallery: list[Ror2GalleryImageResponse] = Field(default_factory=list)
    history: list[Ror2HistoryResponse] = Field(default_factory=list)


Ror2WikiItemResponse.model_rebuild()
Ror2WikiBlockResponse.model_rebuild()
