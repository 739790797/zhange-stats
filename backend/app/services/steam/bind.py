"""Steam 账号绑定：解析标识、拉取资料并校验公开状态。"""

from __future__ import annotations

from dataclasses import asdict

from app.services.adapters.steam import SteamAdapter, SteamPlayerProfile
from app.services.steam.resolve import resolve_steam_input

PRIVACY_HINT = (
    "请在 Steam → 个人资料 → 编辑个人资料 → 隐私设置 中，"
    "将「我的个人资料」设为公开，并将「游戏详情」设为公开后重试"
)


def lookup_steam_profile(raw_input: str) -> SteamPlayerProfile:
    from app.services.integrations_config import get_steam_api_key

    api_key = get_steam_api_key()
    if not api_key:
        raise RuntimeError("未配置 STEAM_API_KEY，无法验证 Steam 账号")

    steam_id = resolve_steam_input(raw_input, api_key)
    adapter = SteamAdapter(api_key)
    return adapter.fetch_player_profile(steam_id)


def require_public_steam_profile(raw_input: str) -> SteamPlayerProfile:
    profile = lookup_steam_profile(raw_input)
    if not profile.is_public:
        raise ValueError(
            "该 Steam 个人资料未公开，无法获取游戏与在线信息。" + PRIVACY_HINT
        )
    return profile


def steam_profile_public_dict(profile: SteamPlayerProfile) -> dict:
    data = asdict(profile)
    data["is_public"] = profile.is_public
    data["privacy_label"] = (
        "公开" if profile.is_public else "未公开（私密或仅好友可见）"
    )
    return data
