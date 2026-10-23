from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.api.guides.tarkov import tarkov_map_svg
from app.api.skland.arknights import skland_arknights_asset
from app.core.database import Base
from app.services import upstream_repos
from app.services.skland import arknights_assets, arknights_catalog


def _local_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo_id: str) -> Path:
    monkeypatch.setattr(upstream_repos, "resolve_install_dir", lambda: tmp_path)
    root = tmp_path / "data" / "repos" / repo_id
    (root / ".git").mkdir(parents=True)
    return root


def test_arknights_catalog_reads_local_files(tmp_path: Path, monkeypatch) -> None:
    root = _local_repo(tmp_path, monkeypatch, upstream_repos.REPO_ARKNIGHTS)
    table_path = root / arknights_catalog.CHARACTER_TABLE_REL
    table_path.parent.mkdir(parents=True)
    table_path.write_text(
        json.dumps(
            {
                "char_fixture": {
                    "name": "Fixture",
                    "profession": "CASTER",
                    "rarity": 5,
                    "displayNumber": "001",
                }
            }
        ),
        encoding="utf-8",
    )
    (root / arknights_catalog.VERSION_REL).write_text("fixture-version", encoding="utf-8")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    try:
        result = arknights_catalog.sync_from_upstream(db)
        operators = arknights_catalog.list_operators(db)
    finally:
        db.close()
        engine.dispose()

    assert result["source_version"] == "fixture-version"
    assert result["operator_count"] == 1
    assert operators[0].name == "Fixture"
    assert operators[0].avatar_url == "/api/skland/arknights/assets/avatar/char_fixture.png"


def test_arknights_asset_route_distinguishes_missing_and_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    root = _local_repo(tmp_path, monkeypatch, upstream_repos.REPO_ARKNIGHTS)
    avatar = root / "avatar" / "char_fixture.png"
    avatar.parent.mkdir()
    avatar.write_bytes(b"png")

    response = skland_arknights_asset("avatar", "char_fixture.png")
    assert Path(response.path) == avatar
    with pytest.raises(HTTPException) as missing:
        skland_arknights_asset("avatar", "missing.png")
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as illegal:
        skland_arknights_asset("avatar", "../private.png")
    assert illegal.value.status_code == 404

    monkeypatch.setattr(
        arknights_assets,
        "ensure_repo",
        lambda _repo: (_ for _ in ()).throw(upstream_repos.RepoError("clone failed")),
    )
    with pytest.raises(HTTPException) as unavailable:
        skland_arknights_asset("avatar", "char_fixture.png")
    assert unavailable.value.status_code == 503


def test_tarkov_svg_route_reads_local_clone_and_maps_errors(
    tmp_path: Path, monkeypatch
) -> None:
    root = _local_repo(tmp_path, monkeypatch, upstream_repos.REPO_TARKOV_SVG)
    svg = root / "custom.svg"
    svg.write_text("<svg/>", encoding="utf-8")

    response = tarkov_map_svg("custom.svg")
    assert Path(response.path) == svg
    with pytest.raises(HTTPException) as missing:
        tarkov_map_svg("missing.svg")
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as illegal:
        tarkov_map_svg("../custom.svg")
    assert illegal.value.status_code == 404

    monkeypatch.setattr(
        upstream_repos,
        "ensure_repo",
        lambda _repo: (_ for _ in ()).throw(upstream_repos.RepoError("clone failed")),
    )
    with pytest.raises(HTTPException) as unavailable:
        tarkov_map_svg("custom.svg")
    assert unavailable.value.status_code == 503
