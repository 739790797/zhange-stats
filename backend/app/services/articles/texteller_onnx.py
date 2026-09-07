"""用本地 ONNX 跑 TexTeller，不依赖 texteller / torch。"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from app.services.articles.errors import ArticleError

IMAGE_MEAN = 0.9545467
IMAGE_STD = 0.15394445
FIXED_IMG_SIZE = 448
DECODER_START_ID = 2
EOS_ID = 2
MAX_NEW_TOKENS = 256


def trim_white_border(rgb: np.ndarray) -> np.ndarray:
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("expect RGB")
    corners = [
        tuple(int(x) for x in rgb[0, 0]),
        tuple(int(x) for x in rgb[0, -1]),
        tuple(int(x) for x in rgb[-1, 0]),
        tuple(int(x) for x in rgb[-1, -1]),
    ]
    bg = np.array(Counter(corners).most_common(1)[0][0], dtype=np.int16)
    diff = np.abs(rgb.astype(np.int16) - bg).max(axis=2)
    mask = diff > 15
    if not mask.any():
        return rgb
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    return rgb[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]


def resize_hw(width: int, height: int) -> tuple[int, int]:
    scale = (FIXED_IMG_SIZE - 1) / max(1, min(width, height))
    if max(width, height) * scale > FIXED_IMG_SIZE:
        scale = FIXED_IMG_SIZE / max(width, height)
    next_w = max(1, min(FIXED_IMG_SIZE, int(round(width * scale))))
    next_h = max(1, min(FIXED_IMG_SIZE, int(round(height * scale))))
    return next_w, next_h


def preprocess_image(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    rgb = trim_white_border(rgb)
    gray = Image.fromarray(rgb).convert("L")
    next_w, next_h = resize_hw(gray.width, gray.height)
    gray = gray.resize((next_w, next_h), Image.Resampling.BICUBIC)
    arr = np.asarray(gray, dtype=np.float32) / 255.0
    arr = (arr - IMAGE_MEAN) / IMAGE_STD
    canvas = np.zeros((FIXED_IMG_SIZE, FIXED_IMG_SIZE), dtype=np.float32)
    canvas[:next_h, :next_w] = arr
    return canvas[None, None, :, :]


def onnxruntime_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


def decode_token_ids(root: Path, ids: list[int]) -> str:
    try:
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise ArticleError(503, "服务器未安装公式识别（tokenizers）") from exc
    path = root / "tokenizer.json"
    if not path.is_file():
        raise ArticleError(503, "公式识别 tokenizer 缺失")
    tokenizer = Tokenizer.from_file(str(path))
    return tokenizer.decode(ids, skip_special_tokens=True).strip()


class _OnnxRuntime:
    def __init__(self, root: Path) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        providers = ["CPUExecutionProvider"]
        self.encoder = ort.InferenceSession(
            str(root / "encoder_model.onnx"),
            opts,
            providers=providers,
        )
        self.decoder = ort.InferenceSession(
            str(root / "decoder_model.onnx"),
            opts,
            providers=providers,
        )
        self.tokenizer_dir = root

    def generate(self, pixels: np.ndarray) -> list[int]:
        hidden = self.encoder.run(None, {"pixel_values": pixels})[0]
        ids = [DECODER_START_ID]
        for _ in range(MAX_NEW_TOKENS):
            logits = self.decoder.run(
                None,
                {
                    "input_ids": np.asarray([ids], dtype=np.int64),
                    "encoder_hidden_states": hidden,
                },
            )[0]
            nxt = int(np.argmax(logits[0, -1]))
            ids.append(nxt)
            if nxt == EOS_ID:
                break
        return ids


_RUNTIME: _OnnxRuntime | None = None


def reset_onnx_runtime() -> None:
    global _RUNTIME
    _RUNTIME = None


def recognize_pil(image: Image.Image, root: Path) -> str:
    if not onnxruntime_available():
        raise ArticleError(503, "服务器未安装公式识别（onnxruntime）")
    if not (root / "encoder_model.onnx").is_file() or not (root / "decoder_model.onnx").is_file():
        raise ArticleError(503, "公式识别 ONNX 权重不完整")
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = _OnnxRuntime(root)
    pixels = preprocess_image(image)
    ids = _RUNTIME.generate(pixels)
    return decode_token_ids(root, ids)
