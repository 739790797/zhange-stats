"""Version discovery and persistent, content-addressed display resources."""

from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.http_client import HttpRequestError, http_request
from app.core.paths import resolve_install_dir
from app.core.timeutil import to_naive
from app.models.arknights_stronghold import StrongholdVersion
from app.schemas.stronghold import StrongholdVersionOut
from app.services.skland.arknights_catalog import CHARACTER_TABLE_REL
from app.services.skland.stronghold_operator_assets import list_values, module_reference, skill_reference
from app.services.skland.stronghold_source import _description, _flag, _icon, _key, _label, _number, _obj, _scope
from app.services.upstream_repos import REPO_ARKNIGHTS, RepoError, read_repo_text

_ASSET_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
_ASSET_BYTES = 4 * 1024 * 1024
_ASSET_PIXELS = 12_000_000
_ICONS = "https://web.hycdn.cn/arknights/game/assets/auto_chess"
_ACTIVATION_RULES = {
    "count_threshold_upward": "at_least",
    "count_threshold_downward": "at_most",
    "count_threshold_upward_golden": "golden",
}


def version_key(activity: str, version: str | None) -> str | None:
    return f"{activity}:{version}" if version else None


def _game_catalog(
    shared: dict, content: dict, characters: dict, skills: dict, modules: dict, effects: dict, enemies: dict
) -> dict:
    strategies = {}
    bands = _obj(shared.get("bandDataDict"))
    for key, row in _obj(content.get("bandDataListDict")).items():
        row = _obj(row)
        if not _key(key) or row.get("bandId") != key:
            continue
        band = _obj(bands.get(key))
        text = _description(row.get("bandDesc"))
        title, delim, body = (text or "").partition("】")
        name = _label(title[1:]) if delim and title.startswith("【") else None
        strategies[key] = {
            "name": name,
            "description": (body.strip() or None) if name else text,
            "icon_url": _icon(f"{_ICONS}/band_icon/{key}.png"),
            "promoter": _label(band.get("bandName")),
            "initial_hp": _number(row.get("totalHp")),
        }
    bonds = {}
    bond_meta = _obj(shared.get("bondInfoDict"))
    chess = _obj(content.get("charShopChessDatas"))
    normal_ids = {key: key for key in chess if _key(key)}
    for key, row in chess.items():
        if key in normal_ids and (golden := _key(_obj(row).get("goldenChessId"))):
            normal_ids.setdefault(golden, key)
    for key, normal in _obj(content.get("chessNormalIdLookupDict")).items():
        if _key(key) and _key(normal) in chess:
            normal_ids[key] = normal
    units = {}
    unit_data = _obj(content.get("charChessDataDict"))
    for key in dict.fromkeys((*unit_data, *normal_ids)):
        if not _key(key):
            continue
        unit = _obj(unit_data.get(key))
        normal = normal_ids.get(key)
        shop = _obj(chess.get(normal))
        status = _obj(unit.get("status"))
        char_id = _key(shop.get("charId"))
        character = _obj(characters.get(char_id))
        units[key] = {
            "is_elite": _flag(unit.get("isGolden")),
            "normal_chess_id": normal,
            # A substitute is selectable for some chess IDs; only use the primary character for a missing battle field
            # if the table guarantees there is no different backup character.
            "char_id": char_id if _key(shop.get("backupCharId")) in (None, char_id) else None,
            "name": _label(character.get("name")),
            "primary_char_id": char_id,
            "profession": _key(character.get("profession")),
            "tier": _number(shop.get("chessLevel")),
            "skill_level": _number(status.get("skillLevel")),
            "module_level": _number(status.get("equipLevel")),
            "traits": [trait for item in list_values(unit.get("garrisonIds")) if (trait := _key(item))]
            if isinstance(unit.get("garrisonIds"), list)
            else None,
        }
    for key, row in _obj(content.get("bondInfoDict")).items():
        row = _obj(row)
        if not _key(key) or row.get("bondId") != key:
            continue
        meta = _obj(bond_meta.get(key))
        operators = None
        ids = row.get("chessIdList")
        # A bond may opt out of the roster in-game (e.g. 绝技); don't turn that into a loading failure.
        show_operators = _flag(meta.get("isHiddenCharList")) is not True
        if isinstance(ids, list) and show_operators:
            entries = {}
            for item in ids:
                unit = _obj(units.get(_key(item)))
                normal_id, char_id = unit.get("normal_chess_id"), unit.get("primary_char_id")
                if not normal_id or not char_id or not char_id.startswith("char_"):
                    continue
                entries[normal_id] = {
                    "id": normal_id,
                    "char_id": char_id,
                    "name": unit.get("name"),
                    "tier": unit.get("tier"),
                }
            if entries or not ids:
                operators = sorted(entries.values(), key=lambda unit: (unit["tier"] or 0, unit["id"]))
        rule = _ACTIVATION_RULES.get(_key(row.get("activeConditionTemplate")))
        bonds[key] = {
            "name": _label(row.get("name")),
            "description": _description(row.get("desc")),
            "icon_url": _icon(f"{_ICONS}/bond_icon/{key}.png"),
            "is_core": _flag(meta.get("isPower")),
            "operators": operators,
            "show_operators": show_operators,
            "activation_count": _number(row.get("activeCount")) if rule else None,
            "activation_rule": rule,
        }
    traits = {}
    for key, entry in _obj(content.get("garrisonDataDict")).items():
        if not _key(key):
            continue
        entry = _obj(entry)
        icon = _key(entry.get("eventTypeSmallIcon"))
        traits[key] = {
            "name": _label(entry.get("eventTypeDesc")),
            "description": _description(entry.get("description")) or _description(entry.get("garrisonDesc")),
            "icon_url": _icon(f"{_ICONS}/garrison_icon/{icon}.png") if icon else None,
        }
    bosses = {}
    boss_meta = _obj(shared.get("bossInfoDict"))
    for key in _obj(content.get("bossInfoDict")):
        meta = _obj(boss_meta.get(key))
        if _key(key) and (enemy := _key(meta.get("enemyId"))):
            name = _obj(enemies.get(enemy)).get("name") or _obj(enemies.get(meta.get("handbookEnemyId"))).get("name")
            bosses[key] = {"enemy_id": enemy, "name": _label(name)}
    titles = {
        key: {"name": name}
        for key, row in _obj(content.get("playerTitleDataDict")).items()
        if _key(key) and (name := _label(_obj(row).get("txt")))
    }
    char_ids = set()
    module_ids = set()
    for shop in map(_obj, chess.values()):
        char_ids.update(filter(None, (_key(shop.get("charId")), _key(shop.get("backupCharId")))))
        module_ids.update(filter(None, (_key(shop.get("defaultUniEquipId")), _key(shop.get("backupCharUniEquipId")))))
    skill_ids = {
        key
        for char_id in char_ids
        for skill in list_values(_obj(characters.get(char_id)).get("skills"))
        if (key := _key(_obj(skill).get("skillId")))
    }
    # Select exact references for this release, including substitutes. Do not attach one to a view unless its ID was recorded.
    skill_entries = {key: skill_reference(_obj(skills.get(key))) for key in sorted(skill_ids & skills.keys())}
    module_entries = {
        key: module_reference(_obj(modules.get(key)), _obj(effects.get(key)))
        for key in sorted(module_ids & modules.keys())
    }
    return {
        group: entries
        for group, entries in (
            ("strategy", strategies),
            ("bond", bonds),
            ("operator", units),
            ("trait", traits),
            ("boss_display", bosses),
            ("title_display", titles),
            ("skill", {key: entry for key, entry in skill_entries.items() if entry}),
            ("module", {key: entry for key, entry in module_entries.items() if entry}),
        )
        if entries
    }


def _optional_game_table(path: str) -> dict:
    try:
        return _obj(json.loads(read_repo_text(REPO_ARKNIGHTS, path)))
    except (OSError, RepoError, ValueError):
        return {}


def discover_activity_versions() -> list[tuple[str, str, dict, dict]]:
    data = _obj(json.loads(read_repo_text(REPO_ARKNIGHTS, "gamedata/excel/activity_table.json")))
    shared = _obj(data.get("autoChessData"))
    versions = _obj(shared.get("versionInfoDict"))
    activities = _obj(_obj(data.get("activity")).get("AUTOCHESS"))
    if not activities:
        return []
    characters = _optional_game_table(CHARACTER_TABLE_REL)
    skills = _optional_game_table("gamedata/excel/skill_table.json")
    modules = _obj(_optional_game_table("gamedata/excel/uniequip_table.json").get("equipDict"))
    effects = _optional_game_table("gamedata/excel/battle_equip_table.json")
    enemies = _obj(_optional_game_table("gamedata/excel/enemy_handbook_table.json").get("enemyData"))
    entries = []
    for entry in versions.values():
        entry = _obj(entry)
        activity = _scope(entry.get("activityId"))
        version = _key(entry.get("versionId"))
        if activity and version:
            content = _obj(_obj(activities.get(activity)).get(version))
            entries.append(
                (
                    activity,
                    version,
                    entry,
                    _game_catalog(shared, content, characters, skills, modules, effects, enemies),
                )
            )
    return entries


def resource_time(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    try:
        text = str(value)
        if text.isascii() and text.isdigit() and 9 <= len(text) <= 10:
            return to_naive(datetime.fromtimestamp(int(text), tz=timezone.utc))
        return to_naive(datetime.fromisoformat(text)) if len(text) >= 10 else None
    except (ValueError, OSError, OverflowError):
        return None


def ensure_version(db: Session, activity: str, version: str, metadata: dict | None = None) -> StrongholdVersion:
    row = db.get(StrongholdVersion, (activity, version))
    if row is None:
        row = StrongholdVersion(season_id=activity, version_id=version, label=version, catalog={}, assets={})
        db.add(row)
        db.flush()
    meta = metadata or {}
    if label := _label(meta.get("seasonName")):
        row.label = label
    if starts := resource_time(meta.get("startTime")):
        row.starts_at = starts
    if ends := resource_time(meta.get("endTime")):
        row.ends_at = ends
    return row


def _display_entry(row: dict, *, trait: bool = False) -> dict:
    if trait:
        return {
            "name": _label(row.get("eventTypeDesc")),
            "description": _description(row.get("description")),
            "icon_url": _icon(row.get("icon"))
            or _icon(row.get("eventTypeSmallIcon"))
            or _icon(row.get("eventTypeIcon")),
        }
    return {
        "name": _label(row.get("name")),
        "description": _description(row.get("desc")),
        "icon_url": _icon(row.get("icon")),
    }


def save_game_catalog(row: StrongholdVersion, catalog: dict, now: datetime) -> None:
    if not catalog:
        return
    previous = row.catalog.get("game", {})
    frozen = row.ends_at is not None and row.ends_at <= now

    # Keep already archived fields, but allow a parser upgrade or optional table to fill gaps in the same version.
    def merge(old: dict, new: dict) -> dict:
        combined = dict(old)
        for key, value in new.items():
            if isinstance(value, dict) and isinstance(prior := combined.get(key), dict):
                combined[key] = merge(prior, value)
            elif value is not None or key not in combined:
                combined[key] = value
        return combined

    if frozen:
        # Do not append new members to established version groups; backfill fields on their existing IDs.
        merged = dict(previous)
        for group, entries in catalog.items():
            if old := previous.get(group):
                merged[group] = {key: merge(entries.get(key, {}), entry) for key, entry in old.items()}
            else:
                merged[group] = entries
    else:
        merged = merge(previous, catalog)
    if merged != previous:
        row.catalog = {**row.catalog, "game": merged}


def _catalog_entry(catalog: dict, group: str, key: str) -> dict:
    game = catalog.get("game", {}).get(group, {}).get(key, {})
    official = catalog.get(group, {}).get(key, {})
    entry = {**game, **official}
    # The strategy headline and the name of its promoter are different fields in the game table.
    if group == "strategy" and game.get("name"):
        entry["name"] = game["name"]
    return {field: value for field, value in entry.items() if value is not None}


def _catalog_entries(catalog: dict, group: str) -> dict:
    game = catalog.get("game", {}).get(group, {})
    official = catalog.get(group, {})
    return {key: _catalog_entry(catalog, group, key) for key in dict.fromkeys((*official, *game))}


def save_resources(db: Session, activity: str, versions: dict[str, dict], now: datetime) -> None:
    for version, raw in versions.items():
        meta = _obj(raw.get("versionInfo"))
        if _scope(meta.get("activityId")) not in (None, activity):
            continue
        row = ensure_version(db, activity, version)
        if any(key != "game" for key in row.catalog) and row.ends_at is not None and row.ends_at <= now:
            continue
        row = ensure_version(db, activity, version, meta)
        catalog = dict(row.catalog)
        for field, group in (
            ("bandInfo", "strategy"),
            ("bondInfo", "bond"),
            ("equipInfo", "equipment"),
            ("garrisonInfo", "trait"),
        ):
            items = dict(catalog.get(group, {}))
            for item_id, value in list(_obj(raw.get(field)).items())[:4096]:
                if not _key(item_id) or not isinstance(value, dict):
                    continue
                entry = _display_entry(value, trait=group == "trait")
                if group == "equipment":
                    entry["tier"] = _number(value.get("itemLevel"))
                items[item_id] = {**items.get(item_id, {}), **{k: v for k, v in entry.items() if v is not None}}
            catalog[group] = items
        for field, group, attribute, validator in (
            ("bossInfo", "boss", "enemyId", _key),
            ("titleInfo", "title", "name", _label),
        ):
            items = dict(catalog.get(group, {}))
            for item_id, value in list(_obj(raw.get(field)).items())[:4096]:
                if _key(item_id) and (result := validator(_obj(value).get(attribute))):
                    items[item_id] = result
            catalog[group] = items
        chess = dict(catalog.get("chess", {}))
        for item_id, value in list(_obj(raw.get("chessInfo")).items())[:4096]:
            if not _key(item_id) or not isinstance(value, dict):
                continue
            fields = {name: _key(value.get(name)) for name in ("charId", "charProfession")}
            fields.update({name: _number(value.get(name)) for name in ("charLevel", "evolvePhase", "chessLevel")})
            fields["charName"] = _label(value.get("charName"))
            if isinstance(traits := value.get("garrisonIds"), list):
                fields["garrisonIds"] = [key for item in traits[:16] if (key := _key(item))]
            chess[item_id] = {**chess.get(item_id, {}), **{k: v for k, v in fields.items() if v is not None}}
        catalog["chess"] = chess
        banner = raw.get("banner")
        banner_url = _icon(banner) or _icon(_obj(banner).get("imageUrl")) or _icon(_obj(banner).get("url"))
        if banner_url:
            catalog["banner_url"] = banner_url
        if not catalog.get("emblem_url"):
            catalog["emblem_url"] = next(
                (
                    catalog["bond"][key]["icon_url"]
                    for key in sorted(catalog.get("bond", {}))
                    if catalog["bond"][key].get("icon_url")
                ),
                None,
            )
        row.catalog = catalog
        # CDN failures get another attempt at the next successful catalog refresh.
        row.assets = {url: digest for url, digest in row.assets.items() if digest}


def cached_source_versions(db: Session, activity: str) -> dict[str, dict]:
    result = {}
    for version in db.scalars(select(StrongholdVersion).where(StrongholdVersion.season_id == activity)):
        catalog = version.catalog
        if not catalog:
            continue
        payload = {
            "versionInfo": {"activityId": activity, "seasonName": version.label},
            "chessInfo": catalog.get("chess", {}),
        }
        for group, field in (("strategy", "bandInfo"), ("bond", "bondInfo"), ("equipment", "equipInfo")):
            payload[field] = {
                key: {
                    "name": value.get("name"),
                    "desc": value.get("description"),
                    "icon": value.get("icon_url"),
                    "itemLevel": value.get("tier"),
                }
                for key, value in _catalog_entries(catalog, group).items()
            }
        payload["garrisonInfo"] = {
            key: {
                "eventTypeDesc": value.get("name"),
                "description": value.get("description"),
                "eventTypeSmallIcon": value.get("icon_url"),
            }
            for key, value in _catalog_entries(catalog, "trait").items()
        }
        payload["bossInfo"] = {
            **{
                key: {"enemyId": value.get("enemy_id")}
                for key, value in _catalog_entries(catalog, "boss_display").items()
            },
            **{key: {"enemyId": value} for key, value in catalog.get("boss", {}).items()},
        }
        payload["titleInfo"] = {
            **{key: {"name": value.get("name")} for key, value in _catalog_entries(catalog, "title_display").items()},
            **{key: {"name": value} for key, value in catalog.get("title", {}).items()},
        }
        result[version.version_id] = payload
    return result


def _asset_dir() -> Path:
    return resolve_install_dir() / "data" / "runtime" / "stronghold" / "assets"


def archive_path(digest: str) -> Path:
    return _asset_dir() / digest[:2] / digest


def archived_content_type(path: Path) -> str | None:
    try:
        with path.open("rb") as image:
            signature = image.read(12)
    except (FileNotFoundError, IsADirectoryError):
        return None
    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if signature.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
        return "image/webp"
    return None


def _archive_image(url: str) -> str | None:
    if not _icon(url):
        return None
    try:
        response = http_request("GET", url, timeout=4, deadline=5, max_bytes=_ASSET_BYTES, follow_redirects=False)
        if response.status_code != 200:
            return None
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        with Image.open(BytesIO(response.content)) as image:
            if _ASSET_TYPES.get(image.format) != content_type or image.width * image.height > _ASSET_PIXELS:
                return None
            image.verify()
        digest = sha256(response.content).hexdigest()
        path = archive_path(digest)
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as target:
                temporary = Path(target.name)
                target.write(response.content)
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        return digest
    except (HttpRequestError, UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        return None


def archive_assets(db: Session, limit: int = 4, deadline: float | None = None) -> int:
    pending = []
    for version in db.scalars(select(StrongholdVersion).order_by(StrongholdVersion.starts_at.desc())):
        urls = dict.fromkeys((version.catalog.get("banner_url"), version.catalog.get("emblem_url")))
        for group in ("strategy", "bond", "equipment", "trait", "module"):
            urls.update(
                dict.fromkeys(item.get("icon_url") for item in _catalog_entries(version.catalog, group).values())
            )
        pending.extend(
            (version.season_id, version.version_id, url) for url in urls if url and url not in version.assets
        )
        if len(pending) >= limit:
            break
    db.commit()
    completed = 0
    for activity, version_id, url in pending[:limit]:
        if deadline is not None and time.monotonic() >= deadline:
            break
        digest = _archive_image(url)
        version = db.get(StrongholdVersion, (activity, version_id))
        if version is not None:
            version.assets = {**version.assets, url: digest}
        db.commit()
        completed += 1
    return completed


def display_url(version: StrongholdVersion | None, url: str | None) -> str | None:
    if url and version and (digest := version.assets.get(url)) and archive_path(digest).is_file():
        return f"/api/skland/arknights/stronghold/assets/{digest}"
    return url


def version_out(version: StrongholdVersion, last_played: datetime | None = None) -> StrongholdVersionOut:
    return StrongholdVersionOut(
        key=version_key(version.season_id, version.version_id),
        label=version.label,
        banner_url=display_url(version, version.catalog.get("banner_url")),
        emblem_url=display_url(version, version.catalog.get("emblem_url")),
        last_played_date=to_naive(last_played).date() if last_played else None,
    )


def display_entry(version: StrongholdVersion | None, group: str, key: str | None) -> dict:
    if version is None or key is None:
        return {}
    entry = _catalog_entry(version.catalog, group, key)
    if url := entry.get("icon_url"):
        entry["icon_url"] = display_url(version, url)
    return entry


def operator_effect(
    version: StrongholdVersion | None, group: str, effect_id: str | None, level: int | None
) -> dict | None:
    if not (entry := display_entry(version, group, effect_id)):
        return None
    levels = entry.get("levels", {})
    # Without a verified configured level, fallback text is explicitly marked level 1, not a claim about the battle.
    ref = level if str(level) in levels else 1 if not level and "1" in levels else None
    return {
        "name": entry.get("name"),
        "description": levels.get(str(ref)),
        "icon_url": entry.get("icon_url"),
        "config_level": level,
        "reference_level": ref,
    }
