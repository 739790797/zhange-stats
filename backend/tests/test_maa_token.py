from app.core.maa_token import resolve_maa_worker_token


def test_maa_worker_token_explicit_wins():
    assert resolve_maa_worker_token("  abc  ", "secret") == "abc"


def test_maa_worker_token_derives_from_secret():
    a = resolve_maa_worker_token("", "same-secret")
    b = resolve_maa_worker_token(None, "same-secret")
    assert a and a == b
    assert len(a) == 64


def test_maa_worker_token_empty_without_secret():
    assert resolve_maa_worker_token("", "") == ""
    assert resolve_maa_worker_token(None, None) == ""
