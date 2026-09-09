"""熊猫 OCR 档位：从 RapidOCR yaml 摊开成套组合。"""

from app.services.ocr.paddle_profiles import (
    parse_onnx_paddle_profiles,
    normalize_paddle_profile,
    DEFAULT_PADDLE_PROFILE,
)

SAMPLE_TREE = {
    "onnxruntime": {
        "PP-OCRv5": {
            "det": {
                "ch_PP-OCRv5_det_mobile": {"model_dir": "http://x/ch_det_m.onnx"},
                "ch_PP-OCRv5_det_server": {"model_dir": "http://x/ch_det_s.onnx"},
            },
            "rec": {
                "ch_PP-OCRv5_rec_mobile": {"model_dir": "http://x/ch_rec_m.onnx"},
                "ch_PP-OCRv5_rec_server": {"model_dir": "http://x/ch_rec_s.onnx"},
                "korean_PP-OCRv5_rec_mobile": {"model_dir": "http://x/ko.onnx"},
                "en_PP-OCRv5_rec_mobile": {"model_dir": "http://x/en.onnx"},
            },
            "cls": {
                "ch_PP-LCNet_x0_25_textline_ori_cls_mobile": {"model_dir": "http://x/cls.onnx"},
            },
        },
        "PP-OCRv6": {
            "det": {
                "multi_PP-OCRv6_det_tiny": {"model_dir": "http://x/d6t.onnx"},
                "multi_PP-OCRv6_det_small": {"model_dir": "http://x/d6s.onnx"},
                "multi_PP-OCRv6_det_medium": {"model_dir": "http://x/d6m.onnx"},
            },
            "rec": {
                "multi_PP-OCRv6_rec_tiny": {"model_dir": "http://x/r6t.onnx"},
                "multi_PP-OCRv6_rec_small": {"model_dir": "http://x/r6s.onnx"},
                "multi_PP-OCRv6_rec_medium": {"model_dir": "http://x/r6m.onnx"},
            },
        },
        "PP-OCRv4": {
            "det": {
                "ch_PP-OCRv4_det_mobile": {"model_dir": "http://x/d4m.onnx"},
                "en_PP-OCRv3_det_mobile": {"model_dir": "http://x/d4e.onnx"},
            },
            "rec": {
                "ch_PP-OCRv4_rec_mobile": {"model_dir": "http://x/r4m.onnx"},
                "en_PP-OCRv4_rec_mobile": {"model_dir": "http://x/r4e.onnx"},
            },
        },
    },
    "openvino": {
        "PP-OCRv5": {
            "det": {"ch_PP-OCRv5_det_server": {"model_dir": "http://dup.onnx"}},
            "rec": {"ch_PP-OCRv5_rec_server": {"model_dir": "http://dup.onnx"}},
        }
    },
}


def test_parse_spreads_versions_and_langs() -> None:
    rows = parse_onnx_paddle_profiles(SAMPLE_TREE)
    ids = [row.id for row in rows]
    assert "v5_server" in ids
    assert "v5_mobile" in ids
    assert "v5_mobile_korean" in ids
    assert "v5_mobile_en" in ids
    assert "v6_tiny" in ids
    assert "v6_small" in ids
    assert "v6_medium" in ids
    assert "v4_mobile" in ids
    assert "v4_mobile_en" in ids
    assert ids.count("v5_server") == 1
    assert "v6_small_ch" not in ids
    assert "v6_small_en" not in ids
    korean = next(row for row in rows if row.id == "v5_mobile_korean")
    assert korean.det_lang == "ch"
    assert korean.rec_lang == "korean"
    assert korean.group == "PP-OCRv5"
    assert korean.label == "korean_PP-OCRv5_rec_mobile"
    assert next(row for row in rows if row.id == "v5_server").label == (
        "ch_PP-OCRv5_rec_server"
    )
    assert next(row for row in rows if row.id == "v6_medium").label == (
        "multi_PP-OCRv6_rec_medium"
    )


def test_parse_ignores_other_engines_and_cls() -> None:
    rows = parse_onnx_paddle_profiles(SAMPLE_TREE)
    assert all("openvino" not in row.id for row in rows)
    assert all(row.model_type != "cls" for row in rows)


def test_empty_tree() -> None:
    assert parse_onnx_paddle_profiles({}) == []
    assert parse_onnx_paddle_profiles(None) == []  # type: ignore[arg-type]


def test_normalize_aliases(monkeypatch) -> None:
    rows = parse_onnx_paddle_profiles(SAMPLE_TREE)
    monkeypatch.setattr(
        "app.services.ocr.paddle_profiles.list_paddle_profiles",
        lambda: rows,
    )
    assert normalize_paddle_profile("v5") == "v5_server"
    assert normalize_paddle_profile("v6medium") == "v6_medium"
    assert normalize_paddle_profile("v5_mobile_korean") == "v5_mobile_korean"
    assert normalize_paddle_profile("nope") == DEFAULT_PADDLE_PROFILE
