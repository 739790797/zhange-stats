import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.guides import tarkov_goons, tarkov_raid_rooms
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
    TarkovFullSyncOut,
    TarkovTaskCatalogOut,
    TarkovTaskDetailOut,
    TarkovTasksSyncOut,
    TarkovRaidPrepOut,
    TarkovBossCatalogOut,
    TarkovBossDetailOut,
    TarkovBossesSyncOut,
    TarkovTraderCatalogOut,
    TarkovTraderDetailOut,
    TarkovTradersSyncOut,
    TarkovSiteSearchOut,
    TarkovMapCatalogOut,
    TarkovMapDetailOut,
    TarkovMapLootOut,
    TarkovMapPlaceIn,
    TarkovMapPlaceImportIn,
    TarkovMapPlaceOut,
    TarkovMapPlacePatchIn,
    TarkovMapPlacesOut,
    TarkovHideoutCatalogOut,
    TarkovHideoutDetailOut,
    TarkovBarterCatalogOut,
    TarkovCraftCatalogOut,
    TarkovGuidesSyncOut,
    TarkovLootTierCatalogOut,
    TarkovKeyPacksOut,
    TarkovKeyOwnsIn,
    TarkovKeyOwnsOut,
    TarkovCollectionOut,
    TarkovCollectionOwnsIn,
    TarkovCollectionOwnsOut,
    TarkovCollectionLayoutIn,
    TarkovCollectionLayoutOut,
    TarkovTaskDonesIn,
    TarkovTaskDonesOut,
    TarkovRaidLogsIn,
    TarkovRaidLogsImportOut,
    TarkovRaidLogsOut,
    TarkovUserRaidPrepStateIn,
    TarkovUserRaidPrepStateOut,
)
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.http_cache import catalog_freshness, set_catalog_cache_headers
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services.tarkov import ammo as ammo_svc
from app.services.tarkov import bosses as bosses_svc
from app.services.tarkov import catalog as catalog_svc
from app.services.tarkov import guides as guides_svc
from app.services.tarkov import guns as gun_svc
from app.services.tarkov import items as items_svc
from app.services.tarkov import key_owns as key_owns_svc
from app.services.tarkov import raid_rooms as rooms_svc
from app.services.tarkov import key_packs as key_packs_svc
from app.services.tarkov import collection as collection_svc
from app.services.tarkov import collection_owns as collection_owns_svc
from app.services.tarkov import collection_layout as collection_layout_svc
from app.services.tarkov import task_dones as task_dones_svc
from app.services.tarkov import raid_logs as raid_logs_svc
from app.services.tarkov import raid_prep_state as raid_prep_state_svc
from app.services.tarkov import maps as maps_svc
from app.services.tarkov import places as places_svc
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov import traders as traders_svc
from app.services.tarkov import search as search_svc
from app.services.tarkov import sync as full_sync_svc
from app.services.tarkov.game_mode import (
    parse_game_mode,
    reset_game_mode,
    use_game_mode,
)
from app.services.tarkov.upstream import raw_row_header

router = APIRouter(prefix="/tarkov")


async def tarkov_game_mode(
    game_mode: str = Query(
        default="pvp",
        max_length=16,
        description="PVP（regular）或 PVE",
    ),
):
    """请求级 PVP/PVE。必须 async，避免 sync yield 在线程池里 set/reset ContextVar 崩成 500。"""
    parsed = parse_game_mode(game_mode)
    token = use_game_mode(parsed)
    try:
        yield parsed
    finally:
        reset_game_mode(token)


router.dependencies.append(Depends(tarkov_game_mode))
# include 会把当时的父级 deps 拍进子路由；须先 append 再 include，
# 否则 GET /raid-rooms 吃不到 game_mode，大厅会按默认 PVP 列公开房。
router.include_router(tarkov_raid_rooms.router)
router.include_router(tarkov_goons.router)


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


def _raw_synced(row: object) -> str:
    return raw_row_header(row)[1] or ""  # type: ignore[arg-type]


def _catalog_fresh(
    request: Request,
    *parts: object,
) -> tuple[str, Response | None]:
    return catalog_freshness(request, parse_game_mode(), *parts)


def _catalog_ok(response: Response, etag: str, body: object) -> object:
    set_catalog_cache_headers(response, etag)
    return body


def _sync_items(db: Session) -> dict:
    try:
        return items_svc.sync_from_upstream(db)
    except items_svc.TarkovItemsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/sync",
    response_model=TarkovFullSyncOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_full_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：回源 json.tarkov.dev 全文件，落本地后再投影现有栏目。"""
    try:
        result = full_sync_svc.sync_all_from_upstream(db)
    except full_sync_svc.TarkovFullSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TarkovFullSyncOut.model_validate(result)


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
    request: Request,
    response: Response,
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
        items_svc.ensure_items(db)
    except items_svc.TarkovItemsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "items",
        _raw_synced(items_svc.get_items_raw(db)),
        category_ids,
        types,
        q,
        page,
        page_size,
    )
    if hit is not None:
        return hit
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
    return _catalog_ok(
        response,
        etag,
        TarkovCatalogOut(
            items=[TarkovCatalogItemOut(**row) for row in result["items"]],
            item_count=int(result.get("item_count") or 0),
            page=int(result.get("page") or page),
            page_size=int(result.get("page_size") or page_size),
            source=result.get("source"),
            synced_at=result.get("synced_at"),
            note=result.get("note"),
        ),
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
        locks=detail.get("locks") if isinstance(detail.get("locks"), list) else [],
    )


@router.get(
    "/ammo",
    response_model=TarkovAmmoCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_ammo(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """弹药穿透/伤害表（派生读模型）。空库时走共享 items 同步。"""
    _ = user
    try:
        ammo_svc.ensure_ammo(db)
    except ammo_svc.TarkovAmmoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    source, synced_at, note = items_svc.items_raw_header(db)
    etag, hit = _catalog_fresh(request, "ammo", synced_at)
    if hit is not None:
        return hit
    packs = catalog_svc.list_ammo_pack_index(db)
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
            pack_icon_link=str((packs.get(row.item_id) or {}).get("pack_icon_link") or ""),
            pack_item_id=str((packs.get(row.item_id) or {}).get("pack_item_id") or ""),
        )
        for row in ammo_svc.list_ammo(db)
    ]
    return _catalog_ok(
        response,
        etag,
        TarkovAmmoCatalogOut(
            items=items,
            ammo_count=len(items),
            source=source,
            synced_at=synced_at,
            note=note,
        ),
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """枪械总表（派生读模型）。空库时走共享 items 同步。"""
    _ = user
    try:
        gun_svc.ensure_guns(db)
    except gun_svc.TarkovGunError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    source, synced_at, note = items_svc.items_raw_header(db)
    etag, hit = _catalog_fresh(request, "guns", synced_at)
    if hit is not None:
        return hit
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
    return _catalog_ok(
        response,
        etag,
        TarkovGunCatalogOut(
            items=items,
            gun_count=len(items),
            source=source,
            synced_at=synced_at,
            note=note,
        ),
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
    """管理员：回源同步任务（json.tarkov.dev）。"""
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
    request: Request,
    response: Response,
    q: str | None = Query(default=None, max_length=80),
    trader: str | None = Query(default=None, max_length=64),
    map_slug: str | None = Query(default=None, max_length=64, alias="map"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    layout: str | None = Query(default="table", max_length=16),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """任务目录：商人 / 地图 / 关键词过滤。layout=all 时不分页，返回筛选后的全量。"""
    _ = user
    try:
        tasks_svc.ensure_tasks(db)
    except tasks_svc.TarkovTasksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "tasks",
        "trader-en",
        _raw_synced(tasks_svc.get_tasks_raw(db)),
        q,
        trader,
        map_slug,
        page,
        page_size,
        layout,
    )
    if hit is not None:
        return hit
    try:
        result = tasks_svc.list_tasks(
            db,
            trader=trader,
            map_slug=map_slug,
            q=q,
            page=page,
            page_size=page_size,
            layout=layout,
        )
    except tasks_svc.TarkovTasksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovTaskCatalogOut.model_validate(result)
    )


@router.get(
    "/raid-prep",
    response_model=TarkovRaidPrepOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_raid_prep(
    request: Request,
    response: Response,
    map_slug: str = Query(..., alias="map", max_length=64),
    q: str | None = Query(default=None, max_length=80),
    trader: str | None = Query(default=None, max_length=64),
    types: str | None = Query(default=None, max_length=200),
    geometry: bool = Query(default=False),
    ids: str | None = Query(default=None, max_length=1200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """联机大厅：按地图列出相关任务。默认目录不含目标正文；geometry+ids 才返回点位。"""
    _ = user
    type_list = _parse_csv_ids(types)
    id_list = _parse_csv_ids(ids)[:40]
    try:
        tasks_svc.ensure_tasks(db)
    except tasks_svc.TarkovTasksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "raid-prep",
        "trader-en",
        _raw_synced(tasks_svc.get_tasks_raw(db)),
        map_slug,
        q,
        trader,
        types,
        int(geometry),
        ids,
    )
    if hit is not None:
        return hit
    try:
        result = tasks_svc.list_raid_prep(
            db,
            map_slug,
            trader=trader,
            q=q,
            types=type_list or None,
            geometry=bool(geometry),
            task_ids=id_list or None,
        )
    except tasks_svc.TarkovTasksError as exc:
        msg = str(exc)
        if msg.startswith("地图无效"):
            raise HTTPException(status_code=400, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return _catalog_ok(
        response, etag, TarkovRaidPrepOut.model_validate(result)
    )


@router.get(
    "/raid-prep/state",
    response_model=TarkovUserRaidPrepStateOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_raid_prep_state_get(
    map_slug: str = Query(..., alias="map", max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """联机大厅单人准备：当前模式/地图的勾选、目标完成和钥匙声明。"""
    try:
        data = raid_prep_state_svc.get_state(db, user, map_slug)
    except raid_prep_state_svc.TarkovRaidPrepStateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return TarkovUserRaidPrepStateOut.model_validate(data)


@router.put(
    "/raid-prep/state",
    response_model=TarkovUserRaidPrepStateOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_raid_prep_state_put(
    body: TarkovUserRaidPrepStateIn,
    map_slug: str = Query(..., alias="map", max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        data = raid_prep_state_svc.put_state(
            db,
            user,
            map_slug,
            selected=body.selected,
            objective_dones=[item.model_dump() for item in body.objective_dones],
            key_brings=body.key_brings,
        )
    except raid_prep_state_svc.TarkovRaidPrepStateError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    return TarkovUserRaidPrepStateOut.model_validate(data)


@router.get(
    "/tasks/{task_id}",
    response_model=TarkovTaskDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """任务详情：目标、奖励（投影，不含多边形）。"""
    try:
        detail = tasks_svc.get_task_detail(db, task_id)
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """商人目录：头像 / 英文名 / 报价数量。"""
    _ = user
    try:
        traders_svc.ensure_traders(db)
    except traders_svc.TarkovTradersError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "traders",
        "trader-en",
        _raw_synced(traders_svc.get_traders_raw(db)),
    )
    if hit is not None:
        return hit
    try:
        result = traders_svc.list_traders(db)
    except traders_svc.TarkovTradersError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovTraderCatalogOut.model_validate(result)
    )


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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """BOSS 目录：头像 / 英文名 / 出生地图。"""
    _ = user
    try:
        bosses_svc.ensure_maps(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request, "bosses", maps_svc.maps_cache_token(db)
    )
    if hit is not None:
        return hit
    try:
        result = bosses_svc.list_bosses(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovBossCatalogOut.model_validate(result)
    )


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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """地图目录：时长 / 人数 / 缩略图（读 bosses maps raw）。"""
    _ = user
    try:
        if maps_svc.get_maps_raw(db) is None:
            maps_svc.ensure_maps(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(request, "maps", maps_svc.maps_cache_token(db))
    if hit is not None:
        return hit
    try:
        result = maps_svc.list_maps(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovMapCatalogOut.model_validate(result)
    )


@router.get(
    "/maps/{map_slug}",
    response_model=TarkovMapDetailOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_detail(
    request: Request,
    response: Response,
    map_slug: str,
    loot_loose: bool = Query(default=False),
    loot_containers: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """地图详情：撤离点/BOSS/门锁等坐标与底图信息；散落物/容器默认不下发。"""
    _ = user
    try:
        if maps_svc.get_maps_raw(db) is None:
            maps_svc.ensure_maps(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        places_token = places_svc.places_cache_token(db, map_slug)
    except places_svc.TarkovMapPlacesError:
        places_token = ""
    etag, hit = _catalog_fresh(
        request,
        "map-detail",
        map_slug,
        int(loot_loose),
        int(loot_containers),
        maps_svc.maps_cache_token(db),
        places_token,
    )
    if hit is not None:
        return hit
    try:
        detail = maps_svc.get_map_detail(
            db,
            map_slug,
            loot_loose=loot_loose,
            loot_containers=loot_containers,
        )
    except bosses_svc.TarkovBossesError as exc:
        msg = str(exc)
        if msg.startswith("未找到地图") or "slug 无效" in msg:
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    try:
        detail["places"] = places_svc.list_places(db, map_slug)
    except places_svc.TarkovMapPlacesError as exc:
        raise _places_error(exc) from exc
    return _catalog_ok(response, etag, TarkovMapDetailOut.model_validate(detail))


@router.get(
    "/maps/{map_slug}/loot",
    response_model=TarkovMapLootOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_loot(
    request: Request,
    response: Response,
    map_slug: str,
    loot_loose: bool = Query(default=False),
    loot_containers: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """地图散落物/容器图层；只解析当前 slug。"""
    _ = user
    try:
        if maps_svc.get_maps_raw(db) is None:
            maps_svc.ensure_maps(db)
    except bosses_svc.TarkovBossesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "map-loot",
        map_slug,
        int(loot_loose),
        int(loot_containers),
        maps_svc.maps_cache_token(db),
    )
    if hit is not None:
        return hit
    try:
        layers = maps_svc.get_map_loot_layers(
            db,
            map_slug,
            loot_loose=loot_loose,
            loot_containers=loot_containers,
        )
    except bosses_svc.TarkovBossesError as exc:
        msg = str(exc)
        if msg.startswith("未找到地图") or "slug 无效" in msg:
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return _catalog_ok(response, etag, TarkovMapLootOut.model_validate(layers))


def _places_error(exc: places_svc.TarkovMapPlacesError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get(
    "/maps/{map_slug}/places",
    response_model=TarkovMapPlacesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_places(
    map_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """某图自定义地名（变体与父图共用）。"""
    _ = user
    try:
        key = places_svc.place_map_key(map_slug)
        items = places_svc.list_places(db, map_slug)
    except places_svc.TarkovMapPlacesError as exc:
        raise _places_error(exc) from exc
    return TarkovMapPlacesOut(map_key=key, items=items)


@router.post(
    "/maps/{map_slug}/places",
    response_model=TarkovMapPlaceOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_place_create(
    map_slug: str,
    body: TarkovMapPlaceIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：新增一个点或框。"""
    try:
        row = places_svc.create_place(db, map_slug, body.model_dump())
    except places_svc.TarkovMapPlacesError as exc:
        raise _places_error(exc) from exc
    db.commit()
    return TarkovMapPlaceOut.model_validate(row)


@router.post(
    "/maps/{map_slug}/places/import",
    response_model=TarkovMapPlacesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_places_import(
    map_slug: str,
    body: TarkovMapPlaceImportIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：把当前画面地名一次写入（仅空图）。"""
    try:
        key = places_svc.place_map_key(map_slug)
        items = places_svc.import_places(
            db,
            map_slug,
            [item.model_dump() for item in body.items],
        )
    except places_svc.TarkovMapPlacesError as exc:
        raise _places_error(exc) from exc
    db.commit()
    return TarkovMapPlacesOut(map_key=key, items=items)


@router.patch(
    "/maps/{map_slug}/places/{place_id}",
    response_model=TarkovMapPlaceOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_place_update(
    map_slug: str,
    place_id: int,
    body: TarkovMapPlacePatchIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：改名、移位或改框。"""
    try:
        row = places_svc.update_place(
            db,
            map_slug,
            place_id,
            body.model_dump(exclude_unset=True),
        )
    except places_svc.TarkovMapPlacesError as exc:
        raise _places_error(exc) from exc
    db.commit()
    return TarkovMapPlaceOut.model_validate(row)


@router.delete(
    "/maps/{map_slug}/places/{place_id}",
    response_model=TarkovMapPlacesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_map_place_delete(
    map_slug: str,
    place_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：删除一个地点。"""
    try:
        places_svc.delete_place(db, map_slug, place_id)
        key = places_svc.place_map_key(map_slug)
        items = places_svc.list_places(db, map_slug)
    except places_svc.TarkovMapPlacesError as exc:
        raise _places_error(exc) from exc
    db.commit()
    return TarkovMapPlacesOut(map_key=key, items=items)


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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """藏身处模块与升级材料。"""
    _ = user
    try:
        guides_svc.ensure_guides(db)
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request, "hideout", "trader-en", guides_svc.guides_cache_token(db)
    )
    if hit is not None:
        return hit
    try:
        result = guides_svc.list_hideout(db)
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovHideoutCatalogOut.model_validate(result)
    )


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
    request: Request,
    response: Response,
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
        guides_svc.ensure_guides(db)
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "barters",
        "trader-en",
        guides_svc.guides_cache_token(db),
        q,
        trader,
        page,
        page_size,
    )
    if hit is not None:
        return hit
    try:
        result = guides_svc.list_barters(
            db, trader=trader, q=q, page=page, page_size=page_size
        )
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovBarterCatalogOut.model_validate(result)
    )


@router.get(
    "/crafts",
    response_model=TarkovCraftCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_craft_catalog(
    request: Request,
    response: Response,
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
        guides_svc.ensure_guides(db)
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "crafts",
        guides_svc.guides_cache_token(db),
        q,
        station,
        page,
        page_size,
    )
    if hit is not None:
        return hit
    try:
        result = guides_svc.list_crafts(
            db, station=station, q=q, page=page, page_size=page_size
        )
    except guides_svc.TarkovGuidesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovCraftCatalogOut.model_validate(result)
    )


@router.get(
    "/loot-tiers",
    response_model=TarkovLootTierCatalogOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_loot_tiers(
    request: Request,
    response: Response,
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
        items_svc.ensure_items(db)
    except items_svc.TarkovItemsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "loot-tiers",
        _raw_synced(items_svc.get_items_raw(db)),
        q,
        tier,
        page,
        page_size,
    )
    if hit is not None:
        return hit
    try:
        result = catalog_svc.list_loot_tiers(
            db, q=q, tier=tier, page=page, page_size=page_size
        )
    except items_svc.TarkovItemsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovLootTierCatalogOut.model_validate(result)
    )


@router.get(
    "/key-packs",
    response_model=TarkovKeyPacksOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_key_packs(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """钥匙分类速查：门锁 / 入场钥按地图分包；附带用途（任务需要 / 门锁类型）。"""
    _ = user
    try:
        items_svc.ensure_items(db)
        if maps_svc.get_maps_raw(db) is None:
            maps_svc.ensure_maps(db)
        tasks_svc.ensure_tasks(db)
    except (
        items_svc.TarkovItemsError,
        bosses_svc.TarkovBossesError,
        tasks_svc.TarkovTasksError,
    ) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "key-packs",
        "trader-en",
        _raw_synced(items_svc.get_items_raw(db)),
        maps_svc.maps_cache_token(db),
        _raw_synced(tasks_svc.get_tasks_raw(db)),
    )
    if hit is not None:
        return hit
    try:
        result = key_packs_svc.list_key_packs(db)
    except key_packs_svc.TarkovKeyPacksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovKeyPacksOut.model_validate(result)
    )


def _key_owns_error(exc: key_owns_svc.TarkovKeyOwnsError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get(
    "/key-owns",
    response_model=TarkovKeyOwnsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_key_owns_list(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户仓库里勾选的钥匙。"""
    return TarkovKeyOwnsOut(item_ids=key_owns_svc.list_item_ids(db, user.id))


@router.put(
    "/key-owns",
    response_model=TarkovKeyOwnsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_key_owns_merge(
    body: TarkovKeyOwnsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """合并写入一批「我有」（本机勾选迁到账号）。"""
    ids = key_owns_svc.merge_owns(db, user, body.item_ids)
    db.commit()
    rooms_svc.publish_occupant_key_owns(db, user)
    return TarkovKeyOwnsOut(item_ids=ids)


@router.put(
    "/key-owns/{item_id}",
    response_model=TarkovKeyOwnsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_key_owns_add(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        ids, _added = key_owns_svc.add_own(db, user, item_id)
    except key_owns_svc.TarkovKeyOwnsError as exc:
        raise _key_owns_error(exc) from exc
    db.commit()
    rooms_svc.publish_occupant_key_owns(db, user)
    return TarkovKeyOwnsOut(item_ids=ids)


@router.delete(
    "/key-owns/{item_id}",
    response_model=TarkovKeyOwnsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_key_owns_remove(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        ids, _removed = key_owns_svc.remove_own(db, user, item_id)
    except key_owns_svc.TarkovKeyOwnsError as exc:
        raise _key_owns_error(exc) from exc
    db.commit()
    rooms_svc.publish_occupant_key_owns(db, user)
    return TarkovKeyOwnsOut(item_ids=ids)


@router.get(
    "/collection",
    response_model=TarkovCollectionOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_collection(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """3×4 收集：收集者任务需上交的道具，按目标顺序。"""
    _ = user
    try:
        items_svc.ensure_items(db)
        tasks_svc.ensure_tasks(db)
    except (items_svc.TarkovItemsError, tasks_svc.TarkovTasksError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    etag, hit = _catalog_fresh(
        request,
        "collection",
        _raw_synced(items_svc.get_items_raw(db)),
        _raw_synced(tasks_svc.get_tasks_raw(db)),
    )
    if hit is not None:
        return hit
    try:
        result = collection_svc.list_collection(db)
    except collection_svc.TarkovCollectionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _catalog_ok(
        response, etag, TarkovCollectionOut.model_validate(result)
    )


def _collection_owns_error(
    exc: collection_owns_svc.TarkovCollectionOwnsError,
) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get(
    "/collection-owns",
    response_model=TarkovCollectionOwnsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_collection_owns_list(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return TarkovCollectionOwnsOut(
        item_ids=collection_owns_svc.list_item_ids(db, user.id)
    )


@router.put(
    "/collection-owns",
    response_model=TarkovCollectionOwnsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_collection_owns_merge(
    body: TarkovCollectionOwnsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ids = collection_owns_svc.merge_owns(db, user, body.item_ids)
    db.commit()
    return TarkovCollectionOwnsOut(item_ids=ids)


@router.put(
    "/collection-owns/{item_id}",
    response_model=TarkovCollectionOwnsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_collection_owns_add(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        ids, _added = collection_owns_svc.add_own(db, user, item_id)
    except collection_owns_svc.TarkovCollectionOwnsError as exc:
        raise _collection_owns_error(exc) from exc
    db.commit()
    return TarkovCollectionOwnsOut(item_ids=ids)


@router.delete(
    "/collection-owns/{item_id}",
    response_model=TarkovCollectionOwnsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_collection_owns_remove(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        ids, _removed = collection_owns_svc.remove_own(db, user, item_id)
    except collection_owns_svc.TarkovCollectionOwnsError as exc:
        raise _collection_owns_error(exc) from exc
    db.commit()
    return TarkovCollectionOwnsOut(item_ids=ids)


@router.get(
    "/collection-layout",
    response_model=TarkovCollectionLayoutOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_collection_layout_get(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return TarkovCollectionLayoutOut.model_validate(
        collection_layout_svc.get_layout(db, user.id)
    )


@router.put(
    "/collection-layout",
    response_model=TarkovCollectionLayoutOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_collection_layout_put(
    body: TarkovCollectionLayoutIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = collection_layout_svc.replace_layout(
        db,
        user,
        [item.model_dump() for item in body.placements],
    )
    db.commit()
    return TarkovCollectionLayoutOut.model_validate(payload)


def _task_dones_error(exc: task_dones_svc.TarkovTaskDonesError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _task_progress_out(db: Session, user: User) -> TarkovTaskDonesOut:
    done, started, objectives = task_dones_svc.account_progress(db, user.id)
    catalog = tasks_svc.catalog_task_id_set(db)
    done, started = task_dones_svc.filter_visible_progress(
        done,
        started,
        catalog,
    )
    if catalog is not None:
        objectives = [item for item in objectives if item["task_id"] in catalog]
    return TarkovTaskDonesOut(
        task_ids=done,
        started_ids=started,
        objective_dones=objectives,
    )


@router.get(
    "/task-dones",
    response_model=TarkovTaskDonesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_dones_list(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前模式的账号进度账：已完成、进行中与小步骤勾选。"""
    return _task_progress_out(db, user)


@router.put(
    "/task-dones",
    response_model=TarkovTaskDonesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_dones_write(
    body: TarkovTaskDonesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """合并或整表替换当前模式的完成 / 进行中 / 小步骤。省略 started_ids 或 objective_dones 则不改对应集合。"""
    task_dones_svc.write_progress(
        db,
        user,
        body.task_ids,
        body.started_ids,
        replace=body.replace,
        objective_dones=(
            [item.model_dump() for item in body.objective_dones]
            if body.objective_dones is not None
            else None
        ),
    )
    db.commit()
    return _task_progress_out(db, user)


@router.put(
    "/task-dones/{task_id}",
    response_model=TarkovTaskDonesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_dones_add(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        task_dones_svc.add_done(db, user, task_id)
    except task_dones_svc.TarkovTaskDonesError as exc:
        raise _task_dones_error(exc) from exc
    db.commit()
    return _task_progress_out(db, user)


@router.delete(
    "/task-dones/{task_id}",
    response_model=TarkovTaskDonesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_dones_remove(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        task_dones_svc.remove_done(db, user, task_id)
    except task_dones_svc.TarkovTaskDonesError as exc:
        raise _task_dones_error(exc) from exc
    db.commit()
    return _task_progress_out(db, user)


@router.put(
    "/task-dones/{task_id}/objectives/{objective_id}",
    response_model=TarkovTaskDonesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_objective_add(
    task_id: str,
    objective_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        task_dones_svc.add_objective(db, user, task_id, objective_id)
    except task_dones_svc.TarkovTaskDonesError as exc:
        raise _task_dones_error(exc) from exc
    db.commit()
    return _task_progress_out(db, user)


@router.delete(
    "/task-dones/{task_id}/objectives/{objective_id}",
    response_model=TarkovTaskDonesOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_task_objective_remove(
    task_id: str,
    objective_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        task_dones_svc.remove_objective(db, user, task_id, objective_id)
    except task_dones_svc.TarkovTaskDonesError as exc:
        raise _task_dones_error(exc) from exc
    db.commit()
    return _task_progress_out(db, user)


@router.post(
    "/raid-logs",
    response_model=TarkovRaidLogsImportOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_raid_logs_import(
    body: TarkovRaidLogsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """本机解析后的战局摘要落库；不接收日志原文。"""
    result = raid_logs_svc.upsert_raids(
        db,
        user,
        [item.model_dump() for item in body.raids],
    )
    db.commit()
    return TarkovRaidLogsImportOut.model_validate(result)


@router.get(
    "/raid-logs",
    response_model=TarkovRaidLogsOut,
    dependencies=[Depends(require_feature("guides.tarkov"))],
)
def guides_tarkov_raid_logs_list(
    map_id: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """最近导入的战局摘要，可供联机大厅战后结算。"""
    data = raid_logs_svc.list_raids(
        db, user, map_id=map_id or "", limit=limit
    )
    return TarkovRaidLogsOut.model_validate(data)
