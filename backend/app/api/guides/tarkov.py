import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.guides.schemas import (
    TarkovAmmoCatalogOut,
    TarkovAmmoDetailOut,
    TarkovAmmoItemOut,
    TarkovAmmoSyncOut,
    TarkovGunCatalogOut,
    TarkovGunItemOut,
    TarkovGunSyncOut,
    TarkovItemsSyncOut,
)
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services import tarkov_ammo as ammo_svc
from app.services import tarkov_guns as gun_svc
from app.services import tarkov_items as items_svc

router = APIRouter(prefix="/tarkov")


def _parse_str_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if x is not None and str(x).strip()]


def _sync_items(db: Session) -> dict:
    try:
        return items_svc.sync_from_upstream(db)
    except items_svc.TarkovItemsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/items/sync",
    response_model=TarkovItemsSyncOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_items_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：回源同步物品（一次写入 ammo+guns 派生）。"""
    result = _sync_items(db)
    return TarkovItemsSyncOut(
        ammo_count=int(result.get("ammo_count") or 0),
        gun_count=int(result.get("gun_count") or 0),
        source=result.get("source"),
        synced_at=result.get("synced_at"),
        message="ok",
    )


@router.get(
    "/ammo",
    response_model=TarkovAmmoCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_ammo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """弹药穿透/伤害表（派生读模型）。空库时走共享 items 同步。"""
    _ = user
    try:
        ammo_svc.ensure_ammo(db)
    except ammo_svc.TarkovAmmoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    items = [
        TarkovAmmoItemOut(
            id=row.item_id,
            name=row.name,
            short_name=row.short_name,
            caliber=row.caliber,
            ammo_type=row.ammo_type,
            damage=row.damage,
            penetration=row.penetration,
            armor_damage=row.armor_damage,
            initial_speed=row.initial_speed,
            accuracy_modifier=row.accuracy_modifier,
            recoil_modifier=row.recoil_modifier,
            light_bleed_modifier=row.light_bleed_modifier,
            heavy_bleed_modifier=row.heavy_bleed_modifier,
            icon_link=row.icon_link,
        )
        for row in ammo_svc.list_ammo(db)
    ]
    meta = ammo_svc.get_ammo_meta(db)
    return TarkovAmmoCatalogOut(
        items=items,
        ammo_count=len(items),
        source=meta.source if meta else None,
        synced_at=meta.synced_at.isoformat() if meta and meta.synced_at else None,
        note=meta.note if meta else None,
    )


@router.get(
    "/ammo/{item_id}",
    response_model=TarkovAmmoDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_ammo_detail(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """弹药详情：从 items raw 返回完整 item / properties。"""
    _ = user
    try:
        detail = items_svc.get_ammo_item_detail(db, item_id)
    except items_svc.TarkovItemsError as exc:
        msg = str(exc)
        if msg.startswith("未找到弹药"):
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return TarkovAmmoDetailOut(
        id=str(detail.get("id") or item_id),
        name=str(detail.get("name") or item_id),
        short_name=str(detail.get("short_name") or ""),
        description=str(detail.get("description") or ""),
        source=detail.get("source"),
        item=detail.get("item") if isinstance(detail.get("item"), dict) else {},
        properties=(
            detail.get("properties")
            if isinstance(detail.get("properties"), dict)
            else {}
        ),
    )


@router.post(
    "/ammo/sync",
    response_model=TarkovAmmoSyncOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_ammo_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：与 /items/sync 相同（兼容旧客户端）。"""
    result = _sync_items(db)
    return TarkovAmmoSyncOut(
        ammo_count=int(result.get("ammo_count") or 0),
        gun_count=int(result.get("gun_count") or 0),
        source=result.get("source"),
        synced_at=result.get("synced_at"),
        message="ok",
    )


@router.get(
    "/guns",
    response_model=TarkovGunCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_guns(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """枪械总表（派生读模型）。空库时走共享 items 同步。"""
    _ = user
    try:
        gun_svc.ensure_guns(db)
    except gun_svc.TarkovGunError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    items = [
        TarkovGunItemOut(
            id=row.item_id,
            name=row.name,
            short_name=row.short_name,
            caliber=row.caliber,
            weapon_class=row.weapon_class,
            fire_rate=row.fire_rate,
            ergonomics=row.ergonomics,
            recoil_vertical=row.recoil_vertical,
            recoil_horizontal=row.recoil_horizontal,
            effective_distance=row.effective_distance,
            fire_modes=_parse_str_list(row.fire_modes_json),
            default_ammo_id=row.default_ammo_id,
            allowed_ammo_ids=_parse_str_list(row.allowed_ammo_json),
            icon_link=row.icon_link,
        )
        for row in gun_svc.list_guns(db)
    ]
    meta = gun_svc.get_gun_meta(db)
    return TarkovGunCatalogOut(
        items=items,
        gun_count=len(items),
        source=meta.source if meta else None,
        synced_at=meta.synced_at.isoformat() if meta and meta.synced_at else None,
        note=meta.note if meta else None,
    )


@router.post(
    "/guns/sync",
    response_model=TarkovGunSyncOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_guns_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：与 /items/sync 相同（兼容旧客户端）。"""
    result = _sync_items(db)
    return TarkovGunSyncOut(
        ammo_count=int(result.get("ammo_count") or 0),
        gun_count=int(result.get("gun_count") or 0),
        source=result.get("source"),
        synced_at=result.get("synced_at"),
        message="ok",
    )
