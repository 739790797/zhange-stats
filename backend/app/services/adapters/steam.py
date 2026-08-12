"""Steam Web API 适配器：拉取玩家当前在线/游玩状态。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.services.adapters import BaseGameAdapter


@dataclass
class SteamPresence:
    steam_id: str
    persona_name: str | None
    persona_state: int | None
    game_id: str | None
    game_extra_info: str | None
    avatar_url: str | None = None

    @property
    def is_playing(self) -> bool:
        return bool(self.game_id)

    @property
    def status(self) -> str:
        """归一化为 offline / online / playing。"""
        if self.game_id:
            return "playing"
        if self.persona_state is None or self.persona_state == 0:
            return "offline"
        return "online"


@dataclass
class SteamPlayerProfile:
    steam_id: str
    persona_name: str | None
    avatar_url: str | None
    profile_url: str | None
    community_visibility_state: int | None
    persona_state: int | None

    @property
    def is_public(self) -> bool:
        # 3 = Public；私密/仅好友无法稳定拉取游戏详情与统计
        return self.community_visibility_state == 3


class SteamAdapter(BaseGameAdapter):
    game_key = "steam"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def fetch_raw(self, external_id: str) -> Any:
        return self.fetch_summaries([external_id])

    def parse(self, raw: Any) -> list[dict[str, Any]]:
        """通用解析接口；Presence 轮询使用 parse_presences。"""
        return []

    def fetch_summaries(self, steam_ids: list[str]) -> dict[str, Any]:
        if not steam_ids:
            return {"response": {"players": []}}
        if not self.api_key:
            raise RuntimeError("STEAM_API_KEY 未配置")

        params = urllib.parse.urlencode(
            {
                "key": self.api_key,
                "steamids": ",".join(steam_ids),
            }
        )
        url = (
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
            f"?{params}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "zhange-stats/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Steam API HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Steam API 网络错误: {exc}") from exc

    def fetch_player_profile(self, steam_id: str) -> SteamPlayerProfile:
        raw = self.fetch_summaries([steam_id])
        players = (raw or {}).get("response", {}).get("players") or []
        if not players:
            raise ValueError("未找到该 Steam 账号")
        p = players[0]
        visibility = p.get("communityvisibilitystate")
        return SteamPlayerProfile(
            steam_id=str(p.get("steamid") or steam_id),
            persona_name=p.get("personaname"),
            avatar_url=p.get("avatarfull") or p.get("avatarmedium") or p.get("avatar"),
            profile_url=p.get("profileurl"),
            community_visibility_state=int(visibility)
            if visibility is not None
            else None,
            persona_state=int(p["personastate"])
            if p.get("personastate") is not None
            else None,
        )

    def fetch_owned_game_icons(self, steam_id: str) -> dict[str, str]:
        """拉取用户库游戏的客户端小图标（库列表名左侧那枚）。

        返回 app_id → 完整 CDN URL。资料未公开或无库时返回空 dict。
        """
        if not self.api_key:
            raise RuntimeError("STEAM_API_KEY 未配置")
        params = urllib.parse.urlencode(
            {
                "key": self.api_key,
                "steamid": steam_id,
                "include_appinfo": 1,
                "include_played_free_games": 1,
                "format": "json",
            }
        )
        url = (
            "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
            f"?{params}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "zhange-stats/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                return {}
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Steam GetOwnedGames HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Steam GetOwnedGames 网络错误: {exc}") from exc

        games = (raw or {}).get("response", {}).get("games") or []
        result: dict[str, str] = {}
        for g in games:
            app_id = str(g.get("appid") or "").strip()
            icon_hash = str(g.get("img_icon_url") or "").strip()
            if not app_id or not icon_hash:
                continue
            result[app_id] = (
                "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/"
                f"{app_id}/{icon_hash}.jpg"
            )
        return result

    def parse_presences(self, raw: dict[str, Any]) -> list[SteamPresence]:
        players = (raw or {}).get("response", {}).get("players", []) or []
        result: list[SteamPresence] = []
        for p in players:
            game_id = p.get("gameid")
            result.append(
                SteamPresence(
                    steam_id=str(p.get("steamid", "")),
                    persona_name=p.get("personaname"),
                    persona_state=int(p["personastate"])
                    if p.get("personastate") is not None
                    else None,
                    game_id=str(game_id) if game_id else None,
                    game_extra_info=p.get("gameextrainfo"),
                    avatar_url=p.get("avatarfull")
                    or p.get("avatarmedium")
                    or p.get("avatar"),
                )
            )
        return result

    def fetch_user_stats(self, steam_id: str, app_id: int = 730) -> dict[str, Any]:
        """拉取指定游戏的 Steam 生涯统计（需资料公开）。"""
        if not self.api_key:
            raise RuntimeError("STEAM_API_KEY 未配置")
        params = urllib.parse.urlencode(
            {
                "key": self.api_key,
                "steamid": steam_id,
                "appid": app_id,
            }
        )
        url = (
            "https://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v2/"
            f"?{params}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "zhange-stats/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Steam Stats HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Steam Stats 网络错误: {exc}") from exc

    @staticmethod
    def stats_to_map(raw: dict[str, Any]) -> dict[str, int]:
        stats = (raw or {}).get("playerstats", {}).get("stats") or []
        result: dict[str, int] = {}
        for item in stats:
            name = item.get("name")
            if not name:
                continue
            try:
                result[str(name)] = int(item.get("value") or 0)
            except (TypeError, ValueError):
                continue
        return result
