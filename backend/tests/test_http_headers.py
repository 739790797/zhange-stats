import anyio
import httpx

from app.core.http_headers import CSP_POLICY, parse_request_id
from app.main import app


def test_parse_request_id_accepts_incoming_or_generates() -> None:
    assert parse_request_id("abc-123") == "abc-123"
    generated = parse_request_id("")
    assert len(generated) >= 8
    assert parse_request_id("x" * 200) != "x" * 200


def test_csp_policy_has_report_uri_and_self_script() -> None:
    assert "script-src 'self'" in CSP_POLICY
    assert "https://static.geetest.com" in CSP_POLICY
    assert "worker-src 'self' blob:" in CSP_POLICY
    assert "frame-src" in CSP_POLICY
    assert "report-uri /api/csp-report" in CSP_POLICY


def _get(path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get(path, headers=headers)

    return anyio.run(_call)


def test_health_response_has_security_headers_and_request_id() -> None:
    resp = _get("/health", headers={"X-Request-ID": "cid-42"})
    assert resp.headers.get("x-request-id") == "cid-42"
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "camera=()" in (resp.headers.get("permissions-policy") or "")
    csp = resp.headers.get("content-security-policy-report-only") or ""
    assert "report-uri /api/csp-report" in csp
    assert resp.headers.get("content-security-policy") is None


def test_csp_report_accepts_browser_content_type() -> None:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post(
                "/api/csp-report",
                content=b'{"csp-report":{"blocked-uri":"https://evil.example"}}',
                headers={"content-type": "application/csp-report"},
            )

    resp = anyio.run(_call)
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert resp.json().get("ok") is True


def test_robots_txt_disallows_all() -> None:
    resp = _get("/robots.txt")
    assert resp.status_code == 200
    assert "Disallow: /" in resp.text
    assert "User-agent: *" in resp.text

