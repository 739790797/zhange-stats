from app.core.http_client import CONNECT_TIMEOUT_SEC, _timeout


def test_connect_timeout_capped() -> None:
    t = _timeout(20)
    assert t.connect == CONNECT_TIMEOUT_SEC
    assert t.read == 20


def test_short_read_also_caps_connect() -> None:
    t = _timeout(2)
    assert t.connect == 2
    assert t.read == 2
