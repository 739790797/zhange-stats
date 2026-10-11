"""local_dev 种子脚本：生产环境拒绝 --wipe。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from local_dev import seed_local, steam_fake


def _production(monkeypatch: pytest.MonkeyPatch, module) -> None:
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(is_production=True))


def test_wipe_non_admin_users_refuses_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _production(monkeypatch, steam_fake)
    with pytest.raises(RuntimeError, match="APP_ENV=production"):
        steam_fake.wipe_non_admin_users(None)  # type: ignore[arg-type]


def test_seed_local_wipe_refuses_before_opening_db(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _production(monkeypatch, seed_local)

    def no_session():
        raise AssertionError("must not open a DB session")

    monkeypatch.setattr(seed_local, "SessionLocal", no_session)
    assert seed_local.main(["--wipe"]) == 2
    assert "--wipe" in capsys.readouterr().err
