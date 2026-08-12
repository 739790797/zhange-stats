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
    gun_count: int
    source: str | None = None
    synced_at: str | None = None
    message: str = Field(default="ok")
