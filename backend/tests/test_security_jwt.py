from app.core.security import create_access_token, decode_access_token


def test_new_token_uses_user_id_sub(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.auth_config.get_access_token_expire_minutes",
        lambda: 60,
    )
    token = create_access_token("alice", user_id=42)
    principal = decode_access_token(token)
    assert principal is not None
    assert principal.user_id == 42
    assert principal.username == "alice"


def test_legacy_username_token_still_decodes(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.auth_config.get_access_token_expire_minutes",
        lambda: 60,
    )
    token = create_access_token("bob")
    principal = decode_access_token(token)
    assert principal is not None
    assert principal.user_id is None
    assert principal.username == "bob"


def test_invalid_token_returns_none() -> None:
    assert decode_access_token("not-a-jwt") is None
