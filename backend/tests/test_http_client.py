from app.core.http_client import CONNECT_TIMEOUT_SEC, _timeout, http_download, http_stream


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


def test_http_download_streams_progress(monkeypatch) -> None:
    class _Resp:
        status_code = 200
        headers = {"content-length": "5"}

        def iter_bytes(self, chunk_size=None):  # noqa: ANN001
            yield b"he"
            yield b"llo"

        def read(self):
            return b""

    class _CM:
        def __enter__(self):
            return _Resp()

        def __exit__(self, *_a):
            return False

    class _Client:
        def stream(self, *_a, **_k):
            return _CM()

    monkeypatch.setattr("app.core.http_client.get_http_client", lambda: _Client())
    seen: list[tuple[int, int | None]] = []
    status, body, _headers = http_download(
        "GET",
        "https://example.test/x",
        on_bytes=lambda n, total: seen.append((n, total)),
    )
    assert status == 200
    assert body == b"hello"
    assert seen[0] == (0, 5)
    assert seen[-1] == (5, 5)


def test_http_stream_yields_response(monkeypatch) -> None:
    class _Resp:
        status_code = 200
        content = b"ok"

        def iter_bytes(self, chunk_size=None):  # noqa: ANN001
            yield b"ok"

    class _CM:
        def __enter__(self):
            return _Resp()

        def __exit__(self, *_a):
            return False

    class _Client:
        def stream(self, method, url, **_k):
            assert method == "GET"
            assert url == "https://example.test/file"
            return _CM()

    monkeypatch.setattr("app.core.http_client.get_http_client", lambda: _Client())
    with http_stream("GET", "https://example.test/file", timeout=300, connect=20) as resp:
        assert resp.status_code == 200
        assert b"".join(resp.iter_bytes()) == b"ok"
