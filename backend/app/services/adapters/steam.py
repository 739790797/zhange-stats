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

    def fetch_friend_list(self, steam_id: str) -> list[dict[str, Any]]:
        """拉取好友列表。好友列表未公开时 Steam 返回 401，此时抛出 PermissionError。"""
        if not self.api_key:
            raise RuntimeError("STEAM_API_KEY 未配置")
        params = urllib.parse.urlencode(
            {
                "key": self.api_key,
                "steamid": steam_id,
                "relationship": "friend",
            }
        )
        url = (
            "https://api.steampowered.com/ISteamUser/GetFriendList/v1/"
            f"?{params}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "zhange-stats/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 401:
                raise PermissionError("Steam 好友列表未公开") from exc
            raise RuntimeError(f"Steam FriendList HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Steam FriendList 网络错误: {exc}") from exc

        friends = (raw or {}).get("friendslist", {}).get("friends") or []
        result: list[dict[str, Any]] = []
        for item in friends:
            sid = str(item.get("steamid") or "").strip()
            if not sid:
                continue
            since = item.get("friend_since")
            result.append(
                {
                    "steam_id": sid,
                    "friend_since": int(since) if since is not None else None,
                }
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
