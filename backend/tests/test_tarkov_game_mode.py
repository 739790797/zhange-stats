from app.services.tarkov.game_mode import (
    DEFAULT_GAME_MODE,
    cache_key,
    game_mode_scope,
    graphql_game_mode,
    json_api_prefix,
    json_resource_url,
    parse_game_mode,
    raw_row_id,
    run_for_modes,
    sync_modes,
)


def test_parse_game_mode_aliases():
    assert parse_game_mode("pve") == "pve"
    assert parse_game_mode("PVE") == "pve"
    assert parse_game_mode("pvp") == "pvp"
    assert parse_game_mode("regular") == "pvp"
    assert parse_game_mode("pmc") == "pvp"
    assert parse_game_mode("") == "pvp"
    assert parse_game_mode("nope") == DEFAULT_GAME_MODE


def test_row_id_and_upstream_mapping():
    assert raw_row_id("pvp") == 1
    assert raw_row_id("pve") == 2
    assert graphql_game_mode("pvp") == "regular"
    assert graphql_game_mode("pve") == "pve"
    assert json_api_prefix("pve") == "pve"
    assert json_resource_url("tasks", mode="pve") == "https://json.tarkov.dev/pve/tasks"
    assert json_resource_url("items", lang="zh", mode="pvp").endswith(
        "/regular/items_zh"
    )


def test_scope_and_cache_key():
    assert parse_game_mode() == "pvp"
    with game_mode_scope("pve"):
        assert parse_game_mode() == "pve"
        assert raw_row_id() == 2
        assert cache_key("t") == "pve:t"
    assert parse_game_mode() == "pvp"
    assert sync_modes() == ("pvp", "pve")
    assert sync_modes("pve") == ("pve",)


def test_run_for_modes_walks_both_and_returns_last():
    seen: list[str] = []

    def fn() -> str:
        seen.append(parse_game_mode())
        return seen[-1]

    class Boom(Exception):
        pass

    assert run_for_modes(fn, error_cls=Boom, label="t") == "pve"
    assert seen == ["pvp", "pve"]
    assert parse_game_mode() == "pvp"


def test_async_game_mode_dep_keeps_401_and_mode():
    """sync yield 会在线程池里 reset ContextVar，把 401 变成 500。"""
    from fastapi import APIRouter, Depends, FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.api.guides.tarkov import tarkov_game_mode

    app = FastAPI()
    router = APIRouter()
    router.dependencies.append(Depends(tarkov_game_mode))

    @router.get("/need-auth")
    def need_auth():
        raise HTTPException(status_code=401, detail="未登录")

    @router.get("/mode")
    def read_mode():
        return {"mode": parse_game_mode()}

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=True)
    denied = client.get("/need-auth?game_mode=pve")
    assert denied.status_code == 401
    assert client.get("/mode?game_mode=pve").json() == {"mode": "pve"}
    assert client.get("/mode").json() == {"mode": "pvp"}
    assert parse_game_mode() == "pvp"
