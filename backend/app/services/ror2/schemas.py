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


class Ror2CatalogOut(BaseModel):
    source: str
    fetched_at: str
    items: list[Ror2ItemOut]
    equipment: list[Ror2ItemOut]
    survivors: list[Ror2SurvivorOut]
