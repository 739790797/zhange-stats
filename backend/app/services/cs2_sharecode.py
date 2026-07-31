"""CS2 / CSGO 对局分享码编解码。"""

from __future__ import annotations

import re
from dataclasses import dataclass

_DICTIONARY = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"
_DICT_LEN = len(_DICTIONARY)
_LOOKUP = {c: i for i, c in enumerate(_DICTIONARY)}
_SHARE_RE = re.compile(
    r"^CSGO-([A-Za-z0-9]{5})-([A-Za-z0-9]{5})-([A-Za-z0-9]{5})-"
    r"([A-Za-z0-9]{5})-([A-Za-z0-9]{5})$"
)


@dataclass(frozen=True)
class DecodedShareCode:
    match_id: int
    outcome_id: int
    token: int

    @property
    def match_id_str(self) -> str:
        return str(self.match_id)

    @property
    def outcome_id_str(self) -> str:
        return str(self.outcome_id)


def normalize_share_code(raw: str) -> str:
    text = (raw or "").strip().replace(" ", "")
    if not text:
        raise ValueError("分享码不能为空")
    if text.upper().startswith("CSGO-"):
        text = "CSGO-" + text.split("-", 1)[1]
    else:
        text = "CSGO-" + text
    if not _SHARE_RE.match(text):
        raise ValueError("分享码格式无效，应为 CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
    return text


def decode_share_code(raw: str) -> DecodedShareCode:
    code = normalize_share_code(raw)
    body = code[5:].replace("-", "")
    if len(body) != 25:
        raise ValueError("分享码长度无效")

    num = 0
    for ch in reversed(body):
        if ch not in _LOOKUP:
            raise ValueError(f"分享码含非法字符: {ch}")
        num = num * _DICT_LEN + _LOOKUP[ch]

    match_id = num & ((1 << 64) - 1)
    num >>= 64
    outcome_id = num & ((1 << 64) - 1)
    num >>= 64
    token = num & ((1 << 16) - 1)
    return DecodedShareCode(match_id=match_id, outcome_id=outcome_id, token=token)


def is_share_code(raw: str) -> bool:
    try:
        normalize_share_code(raw)
        return True
    except ValueError:
        return False
