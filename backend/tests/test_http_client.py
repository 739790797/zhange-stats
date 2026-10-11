import gzip
import time

import httpx
import pytest

from app.core import http_client
from app.core.http_client import (
    CONNECT_TIMEOUT_SEC,
    MAX_REDIRECTS,
    HttpRequestError,
    HttpResponseTooLarge,
    _deadline_sec,
    _timeout,
    http_download,
    http_request,
    http_stream,
)

MIB = 1024 * 1024


class _Chunks(httpx.SyncByteStream):
    """逐块吐 body，记下读到第几块、有没有被关（验证超限时立刻断开）。"""

    def __init__(self, chunks: list[bytes], *, delay: float = 0.0) -> None:
        self._chunks = chunks
        self._delay = delay
        self.pulled = 0
        self.closed = False

    def __iter__(self):
        for chunk in self._chunks:
            if self._delay:
                time.sleep(self._delay)
            self.pulled += 1
            yield chunk

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch):
    """把进程级 client 换成 MockTransport(handler)；返回实际发出去的请求。"""
    clients: list[httpx.Client] = []

    def install(handler):
        seen: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        client = http_client._new_client(transport=httpx.MockTransport(record))
        clients.append(client)
        monkeypatch.setattr(http_client, "_client", client)
        return seen

    yield install
    for client in clients:
        client.close()


def _redirect(location: str, status: int = 302) -> httpx.Response:
    return httpx.Response(status, headers={"location": location})


def test_connect_timeout_capped() -> None:
    t = _timeout(20)
    assert t.connect == CONNECT_TIMEOUT_SEC
    assert t.read == 20


def test_short_read_also_caps_connect() -> None:
    t = _timeout(2)
    assert t.connect == 2
    assert t.read == 2


def test_explicit_connect_not_capped() -> None:
    t = _timeout(300, connect=20)
    assert t.connect == 20
    assert t.read == 300


def test_default_deadline_scales_with_the_read_timeout() -> None:
    assert _deadline_sec(None, None) == 60
    assert _deadline_sec(None, 120) == 600
    assert _deadline_sec(5, 120) == 5


def test_http_download_streams_progress(serve) -> None:
    serve(
        lambda _req: httpx.Response(
            200, headers={"content-length": "5"}, stream=_Chunks([b"he", b"llo"])
        )
    )
    seen: list[tuple[int, int | None]] = []
    status, body, _headers = http_download(
        "GET",
        "https://example.test/x",
        on_bytes=lambda n, total: seen.append((n, total)),
    )
    assert status == 200
    assert body == b"hello"
    assert seen == [(0, 5), (2, 5), (5, 5)]


def test_http_download_returns_error_bodies(serve) -> None:
    serve(lambda _req: httpx.Response(503, content=b"busy"))
    status, body, _headers = http_download(
        "GET", "https://example.test/x", on_bytes=lambda *_a: None
    )
    assert (status, body) == (503, b"busy")


def test_http_stream_yields_response(serve) -> None:
    seen = serve(lambda _req: httpx.Response(200, stream=_Chunks([b"o", b"k"])))
    with http_stream("GET", "https://example.test/file", timeout=300, connect=20) as resp:
        assert resp.status_code == 200
        assert b"".join(resp.iter_bytes()) == b"ok"
    assert [(r.method, str(r.url)) for r in seen] == [("GET", "https://example.test/file")]
    timeout = seen[0].extensions["timeout"]
    assert (timeout["connect"], timeout["read"]) == (20, 300)


def test_same_host_redirect_keeps_custom_headers(serve) -> None:
    seen = serve(
        lambda req: _redirect("/v2/sign")
        if req.url.path == "/v1/sign"
        else httpx.Response(200, json={"ok": 1})
    )
    resp = http_request("GET", "https://zonai.skland.com/v1/sign", headers={"cred": "c-1"})
    assert resp.json() == {"ok": 1}
    assert [r.url.path for r in seen] == ["/v1/sign", "/v2/sign"]
    assert seen[1].headers["cred"] == "c-1"


def test_cross_host_redirect_carrying_a_credential_header_is_refused(serve) -> None:
    seen = serve(lambda _req: _redirect("https://collector.example/steal"))
    with pytest.raises(HttpRequestError, match="collector.example") as exc_info:
        http_request(
            "GET", "https://api.kurobbs.com/user/mineV2", headers={"token": "secret-token"}
        )
    assert [r.url.host for r in seen] == ["api.kurobbs.com"]
    assert "secret-token" not in str(exc_info.value)


def test_cross_host_redirect_without_credentials_is_followed(serve) -> None:
    seen = serve(
        lambda req: _redirect("https://cdn.example/table.json")
        if req.url.host == "raw.example"
        else httpx.Response(200, content=b"{}")
    )
    resp = http_request(
        "GET", "https://raw.example/table.json", headers={"User-Agent": "zhange-stats/1.0"}
    )
    assert resp.content == b"{}"
    assert [r.url.host for r in seen] == ["raw.example", "cdn.example"]


def test_cross_host_redirect_drops_authorization_instead_of_refusing(serve) -> None:
    seen = serve(
        lambda req: _redirect("https://cdn.example/model.onnx")
        if req.url.host == "hub.example"
        else httpx.Response(200, content=b"weights")
    )
    resp = http_request(
        "GET", "https://hub.example/resolve/model.onnx", headers={"Authorization": "Bearer x"}
    )
    assert resp.content == b"weights"
    assert "authorization" not in seen[1].headers


def test_https_to_http_redirect_is_refused(serve) -> None:
    seen = serve(lambda _req: _redirect("http://example.test/plain"))
    with pytest.raises(HttpRequestError, match="HTTPS"):
        http_request("GET", "https://example.test/secure")
    assert len(seen) == 1


def test_cross_host_307_does_not_resend_the_body(serve) -> None:
    seen = serve(lambda _req: _redirect("https://other.example/login", status=307))
    with pytest.raises(HttpRequestError, match="请求体"):
        http_request(
            "POST",
            "https://passport.example/login",
            content=b"passwd=x",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert len(seen) == 1


def test_follow_redirects_false_returns_the_redirect(serve) -> None:
    serve(lambda _req: _redirect("https://elsewhere.example/"))
    resp = http_request("GET", "https://example.test/a", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://elsewhere.example/"


def test_redirect_chain_is_capped(serve) -> None:
    seen = serve(lambda req: _redirect(f"{req.url.path}x"))
    with pytest.raises(HttpRequestError, match="跳转次数过多"):
        http_request("GET", "https://example.test/a")
    assert len(seen) == MAX_REDIRECTS + 1


def test_http_stream_checks_redirects_too(serve) -> None:
    seen = serve(lambda _req: _redirect("https://collector.example/files"))
    with pytest.raises(HttpRequestError, match="凭证"):
        with http_stream("GET", "https://panel.example/files", headers={"X-Api-Key": "k"}):
            pass
    assert len(seen) == 1


def test_declared_oversized_body_is_refused_before_reading(serve) -> None:
    stream = _Chunks([b"x" * 20])
    serve(lambda _req: httpx.Response(200, headers={"content-length": "20"}, stream=stream))
    with pytest.raises(HttpResponseTooLarge):
        http_request("GET", "https://example.test/big", max_bytes=10)
    assert stream.pulled == 0
    assert stream.closed


def test_head_is_not_refused_for_its_declared_length(serve) -> None:
    serve(lambda _req: httpx.Response(200, headers={"content-length": str(64 * MIB)}))
    assert http_request("HEAD", "https://example.test/file").status_code == 200


def test_streamed_body_is_cut_off_once_it_passes_the_cap(serve) -> None:
    stream = _Chunks([b"x" * 1024] * 100)
    serve(lambda _req: httpx.Response(200, stream=stream))
    with pytest.raises(HttpResponseTooLarge):
        http_request("GET", "https://example.test/drip", max_bytes=4096)
    assert stream.pulled == 5
    assert stream.closed


def test_cap_counts_decompressed_bytes(serve) -> None:
    packed = gzip.compress(b"\0" * 65536)

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip", "content-length": str(len(packed))},
            stream=_Chunks([packed]),
        )

    serve(handler)
    with pytest.raises(HttpResponseTooLarge):
        http_request("GET", "https://example.test/bomb", max_bytes=16 * 1024)
    assert http_request("GET", "https://example.test/bomb", max_bytes=None).content == (
        b"\0" * 65536
    )


def test_default_cap_is_8_mib_and_can_be_lifted(serve) -> None:
    serve(lambda _req: httpx.Response(200, stream=_Chunks([b"x" * MIB] * 9)))
    with pytest.raises(HttpResponseTooLarge):
        http_download("GET", "https://example.test/items.json", on_bytes=lambda *_a: None)
    with pytest.raises(HttpResponseTooLarge):
        http_request("GET", "https://example.test/items.json")
    assert len(http_request("GET", "https://example.test/items.json", max_bytes=None).content) == (
        9 * MIB
    )
    serve(lambda _req: httpx.Response(200, stream=_Chunks([b"x" * MIB] * 8)))
    assert len(http_request("GET", "https://example.test/items.json").content) == 8 * MIB


def test_slow_drip_body_hits_the_overall_deadline(serve) -> None:
    stream = _Chunks([b"x"] * 50, delay=0.02)
    serve(lambda _req: httpx.Response(200, stream=stream))
    with pytest.raises(HttpRequestError, match="请求超时"):
        http_request("GET", "https://example.test/drip", deadline=0.05)
    assert stream.pulled <= 3
    assert stream.closed


def test_deadline_covers_redirect_hops(serve) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        time.sleep(0.03)
        return _redirect(f"{req.url.path}x")

    seen = serve(handler)
    with pytest.raises(HttpRequestError, match="请求超时"):
        http_request("GET", "https://example.test/a", deadline=0.05)
    assert len(seen) <= 2
