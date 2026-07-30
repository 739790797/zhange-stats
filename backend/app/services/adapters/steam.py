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
