"""雨中冒险 2 图鉴响应。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Ror2StatOut(BaseModel):
    label: str
    value: str = ""
    stack: str = ""
    add: str = ""


class Ror2ItemOut(BaseModel):
    name: str
    rarity: str = ""
    quote: str = ""
    description: str = ""
    categories: list[str] = Field(default_factory=list)
    unlock: str = ""
    expansion: str = ""
    internal_name: str = ""
    code: str = ""
    corrupt: str = ""
    uncorrupt: str = ""
    boss: str = ""
    cooldown: str = ""
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


class Ror2MonsterOut(BaseModel):
    name: str
    kind: str = ""
    role: str = ""
    expansion: str = ""
    boss_name: str = ""
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
    description: str = ""
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
    description: str = ""
    soundtrack: str = ""
    lunar_seer: str = ""
    expansion: str = ""
    wiki_url: str
    image_url: str | None = None


class Ror2ChallengeOut(BaseModel):
    name: str
    kind: str = ""
    description: str = ""
    unlock: list[str] = Field(default_factory=list)
    coins: str = ""
    expansion: str = ""
    wiki_url: str


class Ror2InteractableOut(BaseModel):
    name: str
    category: str = ""
    effect: str = ""
    expansion: str = ""
    cost: str = ""
    link: str = ""
    location: list[str] = Field(default_factory=list)
    wiki_url: str
    image_url: str | None = None


class Ror2ArtifactOut(BaseModel):
    name: str
    description: str = ""
    code: list[str] = Field(default_factory=list)
    expansion: str = ""
    unlock: str = ""
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
