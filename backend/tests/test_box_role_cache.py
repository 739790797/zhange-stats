"""box_role_cache：从 raw 表还原角色列表。"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.box_role_cache import skland_endfield_roles_from_raws
from app.services.skland.client import GAME_ENDFIELD


def test_skland_endfield_roles_from_raws() -> None:
    row = SimpleNamespace(
        uid="u1",
        role_id="r1",
        server_id="s1",
    )
    db = SimpleNamespace(
        query=lambda _model: SimpleNamespace(
            filter=lambda *args, **kwargs: SimpleNamespace(
                order_by=lambda *_a: SimpleNamespace(all=lambda: [row])
            )
        )
    )
    roles = skland_endfield_roles_from_raws(db, 1)  # type: ignore[arg-type]
    assert roles is not None
    assert len(roles) == 1
    assert roles[0].game_code == GAME_ENDFIELD
    assert roles[0].role_id == "r1"
