"""库街区奖励文案解析（无网络）。"""

# 先加载 client，避免 attendance↔client 循环导入
import app.services.kujiequ_client  # noqa: F401
from app.services.kujiequ_attendance import _format_goods_rows


def test_format_goods_skips_generic_reward_name() -> None:
    assert _format_goods_rows([{"goodsName": "奖励", "goodsNum": 10}]) is None
    assert _format_goods_rows([{"goodsName": "reward", "goodsNum": 2}]) is None


def test_format_goods_uses_real_name() -> None:
    assert _format_goods_rows([{"goodsName": "中级能源核心", "goodsNum": 2}]) == (
        "中级能源核心×2"
    )


def test_format_goods_nested_list() -> None:
    rows = [
        {
            "sigInDate": "2026-08-05 00:01:00",
            "goodsList": [{"goodsName": "星声", "goodsNum": 20}],
        }
    ]
    assert _format_goods_rows(rows) == "星声×20"


def test_format_goods_type_name_fallback() -> None:
    assert (
        _format_goods_rows([{"typeName": "库洛石", "goodsNum": 10}]) == "库洛石×10"
    )
