from app.core.http_cache import catalog_etag, catalog_freshness, etag_matches


def test_catalog_etag_stable_for_same_parts() -> None:
    assert catalog_etag("ammo", "pvp", "2026-01-01") == catalog_etag(
        "ammo", "pvp", "2026-01-01"
    )


def test_catalog_etag_changes_when_synced_at_changes() -> None:
    assert catalog_etag("ammo", "pvp", "a") != catalog_etag("ammo", "pvp", "b")


def test_etag_matches_weak_and_strong() -> None:
    etag = catalog_etag("maps", "pvp")
    assert etag_matches(etag, etag)
    assert etag_matches(f"W/{etag.removeprefix('W/')}", etag)
    assert etag_matches(f"{etag}, W/\"other\"", etag)
    assert not etag_matches("", etag)
    assert not etag_matches("*", etag)
    assert not etag_matches('W/"deadbeef"', etag)


class _FakeRequest:
    def __init__(self, if_none_match: str = "") -> None:
        self.headers = {"if-none-match": if_none_match}


def test_catalog_freshness_miss_does_not_return_304() -> None:
    etag, hit = catalog_freshness(_FakeRequest(""), "ammo", "pvp")
    assert hit is None
    assert etag == catalog_etag("ammo", "pvp")


def test_catalog_freshness_hit_returns_304() -> None:
    etag = catalog_etag("ammo", "pvp")
    got, hit = catalog_freshness(_FakeRequest(etag), "ammo", "pvp")
    assert got == etag
    assert hit is not None
    assert hit.status_code == 304
    assert hit.headers["etag"] == etag


def test_catalog_etag_stable_for_same_parts() -> None:
    assert catalog_etag("ammo", "pvp", "2026-01-01") == catalog_etag(
        "ammo", "pvp", "2026-01-01"
    )


def test_catalog_etag_changes_when_synced_at_changes() -> None:
    assert catalog_etag("ammo", "pvp", "a") != catalog_etag("ammo", "pvp", "b")


def test_etag_matches_weak_and_strong() -> None:
    etag = catalog_etag("maps", "pvp")
    assert etag_matches(etag, etag)
    assert etag_matches(f"W/{etag.removeprefix('W/')}", etag)
    assert etag_matches(f"{etag}, W/\"other\"", etag)
    assert not etag_matches("", etag)
    assert not etag_matches("*", etag)
    assert not etag_matches('W/"deadbeef"', etag)
