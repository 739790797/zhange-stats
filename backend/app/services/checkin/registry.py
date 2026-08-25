"""签到平台 Adapter 注册表。"""

from __future__ import annotations

from app.services.checkin.adapter import CheckinPlatformAdapter
from app.services.checkin.role_prefs import (
    PLATFORM_EXILIUM,
    PLATFORM_KUJIEQU,
    PLATFORM_MIHOYO,
    PLATFORM_SKLAND,
    PLATFORM_TAYGEDO,
)


def _load_adapters() -> dict[str, CheckinPlatformAdapter]:
    # 延迟导入，避免环依赖（各 *_checkin 已依赖 orchestrator）
    from app.services.exilium.checkin import exilium_adapter
    from app.services.kujiequ.checkin import kujiequ_adapter
    from app.services.mihoyo.checkin import mihoyo_adapter
    from app.services.skland.checkin import skland_adapter
    from app.services.taygedo.checkin import taygedo_adapter

    return {
        PLATFORM_SKLAND: skland_adapter,
        PLATFORM_TAYGEDO: taygedo_adapter,
        PLATFORM_EXILIUM: exilium_adapter,
        PLATFORM_KUJIEQU: kujiequ_adapter,
        PLATFORM_MIHOYO: mihoyo_adapter,
    }


ADAPTERS: dict[str, CheckinPlatformAdapter] | None = None


def get_checkin_adapters() -> dict[str, CheckinPlatformAdapter]:
    global ADAPTERS
    if ADAPTERS is None:
        ADAPTERS = _load_adapters()
    return ADAPTERS


def get_checkin_adapter(platform: str) -> CheckinPlatformAdapter:
    adapters = get_checkin_adapters()
    try:
        return adapters[platform]
    except KeyError as exc:
        raise KeyError(f"未知签到平台: {platform}") from exc
