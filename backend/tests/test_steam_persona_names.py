"""Steam 昵称当成员昵称展示：存与显示都去掉尖括号。"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.adapters.steam import SteamAdapter, clean_persona_name
from app.services.steam.display import (
    apply_steam_profile,
    force_set_steam_persona_name,
    format_steam_display_name,
    member_steam_presentation,
)


def _member(name: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=7, user=None, steam_persona_name=name, steam_avatar_url=None
    )


def test_apply_steam_profile_stores_names_without_angle_brackets() -> None:
    member = _member()

    assert apply_steam_profile(member, persona_name=" <b>Gabe</b> ") is True
    assert member.steam_persona_name == "bGabe/b"
    assert apply_steam_profile(member, persona_name="<b>Gabe</b>") is False


def test_apply_steam_profile_ignores_names_that_are_only_markup() -> None:
    member = _member("Old")

    assert apply_steam_profile(member, persona_name="<<>>") is False
    assert member.steam_persona_name == "Old"


def test_force_set_persona_strips_or_clears() -> None:
    member = _member()
    force_set_steam_persona_name(member, "<img src=x>", user=SimpleNamespace())
    assert member.steam_persona_name == "img src=x"

    force_set_steam_persona_name(member, "<>", user=SimpleNamespace())
    assert member.steam_persona_name is None


def test_legacy_stored_names_are_cleaned_on_display() -> None:
    member = _member("<script>x</script>")

    assert format_steam_display_name(member) == "scriptx/script"
    out = member_steam_presentation(member)
    assert out["member_nickname"] == "scriptx/script"
    assert out["steam_persona_name"] == "scriptx/script"
    assert format_steam_display_name(_member("<>"), fallback="m7") == "m7"


def test_adapter_cleans_persona_names() -> None:
    raw = {
        "response": {
            "players": [
                {"steamid": "1", "personaname": "<Pro>", "personastate": 1},
                {"steamid": "2", "personaname": "<>", "personastate": "bad"},
                "junk",
            ]
        }
    }

    presences = SteamAdapter("key").parse_presences(raw)

    assert [(p.steam_id, p.persona_name, p.persona_state) for p in presences] == [
        ("1", "Pro", 1),
        ("2", None, None),
    ]
    assert clean_persona_name(None) is None
    assert SteamAdapter("key").parse_presences({"response": []}) == []


def test_player_profile_persona_is_cleaned(monkeypatch) -> None:
    adapter = SteamAdapter("key")
    monkeypatch.setattr(
        adapter,
        "fetch_summaries",
        lambda ids: {
            "response": {
                "players": [
                    {"steamid": ids[0], "personaname": "a<b>c", "communityvisibilitystate": 3}
                ]
            }
        },
    )

    profile = adapter.fetch_player_profile("76561198000000001")

    assert profile.persona_name == "abc"
    assert profile.is_public is True
