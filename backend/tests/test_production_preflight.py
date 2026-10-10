"""保存 APP_ENV=production 前先跑启动体检：重启会被拒的情况当场 400、不写 app.json，口径与启动时一致。"""

from __future__ import annotations

import bcrypt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.settings import RuntimeEnvUpdate, update_runtime_env
from app.core.config import get_settings
from app.core.database import Base
from app.core.file_config import read_json, write_json
from app.models.user import User, UserRole
from app.services.auth_config import effective_reject_weak_admin_password
from app.services.password_policy import invalidate_weak_password_cache
from app.services.security_bootstrap import (
    check_admin_password_health,
    check_email_code_log_policy,
    production_preflight_problems,
)

ADMIN = object()
STRONG = "Str0ng-Enough!"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("APP_ENV", "ALLOW_EMAIL_CODE_LOG", "REJECT_WEAK_ADMIN_PASSWORD", "REDIS_URL", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    invalidate_weak_password_cache()
    yield
    get_settings.cache_clear()
    invalidate_weak_password_cache()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _admin(db, username: str, password: str) -> None:
    # 低 cost 只为测得快；弱口令探测照样逐个 bcrypt 比对
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    db.add(
        User(
            username=username,
            email=f"{username}@example.com",
            display_name=username,
            password_hash=hashed,
            role=UserRole.admin,
            email_verified=True,
        )
    )
    db.commit()


def _switch(db, env: str = "production"):
    return update_runtime_env(RuntimeEnvUpdate(app_env=env, csp_enforce=True), ADMIN, db)


def test_weak_admin_password_blocks_the_switch(db) -> None:
    _admin(db, "root", "123456")
    with pytest.raises(HTTPException) as exc:
        _switch(db)
    assert exc.value.status_code == 400
    assert exc.value.detail.startswith("生产环境启动体检未通过")
    assert "管理员弱口令：root" in exc.value.detail
    assert not read_json("app")
    assert get_settings().is_production is False


def test_allow_email_code_log_blocks_the_switch(db, monkeypatch) -> None:
    _admin(db, "root", STRONG)
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        _switch(db)
    assert exc.value.status_code == 400
    assert "ALLOW_EMAIL_CODE_LOG" in exc.value.detail
    assert "弱口令" not in exc.value.detail
    assert not read_json("app")


def test_every_problem_is_reported_at_once(db, monkeypatch) -> None:
    _admin(db, "root", "123456")
    _admin(db, "deputy", "deputy")
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true")
    get_settings.cache_clear()
    problems = production_preflight_problems(db)
    assert len(problems) == 2
    assert "ALLOW_EMAIL_CODE_LOG" in problems[0]
    assert "root" in problems[1] and "deputy" in problems[1]


@pytest.mark.parametrize("env", ["production", "Production", " prod "])
def test_healthy_site_switches(db, env: str) -> None:
    _admin(db, "root", STRONG)
    out = _switch(db, env)
    saved = read_json("app") or {}
    assert saved["APP_ENV"] == env
    assert saved["CSP_ENFORCE"] is True
    assert out["is_production"] is True
    assert out["restart_required"] is True


def test_explicitly_allowing_weak_admin_passwords_lets_the_switch_through(db) -> None:
    _admin(db, "root", "123456")
    write_json("auth", {"reject_weak_admin_password": False})
    _switch(db)
    assert (read_json("app") or {})["APP_ENV"] == "production"


def test_switching_to_development_does_not_run_the_checks(db, monkeypatch) -> None:
    _admin(db, "root", "123456")
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true")
    get_settings.cache_clear()
    _switch(db, "development")
    assert (read_json("app") or {})["APP_ENV"] == "development"


def test_fresh_install_without_admin_only_checks_the_email_switch(db) -> None:
    assert production_preflight_problems(db) == []
    _switch(db)
    assert (read_json("app") or {})["APP_ENV"] == "production"


@pytest.mark.parametrize(
    "password,allow_code_log,auth_cfg",
    [
        (STRONG, False, {}),
        ("123456", False, {}),
        ("root", False, {}),
        ("123456", False, {"reject_weak_admin_password": False}),
        (STRONG, True, {}),
        (None, False, {}),
    ],
)
def test_preflight_agrees_with_the_boot_checks(db, monkeypatch, password, allow_code_log, auth_cfg) -> None:
    if password is not None:
        _admin(db, "root", password)
    if auth_cfg:
        write_json("auth", auth_cfg)
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true" if allow_code_log else "false")
    get_settings.cache_clear()
    problems = production_preflight_problems(db)

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        check_email_code_log_policy()
        check_admin_password_health(db)
        boot_refused = False
    except RuntimeError:
        boot_refused = True
    assert bool(problems) is boot_refused


def test_reject_default_follows_the_target_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    unset = {"reject_weak_admin_password": None}
    assert effective_reject_weak_admin_password(unset) is False
    assert effective_reject_weak_admin_password(unset, production=True) is True
    assert effective_reject_weak_admin_password({"reject_weak_admin_password": False}, production=True) is False
    monkeypatch.setenv("REJECT_WEAK_ADMIN_PASSWORD", "false")
    get_settings.cache_clear()
    assert effective_reject_weak_admin_password(unset, production=True) is False
