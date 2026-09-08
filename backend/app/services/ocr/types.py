"""共享 OCR 类型。业务侧（切块、闭集匹配）不要放这里。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from PIL import Image


class OcrError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class OcrLine:
    text: str
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


class OcrEngine(Protocol):
    def recognize(self, image: Image.Image) -> Sequence[str] | Sequence[OcrLine]:
        """识别一张已准备好的 RGB 图，返回文本行（可带框）。"""


@dataclass(frozen=True)
class NamedEngine:
    name: str
    engine: OcrEngine
