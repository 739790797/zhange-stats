"""从 Pelican 启动项推断当前服加载器。"""

from __future__ import annotations

from typing import Any

from app.services.minecraft import pelican as pelican


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def infer_loader(blob: str) -> str:
    text = (blob or "").lower()
    if "neoforge" in text:
        return "neoforge"
    if "quilt" in text:
        return "quilt"
    if "fabric" in text:
        return "fabric"
    if "forge" in text:
        return "forge"
    return ""


def inspect_current_egg(base: str, token: str, uuid: str) -> dict[str, Any]:
    startup = pelican.get_startup(base, token, uuid)
    details = pelican.startup_details(startup)
    blob = _blob(
        details.get("command"),
        " ".join(details.get("docker_images") or []),
        " ".join(
            f"{row.get('key')}={row.get('value')}"
            for row in details.get("variables") or []
        ),
    )
    images = list(details.get("docker_images") or [])
    return {
        **details,
        "inferred_loader": infer_loader(blob),
        "egg_id": 0,
        "egg_name": "",
        "docker_image": images[0] if images else "",
    }
