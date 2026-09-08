"""钥匙箱 OCR：切块尺寸、混淆映射、闭集匹配。不打 RapidOCR。"""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from threading import Event

from app.services.tarkov.key_ocr import (
    NamedRecognizer,
    OcrLine,
    OcrToken,
    RecognizeCancelled,
    TILE_BEST,
    TILE_MAX,
    TILE_MIN,
    box_to_xywh,
    confuse_variants,
    engine_family,
    families_agreed,
    collect_tile_tokens,
    flatten_key_catalog,
    map_tile_xywh,
    match_keys,
    parse_tokens,
    prepare_tile,
    progress_payload,
    recognize_image_bytes,
    repair_token,
    tile_geom,
    tile_rects,
    wants_progress_stream,
)


def test_1080_tiles_stay_in_orange_range() -> None:
    boxes = tile_rects(1920, 1080)
    assert boxes
    assert len(boxes) <= 8
    for _x, _y, w, h in boxes:
        side = max(w, h)
        assert TILE_MIN <= side <= TILE_MAX or side == TILE_BEST


def test_small_keybox_is_one_tile() -> None:
    boxes = tile_rects(480, 420)
    assert boxes == [(0, 0, 480, 420)]
    tile = prepare_tile(Image.new("RGB", (480, 420), (10, 10, 10)), boxes[0])
    assert tile.size[0] == tile.size[1]
    assert TILE_MIN <= tile.size[0] <= TILE_MAX


def test_repair_west_wing_and_color_cards() -> None:
    assert repair_token("画203") == "西203"
    assert repair_token("Wi222") == "西222"
    assert repair_token("空自") == "空白"
    assert repair_token("傅卡") == "黑卡"
    assert repair_token("蛇卡") == "红卡"


def test_il_confusion_maps_latin_codes() -> None:
    variants = confuse_variants("RB-I1")
    assert any("l" in item.lower() or "i" in item.lower() for item in variants)
    catalog = [
        {
            "id": "rb-il",
            "name": "RB-IL 钥匙",
            "short_name": "RB-IL",
            "icon_link": "",
        }
    ]
    hits = match_keys(["RB-I1"], catalog)
    assert [row.id for row in hits] == ["rb-il"]
    assert hits[0].confidence == "exact"


def test_parse_tokens_joins_stacked_color_glyphs() -> None:
    tokens = parse_tokens("绿\n卡\n画203\n10/10")
    assert "绿卡" in tokens
    assert "西203" in tokens
    assert "10" not in tokens
    assert "10/10" not in tokens


def test_closed_set_prefers_short_name_and_drops_ambiguous() -> None:
    catalog = [
        {"id": "a", "name": "宿舍 114 钥匙", "short_name": "114钥匙", "icon_link": ""},
        {"id": "b", "name": "宿舍 214 钥匙", "short_name": "214钥匙", "icon_link": ""},
        {"id": "c", "name": "实验室钥匙卡·蓝", "short_name": "蓝卡", "icon_link": "/blue.png"},
        {"id": "d", "name": "RB-BK 钥匙", "short_name": "RB-BK", "icon_link": ""},
    ]
    hits = match_keys(["蓝卡", "RB=BK", "114"], catalog)
    ids = [row.id for row in hits]
    assert "c" in ids
    assert "d" in ids
    assert "a" not in ids  # 纯数字不当短码


def test_west_203_does_not_steal_dorm_203() -> None:
    catalog = [
        {"id": "west", "name": "疗养院西楼 203 房间钥匙", "short_name": "西203", "icon_link": ""},
        {"id": "dorm", "name": "宿舍 203 钥匙", "short_name": "203钥匙", "icon_link": ""},
    ]
    hits = match_keys(["西203"], catalog)
    assert [row.id for row in hits] == ["west"]


def test_weaker_fuzzy_needs_second_family() -> None:
    catalog = [
        {"id": "cardinal", "name": "Cardinal 公寓钥匙", "short_name": "Cardinal", "icon_link": ""},
        {"id": "aspect", "name": "Aspect 钥匙", "short_name": "Aspect", "icon_link": ""},
    ]
    token = "Candinai"
    solo = match_keys(
        [OcrToken(text=token, engines=frozenset({"paddle"}))],
        catalog,
    )
    invert_only = match_keys(
        [OcrToken(text=token, engines=frozenset({"paddle", "paddle_inv"}))],
        catalog,
    )
    agreed = match_keys(
        [OcrToken(text=token, engines=frozenset({"paddle", "easyocr"}))],
        catalog,
    )
    assert all(row.id != "aspect" for row in [*solo, *invert_only, *agreed])
    assert [row.id for row in solo] == []
    assert [row.id for row in invert_only] == []
    assert [row.id for row in agreed] == ["cardinal"]


def test_engine_family_ignores_invert_channel() -> None:
    assert engine_family("paddle_inv") == "paddle"
    assert engine_family("easyocr") == "easyocr"
    assert families_agreed({"paddle", "paddle_inv"}) is False
    assert families_agreed({"paddle", "easyocr"}) is True
    assert families_agreed({"paddle", "paddle_inv", "tess"}) is True


def test_flatten_key_catalog_dedupes() -> None:
    rows = flatten_key_catalog(
        {
            "maps": [
                {
                    "keys": [
                        {"id": "a", "name": "A", "short_name": "A", "icon_link": "/a"},
                        {"id": "b", "name": "B", "short_name": "B", "icon_link": ""},
                    ]
                }
            ],
            "unbound": [
                {"id": "a", "name": "A2", "short_name": "A2", "icon_link": ""},
                {"id": "c", "name": "C", "short_name": "C", "icon_link": ""},
            ],
        }
    )
    assert [row["id"] for row in rows] == ["a", "b", "c"]


class _FakeEngine:
    def __init__(self, mapping: dict[str, list[str]]):
        self.mapping = mapping
        self.calls = 0

    def recognize(self, image: Image.Image) -> list[str]:
        self.calls += 1
        pixels = image.getpixel((0, 0))
        key = "inv" if pixels[0] > 128 else "norm"
        return list(self.mapping.get(key, self.mapping.get("norm", [])))


def test_recognize_image_bytes_uses_tiles_and_fake_engine() -> None:
    image = Image.new("RGB", (400, 360), (20, 20, 20))
    buf = BytesIO()
    image.save(buf, format="PNG")
    engine = _FakeEngine({"norm": ["蓝卡"], "inv": ["蓝卡", "RB-BK"]})
    catalog = [
        {"id": "blue", "name": "蓝卡", "short_name": "蓝卡", "icon_link": ""},
        {"id": "bk", "name": "RB-BK", "short_name": "RB-BK", "icon_link": ""},
    ]
    out = recognize_image_bytes(buf.getvalue(), catalog, recognizer=engine)
    ids = {row["id"] for row in out["matches"]}
    assert ids == {"blue", "bk"}
    assert out["tile_count"] == 1
    assert engine.calls >= 2
    assert out["overlay"]["width"] == 400
    assert out["overlay"]["height"] == 360
    assert out["overlay"]["boxes"] == []
    assert out["engines"] == ["paddle"]


class _ConstEngine:
    def __init__(self, texts: list[str]):
        self.texts = texts

    def recognize(self, image: Image.Image) -> list[str]:
        return list(self.texts)


def test_collect_tile_tokens_honors_cancel() -> None:
    called: list[int] = []

    class Boom(_ConstEngine):
        def recognize(self, image: Image.Image) -> list[str]:
            called.append(1)
            return super().recognize(image)

    cancel = Event()
    cancel.set()
    try:
        collect_tile_tokens(
            Image.new("RGB", (200, 200), "white"),
            [NamedRecognizer("paddle", Boom(["x"]))],
            cancel=cancel,
        )
    except RecognizeCancelled:
        assert called == []
        return
    raise AssertionError("expected RecognizeCancelled")


def test_wants_progress_stream_from_accept_or_header() -> None:
    assert wants_progress_stream("application/x-ndjson", "") is True
    assert wants_progress_stream("application/json", "1") is True
    assert wants_progress_stream("application/json", "true") is True
    assert wants_progress_stream("application/json", "") is False


def test_progress_payload_clamps_percent() -> None:
    row = progress_payload(" 第 1 块 ", {"percent": 140, "phase": "ocr"})
    assert row["event"] == "progress"
    assert row["message"] == "第 1 块"
    assert row["percent"] == 100
    assert row["phase"] == "ocr"


def test_recognize_reports_monotonic_progress() -> None:
    image = Image.new("RGB", (400, 360), (20, 20, 20))
    buf = BytesIO()
    image.save(buf, format="PNG")
    catalog = [
        {"id": "blue", "name": "蓝卡", "short_name": "蓝卡", "icon_link": ""},
    ]
    seen: list[tuple[str, int, str]] = []

    def on_progress(message: str, stats: dict) -> None:
        seen.append((message, int(stats["percent"]), str(stats.get("phase") or "")))

    out = recognize_image_bytes(
        buf.getvalue(),
        catalog,
        recognizers=[
            NamedRecognizer("paddle", _ConstEngine(["蓝卡"])),
            NamedRecognizer("easyocr", _ConstEngine(["蓝卡"])),
        ],
        progress=on_progress,
    )
    assert {row["id"] for row in out["matches"]} == {"blue"}
    assert seen
    percents = [percent for _msg, percent, _phase in seen]
    assert percents == sorted(percents)
    assert percents[0] >= 0
    assert percents[-1] == 100
    assert any("加载" in message and "熊猫 OCR" in message for message, _p, _ph in seen)
    assert any(phase == "ocr" for _m, _p, phase in seen)
    assert seen[-1][2] == "done"


def test_recognize_merges_two_engine_families() -> None:
    image = Image.new("RGB", (400, 360), (20, 20, 20))
    buf = BytesIO()
    image.save(buf, format="PNG")
    catalog = [
        {"id": "blue", "name": "蓝卡", "short_name": "蓝卡", "icon_link": ""},
        {"id": "bk", "name": "RB-BK", "short_name": "RB-BK", "icon_link": ""},
    ]
    out = recognize_image_bytes(
        buf.getvalue(),
        catalog,
        recognizers=[
            NamedRecognizer("paddle", _ConstEngine(["蓝卡"])),
            NamedRecognizer("easyocr", _ConstEngine(["RB-BK"])),
        ],
    )
    assert {row["id"] for row in out["matches"]} == {"blue", "bk"}
    assert out["engines"] == ["paddle", "easyocr"]


def test_box_to_xywh_from_quad() -> None:
    assert box_to_xywh([[10, 20], [90, 20], [90, 40], [10, 40]]) == (10, 20, 80, 20)
    assert box_to_xywh([10, 20, 80, 24]) == (10, 20, 80, 24)


def test_map_tile_xywh_undoes_pad_and_resize() -> None:
    geom = tile_geom((0, 0, 400, 360))
    assert geom.square_side == 400
    assert geom.prepared_side == 520
    mapped = map_tile_xywh(geom, 52, 26, 130, 39)
    assert mapped is not None
    assert mapped[0] == 40
    assert mapped[1] == 20
    assert mapped[2] == 100
    assert mapped[3] == 30
    assert map_tile_xywh(geom, 10, 468, 20, 20) is None


class _BoxedEngine:
    def recognize(self, image: Image.Image) -> list[OcrLine]:
        return [
            OcrLine(text="蓝卡", x=52, y=26, w=130, h=39),
            OcrLine(text="NoSuchKey99", x=80, y=200, w=100, h=20),
        ]


def test_recognize_maps_tile_boxes_onto_source() -> None:
    image = Image.new("RGB", (400, 360), (20, 20, 20))
    buf = BytesIO()
    image.save(buf, format="PNG")
    catalog = [
        {"id": "blue", "name": "蓝卡", "short_name": "蓝卡", "icon_link": ""},
        {"id": "bk", "name": "RB-BK", "short_name": "RB-BK", "icon_link": ""},
    ]
    out = recognize_image_bytes(buf.getvalue(), catalog, recognizer=_BoxedEngine())
    assert [row["id"] for row in out["matches"]] == ["blue"]
    boxes = {row["kind"]: row for row in out["overlay"]["boxes"]}
    assert set(boxes) == {"hit", "miss"}
    hit = boxes["hit"]
    assert hit["item_id"] == "blue"
    assert hit["label"] == "蓝卡"
    assert hit["x"] == 40
    assert hit["y"] == 20
    assert hit["width"] == 100
    assert hit["height"] == 30
    assert boxes["miss"]["label"] == "NoSuchKey99"


def test_easyocr_rows_become_lines() -> None:
    from app.services.tarkov.key_ocr_engine import _lines_from_easyocr

    rows = [([[10, 20], [90, 20], [90, 40], [10, 40]], "西203", 0.9)]
    lines = _lines_from_easyocr(rows)
    assert len(lines) == 1
    assert lines[0].text == "西203"
    assert lines[0].x == 10
    assert lines[0].w == 80
