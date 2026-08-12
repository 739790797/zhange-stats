from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.guides.schemas import (
    TarkovAmmoCatalogOut,
    TarkovAmmoItemOut,
    TarkovAmmoSyncOut,
)
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services.tarkov_ammo import (
    TarkovAmmoError,
    ensure_ammo,
    get_ammo_meta,
    list_ammo,
    sync_from_upstream,
)

router = APIRouter(prefix="/tarkov")


@router.get(
    "/ammo",
    response_model=TarkovAmmoCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_ammo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """弹药穿透/伤害表。空库时自动从上游同步一次。"""
    _ = user
    try:
        ensure_ammo(db)
    except TarkovAmmoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    items = [
        TarkovAmmoItemOut(
            id=row.item_id,
            name=row.name,
            short_name=row.short_name,
            caliber=row.caliber,
            damage=row.damage,
            penetration=row.penetration,
            armor_damage=row.armor_damage,
        )
        for row in list_ammo(db)
    ]
    meta = get_ammo_meta(db)
    return TarkovAmmoCatalogOut(
        items=items,
        ammo_count=len(items),
        source=meta.source if meta else None,
        synced_at=meta.synced_at.isoformat() if meta and meta.synced_at else None,
        note=meta.note if meta else None,
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
    """管理员：立即从 tarkov.dev（或回退源）同步弹药。"""
    try:
        result = sync_from_upstream(db)
    except TarkovAmmoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovAmmoSyncOut(
        ammo_count=int(result.get("ammo_count") or 0),
        source=result.get("source"),
        synced_at=result.get("synced_at"),
        message="ok",
    )
