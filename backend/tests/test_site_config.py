"""站点公开配置：ICP 备案号合并与 OpenAPI 是否需登录。"""

from app.core.file_config import write_json
from app.main import app
from app.services import site_config as sc


def test_normalize_strips_and_clamps() -> None:
    assert sc.normalize_icp_beian_no("  浙ICP备1号  ") == "浙ICP备1号"
    assert sc.normalize_icp_beian_no("a\n\tb") == "a b"
    assert sc.normalize_icp_beian_no(None) == ""
    long = "备" * 80
    assert len(sc.normalize_icp_beian_no(long)) == 64


def test_load_defaults_when_unconfigured() -> None:
    cfg = sc.load_site_config()
    assert cfg["icp_beian_no"] == ""


def test_stored_file_is_authoritative() -> None:
    write_json("auth", {"icp_beian_no": ""})
    cfg = sc.load_site_config()
    assert cfg["icp_beian_no"] == ""
    write_json("auth", {"icp_beian_no": "浙ICP备123号"})
    assert sc.load_site_config()["icp_beian_no"] == "浙ICP备123号"


def test_save_roundtrip_and_clear() -> None:
    saved = sc.save_site_config(None, {"icp_beian_no": " 京ICP备9号 "})
    assert saved["icp_beian_no"] == "京ICP备9号"
    assert sc.load_site_config()["icp_beian_no"] == "京ICP备9号"
    sc.save_site_config(None, {"icp_beian_no": "  "})
    assert sc.load_site_config()["icp_beian_no"] == ""


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
