"""库街区奖励文案解析（无网络）。"""

# 先加载 client，避免 attendance↔client 循环导入
import app.services.kujiequ.client  # noqa: F401
from app.services.kujiequ.attendance import _format_goods_rows


def test_format_goods_skips_generic_reward_name() -> None:
    text, items = _format_goods_rows([{"goodsName": "奖励", "goodsNum": 10}])
    assert text is None and items == []
    text, items = _format_goods_rows([{"goodsName": "reward", "goodsNum": 2}])
    assert text is None and items == []


def test_format_goods_uses_real_name() -> None:
    text, items = _format_goods_rows(
        [{"goodsName": "中级能源核心", "goodsNum": 2, "goodsId": "g1"}]
    )
    assert text == "中级能源核心×2"
    assert len(items) == 1
    assert items[0]["name"] == "中级能源核心"
    assert items[0]["count"] == 2
    assert items[0]["resource_id"] == "g1"


def test_format_goods_nested_list() -> None:
    rows = [
        {
            "sigInDate": "2026-08-05 00:01:00",
            "goodsList": [{"goodsName": "星声", "goodsNum": 20}],
        }
    ]
    text, items = _format_goods_rows(rows)
    assert text == "星声×20"
    assert items[0]["name"] == "星声"
    assert items[0]["count"] == 20


def test_format_goods_type_name_fallback() -> None:
    text, items = _format_goods_rows([{"typeName": "库洛石", "goodsNum": 10}])
    assert text == "库洛石×10"
    assert items[0]["name"] == "库洛石"
