import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.guides.schemas import (
    TarkovAmmoCatalogOut,
    TarkovAmmoDetailOut,
    TarkovAmmoItemOut,
    TarkovAmmoSyncOut,
    TarkovCatalogItemOut,
    TarkovCatalogOut,
    TarkovGunCatalogOut,
    TarkovGunItemOut,
    TarkovGunSyncOut,
    TarkovItemDetailOut,
    TarkovItemsSyncOut,
    TarkovTaskCatalogOut,
    TarkovTaskDetailOut,
    TarkovTasksSyncOut,
    TarkovBossCatalogOut,
    TarkovBossDetailOut,
    TarkovBossesSyncOut,
    TarkovTraderCatalogOut,
    TarkovTraderDetailOut,
    TarkovTradersSyncOut,
    TarkovSiteSearchOut,
    TarkovTrackerBindIn,
    TarkovTrackerStatusOut,
    TarkovMapCatalogOut,
    TarkovMapDetailOut,
    TarkovHideoutCatalogOut,
    TarkovHideoutDetailOut,
    TarkovBarterCatalogOut,
    TarkovCraftCatalogOut,
    TarkovGuidesSyncOut,
    TarkovLootTierCatalogOut,
)
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services import tarkov_ammo as ammo_svc
from app.services import tarkov_bosses as bosses_svc
from app.services import tarkov_catalog as catalog_svc
from app.services import tarkov_guides as guides_svc
from app.services import tarkov_guns as gun_svc
from app.services import tarkov_items as items_svc
from app.services import tarkov_maps as maps_svc
from app.services import tarkov_tasks as tasks_svc
from app.services import tarkov_traders as traders_svc
from app.services import tarkov_search as search_svc
from app.services import tarkov_tracker as tracker_svc

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


def _parse_csv_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


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
    "/items",
    response_model=TarkovCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_item_catalog(
    category_ids: str | None = None,
    types: str | None = None,
    q: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """手册物品目录：按 handbook 分类 / types 过滤，分页返回（读 raw）。"""
    _ = user
    try:
        result = catalog_svc.list_catalog(
            db,
            category_ids=_parse_csv_ids(category_ids),
            types=_parse_csv_ids(types),
            q=q,
            page=page,
            page_size=page_size,
        )
    except items_svc.TarkovItemsError as exc:
        msg = str(exc)
        if msg.startswith("请指定"):
            raise HTTPException(status_code=400, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return TarkovCatalogOut(
        items=[TarkovCatalogItemOut(**row) for row in result["items"]],
        item_count=int(result.get("item_count") or 0),
        page=int(result.get("page") or page),
        page_size=int(result.get("page_size") or page_size),
        source=result.get("source"),
        synced_at=result.get("synced_at"),
        note=result.get("note"),
    )


@router.get(
    "/search",
    response_model=TarkovSiteSearchOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_site_search(
    q: str = Query(default="", max_length=80),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """攻略站全站搜索：物品 / 任务 / 商人 / BOSS（有 raw 才查，不回源）。"""
    _ = user
    return TarkovSiteSearchOut.model_validate(search_svc.search_site(db, q))


@router.get(
    "/items/{item_id}",
    response_model=TarkovItemDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_item_detail(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """通用物品详情：从 items raw 返回完整 item / properties。"""
    _ = user
    try:
        detail = catalog_svc.get_item_detail(db, item_id)
    except items_svc.TarkovItemsError as exc:
        msg = str(exc)
        if msg.startswith("未找到物品") or msg.startswith("物品 id"):
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return TarkovItemDetailOut(
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


def _sync_tasks(db: Session) -> dict:
    try:
        return tasks_svc.sync_from_upstream(db)
    except tasks_svc.TarkovTasksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/tasks/sync",
    response_model=TarkovTasksSyncOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_tasks_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：回源同步任务（GraphQL 优先，失败回退 json.tarkov.dev）。"""
    result = _sync_tasks(db)
    return TarkovTasksSyncOut(
        task_count=int(result.get("task_count") or 0),
        source=result.get("source"),
        synced_at=result.get("synced_at"),
        message="ok",
    )


@router.get(
    "/tasks",
    response_model=TarkovTaskCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_catalog(
    q: str | None = Query(default=None, max_length=80),
    trader: str | None = Query(default=None, max_length=64),
    map_slug: str | None = Query(default=None, max_length=64, alias="map"),
    kappa: bool | None = Query(default=None),
    progress: bool = Query(default=False),
    progress_status: str | None = Query(default=None, max_length=16),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """任务目录：商人 / 地图 / Kappa / 关键词过滤，分页返回。"""
    bound, snap = False, None
    if progress or (progress_status or "").strip():
        bound, snap = tracker_svc.user_progress_snapshot(db, user)
    try:
        result = tasks_svc.list_tasks(
            db,
            trader=trader,
            map_slug=map_slug,
            kappa=kappa,
            q=q,
            page=page,
            page_size=page_size,
            progress=snap if progress else None,
            progress_status=progress_status if progress and snap else None,
            progress_bound=bound if progress else False,
        )
    except tasks_svc.TarkovTasksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovTaskCatalogOut.model_validate(result)


@router.get(
    "/tasks/{task_id}",
    response_model=TarkovTaskDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_detail(
    task_id: str,
    progress: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """任务详情：目标、前置、奖励（投影，不含多边形）。"""
    bound, snap = False, None
    if progress:
        bound, snap = tracker_svc.user_progress_snapshot(db, user)
    try:
        detail = tasks_svc.get_task_detail(
            db,
            task_id,
            progress=snap if progress else None,
            progress_bound=bound if progress else False,
        )
    except tasks_svc.TarkovTasksError as exc:
        msg = str(exc)
        if msg.startswith("未找到任务") or msg.startswith("任务 id"):
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return TarkovTaskDetailOut.model_validate(detail)


def _sync_traders(db: Session) -> dict:
    try:
        return traders_svc.sync_from_upstream(db)
    except traders_svc.TarkovTradersError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/traders/sync",
    response_model=TarkovTradersSyncOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_traders_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：回源同步商人元数据与现金报价（json.tarkov.dev + 物品 buyFromTrader）。"""
    result = _sync_traders(db)
    return TarkovTradersSyncOut(
        trader_count=int(result.get("trader_count") or 0),
        offer_count=int(result.get("offer_count") or 0),
        source=result.get("source"),
        synced_at=result.get("synced_at"),
        message="ok",
    )


@router.get(
    "/traders",
    response_model=TarkovTraderCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_trader_catalog(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """商人目录：头像 / 英文 / 中文简称 / 报价数量。"""
    _ = user
    try:
        result = traders_svc.list_traders(db)
    except traders_svc.TarkovTradersError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovTraderCatalogOut.model_validate(result)


@router.get(
    "/traders/{trader_slug}",
    response_model=TarkovTraderDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_trader_detail(
    trader_slug: str,
    level: int | None = Query(default=None, ge=1, le=4),
    q: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """商人详情：简介、补货时间、忠诚等级现金报价。"""
    _ = user
    try:
        detail = traders_svc.get_trader_detail(
            db,
            trader_slug,
            level=level,
            q=q,
            page=page,
            page_size=page_size,
        )
    except traders_svc.TarkovTradersError as exc:
        msg = str(exc)
        if msg.startswith("未找到商人") or msg.startswith("商人 slug"):
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return TarkovTraderDetailOut.model_validate(detail)


def _sync_bosses(db: Session) -> dict:
    try:
        return bosses_svc.sync_from_upstream(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/bosses/sync",
    response_model=TarkovBossesSyncOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_bosses_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：回源同步 BOSS 出生率 / 生命值 / 护卫（json.tarkov.dev maps）。"""
    result = _sync_bosses(db)
    return TarkovBossesSyncOut(
        boss_count=int(result.get("boss_count") or 0),
        source=result.get("source"),
        synced_at=result.get("synced_at"),
        message="ok",
    )


@router.get(
    "/bosses",
    response_model=TarkovBossCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_boss_catalog(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """BOSS 目录：头像 / 英文名 / 中文昵称 / 出生地图。"""
    _ = user
    try:
        result = bosses_svc.list_bosses(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovBossCatalogOut.model_validate(result)


@router.get(
    "/bosses/{boss_slug}",
    response_model=TarkovBossDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_boss_detail(
    boss_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """BOSS 详情：行为、地图、刷新概率、生命值、特殊战利品。"""
    _ = user
    try:
        detail = bosses_svc.get_boss_detail(db, boss_slug)
    except bosses_svc.TarkovBossesError as exc:
        msg = str(exc)
        if msg.startswith("未找到 BOSS") or msg.startswith("BOSS slug"):
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return TarkovBossDetailOut.model_validate(detail)


def _sync_guides(db: Session) -> dict:
    try:
        return guides_svc.sync_from_upstream(db)
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/maps",
    response_model=TarkovMapCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_catalog(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """地图目录：时长 / 人数 / 缩略图（读 bosses maps raw）。"""
    _ = user
    try:
        result = maps_svc.list_maps(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovMapCatalogOut.model_validate(result)


@router.get(
    "/maps/{map_slug}",
    response_model=TarkovMapDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_detail(
    map_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """地图详情：撤离点、BOSS、突袭时长；互动图层链到 tarkov.dev。"""
    _ = user
    try:
        detail = maps_svc.get_map_detail(db, map_slug)
    except bosses_svc.TarkovBossesError as exc:
        msg = str(exc)
        if msg.startswith("未找到地图") or "slug 无效" in msg:
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return TarkovMapDetailOut.model_validate(detail)


@router.post(
    "/guides/sync",
    response_model=TarkovGuidesSyncOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_guides_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：回源同步藏身处 / 以物易物 / 制作。"""
    result = _sync_guides(db)
    return TarkovGuidesSyncOut.model_validate({**result, "message": "ok"})


@router.get(
    "/hideout",
    response_model=TarkovHideoutCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_hideout_catalog(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """藏身处模块与升级材料。"""
    _ = user
    try:
        result = guides_svc.list_hideout(db)
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovHideoutCatalogOut.model_validate(result)


@router.get(
    "/hideout/{station_slug}",
    response_model=TarkovHideoutDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_hideout_detail(
    station_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """单个藏身处模块的全部等级。"""
    _ = user
    try:
        detail = guides_svc.get_hideout_station(db, station_slug)
    except guides_svc.TarkovGuidesError as exc:
        msg = str(exc)
        if msg.startswith("未找到") or "slug 无效" in msg:
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return TarkovHideoutDetailOut.model_validate(detail)


@router.get(
    "/barters",
    response_model=TarkovBarterCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_barter_catalog(
    q: str | None = Query(default=None, max_length=80),
    trader: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """商人以物易物。"""
    _ = user
    try:
        result = guides_svc.list_barters(
            db, trader=trader, q=q, page=page, page_size=page_size
        )
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovBarterCatalogOut.model_validate(result)


@router.get(
    "/crafts",
    response_model=TarkovCraftCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_craft_catalog(
    q: str | None = Query(default=None, max_length=80),
    station: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """藏身处制作。"""
    _ = user
    try:
        result = guides_svc.list_crafts(
            db, station=station, q=q, page=page, page_size=page_size
        )
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovCraftCatalogOut.model_validate(result)


@router.get(
    "/loot-tiers",
    response_model=TarkovLootTierCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_loot_tiers(
    q: str | None = Query(default=None, max_length=80),
    tier: str | None = Query(default=None, max_length=8),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """战利品等级：跳蚤每格价分档。"""
    _ = user
    try:
        result = catalog_svc.list_loot_tiers(
            db, q=q, tier=tier, page=page, page_size=page_size
        )
    except items_svc.TarkovItemsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovLootTierCatalogOut.model_validate(result)


def _tracker_http_error(exc: tracker_svc.TarkovTrackerError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get(
    "/progress",
    response_model=TarkovTrackerStatusOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_progress_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户 Tarkov Tracker 绑定摘要（不回传明文 token）。"""
    return TarkovTrackerStatusOut.model_validate(tracker_svc.get_status(db, user))


@router.put(
    "/progress/tracker-token",
    response_model=TarkovTrackerStatusOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_progress_bind(
    payload: TarkovTrackerBindIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """绑定 Tarkov Tracker token 并立刻拉取等级 / 进度摘要。"""
    try:
        result = tracker_svc.bind_token(db, user, payload.token)
    except tracker_svc.TarkovTrackerError as exc:
        raise _tracker_http_error(exc) from exc
    return TarkovTrackerStatusOut.model_validate(result)


@router.delete(
    "/progress/tracker-token",
    response_model=TarkovTrackerStatusOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_progress_unbind(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """解绑 Tarkov Tracker token。"""
    return TarkovTrackerStatusOut.model_validate(tracker_svc.unbind_token(db, user))


@router.post(
    "/progress/sync",
    response_model=TarkovTrackerStatusOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_progress_sync(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """已绑定：从 Tarkov Tracker 再拉一次进度摘要。"""
    try:
        result = tracker_svc.sync_progress(db, user)
    except tracker_svc.TarkovTrackerError as exc:
        raise _tracker_http_error(exc) from exc
    return TarkovTrackerStatusOut.model_validate(result)
