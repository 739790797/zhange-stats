"""工作台改装预览图：SPT 信封、工厂/裸枪短路、代理可注入。"""

from __future__ import annotations

import asyncio
import re

import pytest

from app.services.tarkov import workbench as wb
from app.services.tarkov import workbench_image as img
from app.services.tarkov import workbench_image_pw as pw
from tests.test_tarkov_workbench import CYCLIC_PAIRS, _payload, make_cyclic


@pytest.fixture
def index() -> wb.WorkbenchIndex:
    return wb.build_index("json.tarkov.dev", _payload())


@pytest.fixture(autouse=True)
def _reset_backend() -> None:
    yield
    img.set_image_gen_backend(None)
    img.clear_image_cache()


def _enable_image_gen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        img,
        "get_settings",
        lambda: type("S", (), {"TARKOV_WORKBENCH_IMAGE_GEN": True})(),
    )


def test_source_name_skips_locale_keys(index: wb.WorkbenchIndex):
    gun = index.items["gun1"]
    assert gun.name == "测试步枪"
    assert gun.name_en == ""
    assert gun.short_name_en == "TR"
    assert img.search_name(gun) == "TR"
    gun.name = "短突击步枪"
    gun.name_en = "Kalashnikov AKS-74U 5.45x39 assault rifle"
    assert img.search_name(gun) == "Kalashnikov AKS-74U 5.45x39 assault rifle"


def test_cookie_button_pattern_matches_image_gen_banner():
    from app.services.tarkov.workbench_image_pw import _COOKIE_RE

    assert _COOKIE_RE.search("Decline")
    assert _COOKIE_RE.search("Accept Analytics")


def test_hex24_is_stable_24_hex():
    first = img._bp_hex24("gun1:root")
    assert first == img._bp_hex24("gun1:root")
    assert len(first) == 24
    assert first != img._bp_hex24("gun2:root")


def test_spt_items_use_game_slot_names(index: wb.WorkbenchIndex):
    gun = wb._require_gun(index, "gun1")
    items = img.build_spt_items(
        index,
        gun,
        [("slot-grip", "grip1"), ("slot-rail", "rail1")],
    )
    assert items[0]["_tpl"] == "gun1"
    assert items[0]["slotId"] == "hideout"
    by_tpl = {row["_tpl"]: row for row in items}
    assert by_tpl["grip1"]["slotId"] == "mod_pistol_grip"
    assert by_tpl["grip1"]["parentId"] == items[0]["_id"]
    assert by_tpl["rail1"]["slotId"] == "mod_tactical"
    assert by_tpl["rail1"]["parentId"] == by_tpl["grip1"]["_id"]


def test_classify_bare_and_factory(index: wb.WorkbenchIndex):
    gun = wb._require_gun(index, "preset1")
    assert img.classify_build(index, gun, []) == "bare"
    factory = wb.map_factory_pairs(index, "preset1")
    assert img.classify_build(index, gun, factory) == "factory"
    assert img.classify_build(index, gun, [("slot-grip", "grip2")]) == "custom"


def test_render_factory_skips_backend(index: wb.WorkbenchIndex, monkeypatch: pytest.MonkeyPatch):
    class Boom:
        busy = False
        last_error = None

        def generate(self, **_kwargs: object) -> str:
            raise AssertionError("factory must not call image-gen")

    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    img.set_image_gen_backend(Boom())
    factory = wb.map_factory_pairs(index, "gun1")
    out = img.render_build_image(None, "gun1", factory)  # type: ignore[arg-type]
    assert out["kind"] == "factory"
    assert out["image_url"] == "https://x/preset-512.png"


def test_render_bare_uses_receiver_image(index: wb.WorkbenchIndex, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    out = img.render_build_image(None, "gun1", [])  # type: ignore[arg-type]
    assert out["kind"] == "bare"
    assert out["image_url"] == "https://x/gun-512.png"


def test_render_custom_uses_backend(index: wb.WorkbenchIndex, monkeypatch: pytest.MonkeyPatch):
    class Fake:
        busy = False
        last_error = None
        seen: dict | None = None

        def generate(self, **kwargs: object) -> str:
            self.seen = kwargs
            return "https://image-gen.tarkov-changes.com/gen.png"

    fake = Fake()
    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    _enable_image_gen(monkeypatch)
    img.set_image_gen_backend(fake)
    out = img.render_build_image(  # type: ignore[arg-type]
        None,
        "preset1",
        [("slot-grip", "grip2")],
    )
    assert out["kind"] == "generated"
    assert out["image_url"] == "https://image-gen.tarkov-changes.com/gen.png"
    assert fake.seen is not None
    assert fake.seen["gun_id"] == "gun1"
    assert fake.seen["weapon_name"] == "TR"
    items = fake.seen["items"]
    assert items[0]["_tpl"] == "gun1"
    assert any(row["_tpl"] == "grip2" for row in items)


def test_render_custom_falls_back_when_backend_fails(
    index: wb.WorkbenchIndex, monkeypatch: pytest.MonkeyPatch
):
    class Fake:
        busy = False
        last_error = "down"

        def generate(self, **_kwargs: object) -> str:
            raise RuntimeError("down")

    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    _enable_image_gen(monkeypatch)
    img.set_image_gen_backend(Fake())
    out = img.render_build_image(  # type: ignore[arg-type]
        None, "gun1", [("slot-grip", "grip2")]
    )
    assert out["kind"] == "unavailable"
    assert out["image_url"] == "https://x/preset-512.png"
    assert out["message"]
    assert out["busy"] is False


def test_render_respects_env_disable(
    index: wb.WorkbenchIndex, monkeypatch: pytest.MonkeyPatch
):
    class Boom:
        busy = False
        last_error = None

        def generate(self, **_kwargs: object) -> str:
            raise AssertionError("disabled must not call image-gen")

    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    monkeypatch.setattr(
        img,
        "get_settings",
        lambda: type("S", (), {"TARKOV_WORKBENCH_IMAGE_GEN": False})(),
    )
    img.set_image_gen_backend(Boom())
    out = img.render_build_image(  # type: ignore[arg-type]
        None, "gun1", [("slot-grip", "grip2")]
    )
    assert out["kind"] == "unavailable"
    assert out["enabled"] is False


def test_render_busy_returns_without_waiting(
    index: wb.WorkbenchIndex, monkeypatch: pytest.MonkeyPatch
):
    class Busy:
        busy = True
        last_error = None

        def generate(self, **_kwargs: object) -> str:
            raise img.ImageGenBusy()

    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    _enable_image_gen(monkeypatch)
    img.set_image_gen_backend(Busy())
    out = img.render_build_image(  # type: ignore[arg-type]
        None, "gun1", [("slot-grip", "grip2")]
    )
    assert out["kind"] == "unavailable"
    assert out["busy"] is True
    assert out["image_url"] == "https://x/preset-512.png"


def test_accept_generated_image_url_is_same_origin():
    assert img.accept_generated_image_url("/gen.png") == (
        "https://image-gen.tarkov-changes.com/gen.png"
    )
    assert (
        img.accept_generated_image_url(
            "https://image-gen.tarkov-changes.com/gen.png"
        )
        == "https://image-gen.tarkov-changes.com/gen.png"
    )
    assert img.accept_generated_image_url("https://evil.example/x.png") is None
    assert img.accept_generated_image_url("//evil.example/x.png") is None


def test_render_custom_rejects_off_origin_url(
    index: wb.WorkbenchIndex, monkeypatch: pytest.MonkeyPatch
):
    class Fake:
        busy = False
        last_error = None

        def generate(self, **_kwargs: object) -> str:
            return "https://evil.example/phish.png"

    monkeypatch.setattr(wb, "load_index", lambda _db: index)
    _enable_image_gen(monkeypatch)
    img.set_image_gen_backend(Fake())
    out = img.render_build_image(  # type: ignore[arg-type]
        None, "preset1", [("slot-grip", "grip2")]
    )
    assert out["kind"] == "unavailable"
    assert out["image_url"] == "https://x/preset-512.png"


def test_ordered_pairs_cuts_cycles(index: wb.WorkbenchIndex):
    make_cyclic(index)
    gun = wb._require_gun(index, "gun1")
    ordered = img.ordered_pairs(index, gun, CYCLIC_PAIRS)
    assert ordered == [("slot-grip", "grip1"), ("slot-rail", "rail1")]
    assert img.classify_build(index, gun, CYCLIC_PAIRS) == "custom"
    tpls = [row["_tpl"] for row in img.build_spt_items(index, gun, CYCLIC_PAIRS)]
    assert tpls == ["gun1", "grip1", "rail1"]


class _FakeCloser:
    def __init__(self, calls: list[str], name: str, *, hang: bool = False, fail: bool = False):
        self.calls = calls
        self.name = name
        self.hang = hang
        self.fail = fail

    async def _run(self) -> None:
        self.calls.append(self.name)
        if self.hang:
            await asyncio.sleep(3600)
        if self.fail:
            raise RuntimeError(f"{self.name} boom")

    async def close(self) -> None:
        await self._run()

    async def stop(self) -> None:
        await self._run()


def test_pw_reset_closes_everything_even_if_context_hangs(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pw, "_CLOSE_TIMEOUT", 0.05)
    calls: list[str] = []
    backend = pw.PatchrightImageBackend()
    backend._pw_page = object()
    backend._pw_context = _FakeCloser(calls, "context", hang=True)
    backend._pw_browser = _FakeCloser(calls, "browser", fail=True)
    backend._pw_instance = _FakeCloser(calls, "playwright")
    asyncio.run(backend._reset_page())
    assert calls == ["context", "browser", "playwright"]
    assert backend._pw_page is None
    assert backend._pw_context is None
    assert backend._pw_browser is None
    assert backend._pw_instance is None


def test_pw_generate_failure_stops_driver_and_kills_profile(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pw, "_CLOSE_TIMEOUT", 0.05)
    calls: list[str] = []
    monkeypatch.setattr(pw, "_kill_profile_chrome", lambda: calls.append("kill"))
    backend = pw.PatchrightImageBackend()

    async def _boom(*_args: object) -> dict:
        raise RuntimeError("等待出图服务超时")

    monkeypatch.setattr(backend, "_do_request", _boom)
    backend._pw_page = object()
    backend._pw_context = _FakeCloser(calls, "context", hang=True)
    backend._pw_instance = _FakeCloser(calls, "playwright")
    try:
        with pytest.raises(RuntimeError, match="超时"):
            backend.generate(gun_id="gun1", items=[], weapon_name="TR")
        # 旧实现：reset 失败就直接置空句柄，driver/Chrome 没人关
        assert calls == ["context", "playwright", "kill"]
        assert backend._pw_context is None
        assert backend._pw_instance is None
        assert backend.last_error == "等待出图服务超时"
    finally:
        backend.shutdown()


def test_pw_posix_kill_targets_only_profile(monkeypatch: pytest.MonkeyPatch, tmp_path):
    profile = tmp_path / "a.b (x)" / pw._PROFILE_NAME
    seen: list[list[str]] = []

    def _fake_run(args: list[str], **kwargs: object) -> None:
        assert "shell" not in kwargs
        seen.append(args)

    monkeypatch.setattr(pw.sys, "platform", "linux")
    monkeypatch.setattr(pw, "_profile_dir", lambda: profile)
    monkeypatch.setattr(pw.subprocess, "run", _fake_run)
    pw._kill_profile_chrome()
    assert len(seen) == 1
    args = seen[0]
    assert args[:3] == ["pkill", "-KILL", "-f"]
    pattern = args[3]
    assert not pattern.startswith("-")
    assert pattern.endswith(pw._PROFILE_NAME)
    # ERE 元字符已转义：'.' '(' ')' 不会误匹配别的路径
    assert r"a\.b \(x\)" in pattern
    assert re.search(pattern, f"chrome --user-data-dir={profile} --headless=new")
    assert not re.search(pattern, "chrome --user-data-dir=/home/u/.config/google-chrome")
