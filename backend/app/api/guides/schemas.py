from pydantic import BaseModel, Field


class TarkovAmmoItemOut(BaseModel):
    id: str
    name: str
    short_name: str = ""
    caliber: str
    damage: int
    penetration: int
    armor_damage: int = 0


class TarkovAmmoCatalogOut(BaseModel):
    items: list[TarkovAmmoItemOut]
    ammo_count: int
    source: str | None = None
    synced_at: str | None = None
    note: str | None = None


class TarkovAmmoSyncOut(BaseModel):
    ammo_count: int
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")
