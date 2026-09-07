"""站点公开配置：ICP 备案号合并与 OpenAPI 是否需登录。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.main import app
from app.models.system_config import SystemConfig
from app.services import site_config as sc
from tests.integrations_fakes import db_with_stored


def test_normalize_strips_and_clamps() -> None:
    assert sc.normalize_icp_beian_no("  浙ICP备1号  ") == "浙ICP备1号"
    assert sc.normalize_icp_beian_no("a\n\tb") == "a b"
    assert sc.normalize_icp_beian_no(None) == ""
    long = "备" * 80
    assert len(sc.normalize_icp_beian_no(long)) == 64


def test_load_uses_env_when_unconfigured(monkeypatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ICP_BEIAN_NO", "浙ICP备123号")
    get_settings.cache_clear()
    try:
        cfg = sc.load_site_config(db_with_stored(None))
        assert cfg["icp_beian_no"] == "浙ICP备123号"
    finally:
        get_settings.cache_clear()


def test_stored_empty_overrides_env(monkeypatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ICP_BEIAN_NO", "浙ICP备123号")
    get_settings.cache_clear()
    try:
        cfg = sc.load_site_config(db_with_stored({"icp_beian_no": ""}))
        assert cfg["icp_beian_no"] == ""
    finally:
        get_settings.cache_clear()


def _sqlite() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[SystemConfig.__table__])
    return sessionmaker(bind=engine)()


def test_save_roundtrip_and_clear(monkeypatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ICP_BEIAN_NO", "env号")
    get_settings.cache_clear()
    db = _sqlite()
    try:
        saved = sc.save_site_config(db, {"icp_beian_no": " 京ICP备9号 "})
        assert saved["icp_beian_no"] == "京ICP备9号"
        assert sc.load_site_config(db)["icp_beian_no"] == "京ICP备9号"
        sc.save_site_config(db, {"icp_beian_no": "  "})
        assert sc.load_site_config(db)["icp_beian_no"] == ""
    finally:
        db.close()
        get_settings.cache_clear()


def test_public_shape() -> None:
    out = sc.public_site_config({"icp_beian_no": " 浙ICP备1号 "})
    assert out["icp_beian_no"] == "浙ICP备1号"
    assert out["icp_beian_href"] == sc.ICP_BEIAN_HREF


def test_site_public_openapi_unauthenticated() -> None:
    schema = app.openapi()
    public = (schema.get("paths") or {}).get("/api/settings/site/public", {}).get("get")
    assert public is not None
    assert not public.get("security")
    put = (schema.get("paths") or {}).get("/api/settings/site", {}).get("put")
    assert put is not None
    assert put.get("security")
