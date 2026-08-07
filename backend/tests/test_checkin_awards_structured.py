"""塔吉多 / 追放结构化奖励解析与公共 award_item。"""

import app.services.exilium_client  # noqa: F401
import app.services.taygedo_client  # noqa: F401
from app.services.checkin_common import award_item, awards_text_from_items, loads_awards_json
from app.services.exilium_attendance import sign_in
from app.services.exilium_client import ExiliumCredentials
from app.services.taygedo_attendance import _awards_from_sign_payload, _item_award_dict


def test_award_item_and_text() -> None:
    item = award_item(name="合成玉", count=80, resource_id="4003", resource_type="DIAMOND_SHD")
    assert item["name"] == "合成玉"
    assert item["count"] == 80
    assert item["resource_id"] == "4003"
    assert awards_text_from_items([item]) == "合成玉x80"


def test_loads_awards_json_roundtrip() -> None:
    raw = '[{"name":"合成玉","count":80,"resource_type":"DIAMOND_SHD"}]'
    items = loads_awards_json(raw)
    assert items is not None
    assert items[0]["name"] == "合成玉"


def test_taygedo_sign_payload_structured() -> None:
    text, items = _awards_from_sign_payload(
        {
            "code": 0,
            "data": {
                "rewards": [
                    {"name": "异方结晶", "num": 100, "id": "r1", "type": "crystal"}
                ]
            },
        }
    )
    assert text == "异方结晶 x100"
    assert len(items) == 1
    assert items[0]["resource_id"] == "r1"
    assert items[0]["resource_type"] == "crystal"


def test_taygedo_item_award_nested() -> None:
    d = _item_award_dict({"reward": {"name": "金币", "count": 5, "id": "g"}})
    assert d is not None
    assert d["name"] == "金币"
    assert d["count"] == 5
    assert d["resource_id"] == "g"


def test_taygedo_item_award_icon_url() -> None:
    d = _item_award_dict(
        {
            "name": "井胃达人",
            "num": 3,
            "icon": "https://cdn.example.com/item.png",
        }
    )
    assert d is not None
    assert d["name"] == "井胃达人"
    assert d["count"] == 3
    assert d["icon_url"] == "https://cdn.example.com/item.png"


def test_taygedo_sign_payload_keeps_icon() -> None:
    text, items = _awards_from_sign_payload(
        {
            "code": 0,
            "data": {
                "rewards": [
                    {
                        "name": "井胃达人",
                        "num": 3,
                        "iconUrl": "https://cdn.example.com/j.png",
                    }
                ]
            },
        }
    )
    assert text == "井胃达人 x3"
    assert items[0]["icon_url"] == "https://cdn.example.com/j.png"


def test_exilium_sign_in_structured(monkeypatch) -> None:
    def fake_http_full(*_a, **_k):
        data = {
            "get_item_name": "补给箱",
            "get_item_count": 1,
            "get_exp": 10,
            "get_score": 20,
        }
        return data, {"code": 0, "data": data}

    monkeypatch.setattr("app.services.exilium_attendance._http_full", fake_http_full)
    creds = ExiliumCredentials(
        token="t",
        account_name="u",
        password="p",
        user_id="1",
        nickname="n",
    )
    result = sign_in(creds)
    assert result.status == "ok"
    assert result.awards_text is not None
    assert "补给箱" in (result.awards_text or "")
    assert result.awards is not None
    names = {a["name"] for a in result.awards}
    assert "补给箱" in names
    assert "经验" in names
    assert "积分" in names
