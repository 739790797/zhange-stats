"""从 jar 文件名检索 Modrinth / MCMOD，给总览模组行用。"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.core.ephemeral_kv import ephemeral_get, ephemeral_set
from app.services.minecraft.modrinth import MODRINTH_API, USER_AGENT, ModrinthError, _get_json

logger = logging.getLogger(__name__)

MCMOD_SEARCH = "https://mcmod-api.zkitefly.eu.org/s/key="
MCMOD_CLASS = "https://mcmod-api.zkitefly.eu.org/d/class/"
CATALOG_TTL_SEC = 6 * 3600
_HTTP_TIMEOUT = 4.0

_LOADER_TOKENS = {
    "fabric",
    "forge",
    "neoforge",
    "quilt",
    "bukkit",
    "spigot",
    "paper",
    "mc",
}
_MC_VER = re.compile(r"(?:mc)?1\.\d{1,2}(?:\.\d{1,2})?", re.I)
_VERSION = re.compile(r"v?\d+\.\d+(?:\.\d+)?(?:-[a-z]+\d*)?", re.I)
_CJK = re.compile(r"[\u4e00-\u9fff]")


def jar_stem(filename: str) -> str:
    name = str(filename or "").strip()
    if name.lower().endswith(".jar"):
        return name[:-4]
    return name


def query_from_jar(filename: str) -> str:
    stem = jar_stem(filename)
    parts = re.split(r"[-_+ ]+", stem)
    kept: list[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        lower = token.lower()
        if lower in _LOADER_TOKENS:
            continue
        if _MC_VER.fullmatch(token):
            continue
        if kept and _VERSION.fullmatch(token):
            continue
        kept.append(token)
    return " ".join(kept) or stem


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (text or "").lower())


def pick_modrinth_hit(hits: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    wanted = _norm(query)
    mods = [row for row in hits if isinstance(row, dict) and row.get("project_type") == "mod"]
    if not mods:
        mods = [row for row in hits if isinstance(row, dict)]
    if not mods:
        return None
    if wanted:
        for row in mods:
            slug = _norm(str(row.get("slug") or ""))
            title = _norm(str(row.get("title") or ""))
            if wanted == slug or wanted == title:
                return row
        for row in mods:
            slug = _norm(str(row.get("slug") or ""))
            title = _norm(str(row.get("title") or ""))
            if wanted in slug or wanted in title or slug in wanted or title in wanted:
                return row
    return mods[0]


def pick_curseforge_url(links: list[Any]) -> str:
    urls: list[str] = []
    for item in links:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if "curseforge.com" not in url.lower():
            continue
        urls.append(url)
    for url in urls:
        if "/minecraft/mc-mods/" in url.lower():
            return url
    for url in urls:
        lower = url.lower()
        if "/bukkit-plugins/" in lower or "/texture-packs/" in lower:
            continue
        return url
    return urls[0] if urls else ""


def pick_modrinth_mod_url(links: list[Any]) -> str:
    for item in links:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if re.search(r"modrinth\.com/mod/", url, re.I):
            return url
    return ""


def mcmod_class_id(row: dict[str, Any]) -> str:
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    mid = str(data.get("mcmod_id") or "").strip()
    if mid.isdigit():
        return mid
    match = re.search(r"/class/(\d+)", str(row.get("address") or ""))
    return match.group(1) if match else ""


def pick_mcmod_hit(rows: list[Any], query: str) -> dict[str, Any] | None:
    classes: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        address = str(row.get("address") or "")
        if "/class/" not in address:
            continue
        classes.append(row)
    if not classes:
        return None
    wanted = _norm(query)
    if wanted:
        for row in classes:
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            names = [
                str(row.get("title") or ""),
                str(data.get("chinese_name") or ""),
                str(data.get("sub_name") or ""),
                str(data.get("abbr") or ""),
            ]
            if any(wanted == _norm(name) or wanted in _norm(name) for name in names if name):
                return row
    return classes[0]


def _http_json(url: str, *, timeout: float = _HTTP_TIMEOUT) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _search_modrinth(query: str) -> dict[str, Any] | None:
    q = (query or "").strip()
    if not q:
        return None
    params = {
        "query": q,
        "limit": "8",
        "facets": json.dumps([["project_type:mod"]], ensure_ascii=False),
    }
    url = f"{MODRINTH_API}/search?{urllib.parse.urlencode(params)}"
    try:
        data = _get_json(url, timeout=_HTTP_TIMEOUT)
    except ModrinthError:
        return None
    hits = data.get("hits") if isinstance(data, dict) else None
    if not isinstance(hits, list):
        return None
    return pick_modrinth_hit(hits, q)


def _search_mcmod(query: str) -> dict[str, Any] | None:
    q = (query or "").strip()
    if not q:
        return None
    url = MCMOD_SEARCH + urllib.parse.quote(q, safe="")
    try:
        data = _http_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, list):
        return None
    return pick_mcmod_hit(data, q)


def _fetch_mcmod_class(mcmod_id: str) -> dict[str, Any] | None:
    mid = (mcmod_id or "").strip()
    if not mid.isdigit():
        return None
    try:
        data = _http_json(MCMOD_CLASS + mid)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _empty_catalog(filename: str, *, version_number: str = "", project_title: str = "") -> dict[str, Any]:
    return {
        "filename": filename,
        "version_number": version_number,
        "project_id": "",
        "slug": "",
        "title": project_title,
        "title_zh": "",
        "icon_url": "",
        "summary": "",
        "downloads": None,
        "environment": "",
        "modrinth_url": "",
        "curseforge_url": "",
        "mcmod_url": "",
    }


def _apply_mcmod_search(out: dict[str, Any], mcmod: dict[str, Any]) -> None:
    address = str(mcmod.get("address") or "")
    data = mcmod.get("data") if isinstance(mcmod.get("data"), dict) else {}
    zh = str(data.get("chinese_name") or "")
    sub = str(data.get("sub_name") or "")
    if _CJK.search(zh):
        out["title_zh"] = zh
    elif _CJK.search(str(mcmod.get("title") or "")):
        out["title_zh"] = str(mcmod.get("title") or "")
    if not out["title"] and sub:
        out["title"] = sub
    if address.startswith("https://www.mcmod.cn/class/"):
        out["mcmod_url"] = address


def _apply_mcmod_detail(out: dict[str, Any], detail: dict[str, Any]) -> None:
    env = str(detail.get("operating_environment") or "").strip()
    if env:
        out["environment"] = env
    links = detail.get("related_links") if isinstance(detail.get("related_links"), list) else []
    curseforge = pick_curseforge_url(links)
    if curseforge:
        out["curseforge_url"] = curseforge
    modrinth = pick_modrinth_mod_url(links)
    if modrinth and not out["modrinth_url"]:
        out["modrinth_url"] = modrinth
    zh_title = str(detail.get("title") or "")
    if _CJK.search(zh_title) and not out["title_zh"]:
        out["title_zh"] = zh_title
    subtitle = str(detail.get("subtitle") or "").strip()
    if subtitle and not out["title"]:
        out["title"] = subtitle


def lookup_mod_catalog(
    filename: str,
    *,
    version_number: str = "",
    project_title: str = "",
    project_id: str = "",
    slug: str = "",
) -> dict[str, Any]:
    out = _empty_catalog(filename, version_number=version_number, project_title=project_title)
    query = query_from_jar(filename) or project_title
    hit: dict[str, Any] | None = None
    if project_id:
        try:
            proj = _get_json(
                f"{MODRINTH_API}/project/{urllib.parse.quote(project_id)}",
                timeout=_HTTP_TIMEOUT,
            )
            if isinstance(proj, dict):
                hit = proj
                hit["project_id"] = str(proj.get("id") or project_id)
        except ModrinthError:
            hit = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_mr = None if hit is not None else pool.submit(_search_modrinth, query)
        fut_mc = pool.submit(_search_mcmod, query)
        if fut_mr is not None:
            found = fut_mr.result()
            if isinstance(found, dict):
                hit = found
        mcmod = fut_mc.result()
    if isinstance(hit, dict):
        pid = str(hit.get("project_id") or hit.get("id") or "")
        slug_val = str(hit.get("slug") or slug or "")
        title = str(hit.get("title") or project_title or "")
        out["project_id"] = pid
        out["slug"] = slug_val
        out["title"] = title
        out["icon_url"] = str(hit.get("icon_url") or "")
        out["summary"] = str(hit.get("description") or "")
        downloads = hit.get("downloads")
        if isinstance(downloads, bool):
            out["downloads"] = None
        elif isinstance(downloads, int):
            out["downloads"] = downloads
        elif isinstance(downloads, float) and downloads.is_integer():
            out["downloads"] = int(downloads)
        else:
            out["downloads"] = None
        if slug_val:
            out["modrinth_url"] = f"https://modrinth.com/mod/{urllib.parse.quote(slug_val)}"
    if not isinstance(mcmod, dict) and out["title"] and out["title"] != query:
        mcmod = _search_mcmod(out["title"])
    if isinstance(mcmod, dict):
        _apply_mcmod_search(out, mcmod)
        detail = _fetch_mcmod_class(mcmod_class_id(mcmod))
        if isinstance(detail, dict):
            _apply_mcmod_detail(out, detail)
    if not out["title"]:
        out["title"] = project_title
    return out


def _cache_key(filename: str) -> str:
    return f"minecraft:modcat:v2:{filename}"


def enrich_overview_mod(row: dict[str, Any]) -> dict[str, Any]:
    filename = str(row.get("filename") or "")
    version_number = str(row.get("version_number") or "")
    project_title = str(row.get("project_title") or "")
    base = _empty_catalog(filename, version_number=version_number, project_title=project_title)
    if not filename:
        return base
    cached = ephemeral_get(_cache_key(filename))
    if cached:
        try:
            parsed = json.loads(cached)
            if isinstance(parsed, dict):
                parsed["filename"] = filename
                parsed["version_number"] = version_number or str(parsed.get("version_number") or "")
                return parsed
        except json.JSONDecodeError:
            pass
    try:
        catalog = lookup_mod_catalog(
            filename,
            version_number=version_number,
            project_title=project_title,
            project_id=str(row.get("project_id") or ""),
            slug=str(row.get("slug") or ""),
        )
    except Exception:
        logger.exception("minecraft mod catalog failed for %s", filename)
        catalog = base
    ephemeral_set(_cache_key(filename), json.dumps(catalog, ensure_ascii=False), ttl_sec=CATALOG_TTL_SEC)
    return catalog


def enrich_overview_mods(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    workers = min(8, len(rows))
    if workers == 1:
        return [enrich_overview_mod(rows[0])]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(enrich_overview_mod, rows))
