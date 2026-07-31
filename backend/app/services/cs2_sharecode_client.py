"""CS2 对局分享码拉取：GetNextMatchSharingCode。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class Cs2ShareCodeClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def get_next_match_sharing_code(
        self, steam_id: str, auth_code: str, known_code: str
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("STEAM_API_KEY 未配置")
        params = urllib.parse.urlencode(
            {
                "key": self.api_key,
                "steamid": steam_id,
                "steamidkey": auth_code,
                "knowncode": known_code,
            }
        )
        url = (
            "https://api.steampowered.com/ICSGOPlayers_730/"
            f"GetNextMatchSharingCode/v1/?{params}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "zhange-stats/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"ShareCode API HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"ShareCode API 网络错误: {exc}") from exc

    @staticmethod
    def extract_next_code(payload: dict[str, Any]) -> str | None:
        """
        返回下一场分享码；无新对局时返回 None。
        Steam 在无更新时常返回 nextcode 为空或 result 非 1。
        """
        result = (payload or {}).get("result") or {}
        next_code = result.get("nextcode") or result.get("next_code")
        if not next_code:
            return None
        text = str(next_code).strip()
        if not text or text.upper() in {"N/A", "NULL", "NONE"}:
            return None
        return text
