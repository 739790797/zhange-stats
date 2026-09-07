"""Playwright/Patchright 代理 image-gen.tarkov-changes.com。

该站没有公开 HTTP 契约（Cloudflare + 页面自己发 /api/generate-build）。
流程对齐 EFTForge（MIT）：真实 Chrome 会话里拦截 fetch，换上我们的 SPT items。
不是图鉴回源，失败时工作台回落 dump 静图。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.tarkov.workbench_image import ImageGenBusy

logger = logging.getLogger(__name__)

IMAGE_GEN_BUILD = "https://image-gen.tarkov-changes.com/build"

# 注入到页面 MAIN world，赶在站点脚本之前包住 window.fetch。
# 逻辑来自 EFTForge backend/main.py（MIT）。
_FETCH_OVERRIDE_SCRIPT = r"""
(function() {
    if (typeof window === 'undefined') return;
    if (window.__ZG_INSTALLED__) return;
    window.__ZG_INSTALLED__ = true;
    window.__ZG_BUILD_OVERRIDE__ = null;
    document.addEventListener('__zg_set_override__', function(e) {
        window.__ZG_BUILD_OVERRIDE__ = e.detail;
    });
    var _origFetch = window.fetch;
    if (typeof _origFetch !== 'function') return;
    window.fetch = function(url, init) {
        var urlStr = (url instanceof Request) ? url.url : String(url);
        if (urlStr.indexOf('/api/generate-build') !== -1 &&
                window.__ZG_BUILD_OVERRIDE__) {
            var override = window.__ZG_BUILD_OVERRIDE__;
            window.__ZG_BUILD_OVERRIDE__ = null;
            try {
                var naturalBodyStr = (!(url instanceof Request) && init && init.body)
                    ? init.body : '{}';
                var naturalBody = JSON.parse(naturalBodyStr);
                var naturalItems, bodyShape;
                if (naturalBody.data && Array.isArray(naturalBody.data.items)) {
                    naturalItems = naturalBody.data.items;
                    bodyShape = 'data';
                } else if (Array.isArray(naturalBody.items)) {
                    naturalItems = naturalBody.items;
                    bodyShape = 'root';
                } else {
                    naturalItems = [];
                    bodyShape = 'unknown';
                }
                var naturalGun = naturalItems[0];
                var ourItems = (override.data && override.data.items) || [];
                var ourGunId = ourItems.length > 0 ? ourItems[0]._id : null;
                var mergedItems;
                if (naturalGun && ourGunId && ourItems.length > 1) {
                    mergedItems = [naturalGun];
                    for (var i = 1; i < ourItems.length; i++) {
                        var att = Object.assign({}, ourItems[i]);
                        if (att.parentId === ourGunId) {
                            att.parentId = naturalGun._id;
                        }
                        mergedItems.push(att);
                    }
                } else {
                    mergedItems = ourItems;
                }
                var newBodyObj;
                if (bodyShape === 'data') {
                    newBodyObj = Object.assign({}, naturalBody, {
                        data: Object.assign({}, naturalBody.data, {
                            id: naturalGun ? naturalGun._id : naturalBody.data.id,
                            items: mergedItems
                        })
                    });
                } else if (bodyShape === 'root') {
                    newBodyObj = Object.assign({}, naturalBody, {
                        id: naturalGun ? naturalGun._id : naturalBody.id,
                        items: mergedItems
                    });
                } else {
                    newBodyObj = {
                        data: {
                            id: override.data && override.data.id,
                            items: mergedItems
                        }
                    };
                }
                var newBody = JSON.stringify(newBodyObj);
                if (url instanceof Request) {
                    url = new Request(url, { body: newBody });
                } else {
                    init = Object.assign({}, init || {}, { body: newBody });
                }
                try { document.body.setAttribute('data-zg-fired', '1'); } catch(_e) {}
            } catch(e) {
                try { document.body.setAttribute('data-zg-fired', 'merge-failed:' + e.message); } catch(_e2) {}
            }
        }
        return _origFetch.apply(this, [url, init]);
    };
})();
"""

_SW_CODE = r"""
self.addEventListener('install', function(e) { e.waitUntil(self.skipWaiting()); });
self.addEventListener('activate', function(e) { e.waitUntil(self.clients.claim()); });
"""

_COOKIE_RE = re.compile(
    r"Decline|Reject|Accept Analytics|Reject All|Refuse|拒绝|不同意",
    re.I,
)

_PROFILE_NAME = "tarkov_pw_profile"


def _profile_dir() -> Path:
    return get_settings().data_dir_path / _PROFILE_NAME


def _kill_profile_chrome() -> None:
    """uvicorn --reload 会留下占着 profile 的 Chrome，下一轮 launch 会一直挂。"""
    if sys.platform != "win32":
        return
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" |"
                    f" Where-Object {{ $_.CommandLine -like '*{_PROFILE_NAME}*' }} |"
                    " ForEach-Object { Stop-Process -Id $_.ProcessId -Force"
                    " -ErrorAction SilentlyContinue }"
                ),
            ],
            timeout=8,
            capture_output=True,
            check=False,
        )
    except Exception as exc:
        logger.warning("kill leftover image-gen chrome: %s", exc)


async def _dismiss_image_gen_overlays(page: Any) -> None:
    """Cookie / 选枪引导会挡住搜索框，无头里必须点掉。"""
    for selector in (
        "#onetrust-reject-all-handler",
        "#onetrust-accept-btn-handler",
        "button#onetrust-reject-all-handler",
    ):
        loc = page.locator(selector)
        try:
            if await loc.count():
                await loc.first.click(timeout=1500)
        except Exception:
            pass
    try:
        btn = page.get_by_role("button", name=_COOKIE_RE)
        if await btn.count():
            await btn.first.click(timeout=1500)
    except Exception:
        pass
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass


async def _pick_weapon_in_search(page: Any, weapon_name: str) -> None:
    search = page.get_by_placeholder("Search for an item...")
    await search.wait_for(state="visible", timeout=20000)
    await search.click(timeout=8000)
    await search.fill("")
    await search.type(weapon_name, delay=20)
    await asyncio.sleep(0.6)
    try:
        await page.get_by_text(weapon_name, exact=True).first.click(timeout=6000)
        return
    except Exception:
        pass
    try:
        await page.locator('[role="option"]').first.click(timeout=4000)
        return
    except Exception:
        pass
    await page.get_by_text(weapon_name).first.click(timeout=8000)


class PatchrightImageBackend:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._pw_instance = None
        self._pw_context = None
        self._pw_page = None
        self._req_lock: asyncio.Lock | None = None
        self._in_flight = 0
        self._last_error: str | None = None
        self._start_lock = threading.Lock()
        self._gate = threading.Lock()

    @property
    def busy(self) -> bool:
        return self._in_flight > 0

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._start_lock:
            if self._loop is not None:
                return self._loop

            def _run() -> None:
                if sys.platform == "win32":
                    loop = asyncio.ProactorEventLoop()
                else:
                    loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._loop = loop
                self._loop_ready.set()
                loop.run_forever()

            self._thread = threading.Thread(
                target=_run, daemon=True, name="tarkov-image-pw"
            )
            self._thread.start()
        if not self._loop_ready.wait(timeout=10):
            raise RuntimeError("出图浏览器事件循环未能启动")
        assert self._loop is not None
        return self._loop

    def generate(
        self,
        *,
        gun_id: str,
        items: list[dict[str, Any]],
        weapon_name: str,
    ) -> str:
        if not self._gate.acquire(blocking=False):
            raise ImageGenBusy()
        try:
            loop = self._ensure_loop()
            future = asyncio.run_coroutine_threadsafe(
                self._do_request(gun_id, items, weapon_name),
                loop,
            )
            try:
                data = future.result(timeout=90)
            except Exception as exc:
                future.cancel()
                _kill_profile_chrome()
                try:
                    asyncio.run_coroutine_threadsafe(self._reset_page(), loop).result(
                        timeout=8
                    )
                except Exception:
                    self._pw_page = None
                    self._pw_context = None
                    self._pw_instance = None
                self._last_error = str(exc)
                raise
            url = str(data.get("imageUrl") or data.get("image_url") or "").strip()
            if not url:
                self._last_error = "出图服务没有返回图片地址"
                raise RuntimeError(self._last_error)
            self._last_error = None
            return url
        finally:
            self._gate.release()

    async def _init_pw(self) -> None:
        settings = get_settings()
        profile = _profile_dir()
        _kill_profile_chrome()
        profile.mkdir(parents=True, exist_ok=True)
        for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            lock_path = profile / lock_name
            if lock_path.exists():
                try:
                    lock_path.unlink()
                except OSError:
                    pass

        from patchright.async_api import async_playwright

        self._pw_instance = await async_playwright().start()
        # 默认无头：有界面会弹出 image-gen 整页，用户侧不能接受。
        headless = bool(settings.TARKOV_WORKBENCH_IMAGE_HEADLESS)
        args = ["--disable-crash-reporter", "--mute-audio"]
        if headless:
            args.extend(["--headless=new", "--disable-gpu"])
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": str(profile),
            "headless": headless,
            "timeout": 45_000,
            "args": args,
        }
        try:
            self._pw_context = await self._pw_instance.chromium.launch_persistent_context(
                channel="chrome",
                **launch_kwargs,
            )
        except Exception as exc:
            logger.warning("chrome channel unavailable (%s), fallback chromium", exc)
            self._pw_context = await self._pw_instance.chromium.launch_persistent_context(
                **launch_kwargs,
            )
        self._pw_page = await self._pw_context.new_page()

        async def _serve_sw(route: Any) -> None:
            await route.fulfill(
                status=200,
                headers={
                    "content-type": "application/javascript; charset=utf-8",
                    "service-worker-allowed": "/",
                },
                body=_SW_CODE.encode(),
            )

        await self._pw_context.route("**/eft-sw.js", _serve_sw)
        override_tag = ("<script>" + _FETCH_OVERRIDE_SCRIPT + "</script>").encode()

        async def _patch_html(route: Any) -> None:
            try:
                resp = await route.fetch(timeout=60000)
                body = await resp.body()
                patched = body.replace(b"<head>", b"<head>" + override_tag, 1)
                strip = {
                    "content-length",
                    "content-encoding",
                    "content-security-policy",
                    "x-content-security-policy",
                    "x-webkit-csp",
                }
                hdrs = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() not in strip
                }
                await route.fulfill(status=resp.status, headers=hdrs, body=patched)
            except Exception as exc:
                logger.warning("image-gen html patch failed: %s", exc)
                await route.continue_()

        await self._pw_page.route(IMAGE_GEN_BUILD, _patch_html)
        await self._pw_page.goto(
            IMAGE_GEN_BUILD, wait_until="domcontentloaded", timeout=45000
        )
        await _dismiss_image_gen_overlays(self._pw_page)
        await self._pw_page.mouse.move(400, 300)
        await asyncio.sleep(0.4)
        await self._pw_page.mouse.move(700, 400)
        await _dismiss_image_gen_overlays(self._pw_page)
        try:
            await self._pw_page.get_by_placeholder("Search for an item...").wait_for(
                state="visible", timeout=20000
            )
        except Exception as exc:
            raise RuntimeError("出图站搜索框未出现，可能被拦截") from exc
        await self._pw_page.evaluate(
            """async () => {
            try {
                const oldRegs = await navigator.serviceWorker.getRegistrations();
                for (const r of oldRegs) await r.unregister();
                await navigator.serviceWorker.register('/eft-sw.js', {scope: '/'});
            } catch (e) {}
        }"""
        )

    async def _reset_page(self) -> None:
        self._pw_page = None
        try:
            if self._pw_context is not None:
                await self._pw_context.close()
        except Exception as exc:
            logger.warning("image-gen close context: %s", exc)
        finally:
            self._pw_context = None
        try:
            if self._pw_instance is not None:
                await self._pw_instance.stop()
        except Exception as exc:
            logger.warning("image-gen stop playwright: %s", exc)
        finally:
            self._pw_instance = None

    async def _do_request(
        self,
        gun_id: str,
        items: list[dict[str, Any]],
        weapon_name: str,
    ) -> dict[str, Any]:
        self._in_flight += 1
        try:
            if self._pw_page is None:
                await self._init_pw()
                await asyncio.sleep(1)
            if self._req_lock is None:
                self._req_lock = asyncio.Lock()
            async with self._req_lock:
                page = self._pw_page
                if page is None:
                    raise RuntimeError("出图浏览器未就绪")
                api_resp: list[tuple[int, str]] = []
                api_done = asyncio.Event()

                async def _on_response(response: Any) -> None:
                    if "/api/generate-build" in response.url and not api_done.is_set():
                        try:
                            body = await response.text()
                            api_resp.append((response.status, body))
                        except Exception as exc:
                            logger.warning("image-gen read response: %s", exc)
                        api_done.set()

                page.on("response", _on_response)
                try:
                    await page.evaluate(
                        "() => { try { document.body.removeAttribute('data-zg-fired'); } catch(_) {} }"
                    )
                    await _dismiss_image_gen_overlays(page)
                    payload = {"data": {"id": gun_id, "items": items}}
                    await page.evaluate(
                        """(payload) => {
                        document.dispatchEvent(
                            new CustomEvent('__zg_set_override__', {detail: payload})
                        );
                    }""",
                        payload,
                    )
                    await _pick_weapon_in_search(page, weapon_name)
                    try:
                        await asyncio.wait_for(api_done.wait(), timeout=30)
                    except TimeoutError as exc:
                        raise RuntimeError("等待出图服务超时") from exc
                finally:
                    page.remove_listener("response", _on_response)

                if not api_resp:
                    raise RuntimeError("没有捕获到出图响应")
                status, body = api_resp[0]
                if status >= 400 or not body.strip():
                    raise RuntimeError(f"出图服务 HTTP {status}")
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise RuntimeError("出图服务返回无法解析")
                return data
        finally:
            self._in_flight -= 1

    def shutdown(self) -> None:
        loop = self._loop
        if loop is not None:
            try:
                fut = asyncio.run_coroutine_threadsafe(self._reset_page(), loop)
                fut.result(timeout=5)
            except Exception:
                pass
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass
        _kill_profile_chrome()
        self._loop = None


_backend: PatchrightImageBackend | None = None
_backend_lock = threading.Lock()


def patchright_backend() -> PatchrightImageBackend:
    global _backend
    with _backend_lock:
        if _backend is None:
            _backend = PatchrightImageBackend()
        return _backend


def shutdown_patchright() -> None:
    global _backend
    with _backend_lock:
        backend = _backend
        _backend = None
    if backend is not None:
        backend.shutdown()
