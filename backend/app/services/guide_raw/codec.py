"""图鉴 raw 正文：小文档明文，大文档 gz1:（gzip 后再 base64）。

塔科夫各表和 ``guide_raws`` 共用这一份，读旧明文行不用迁移。
"""

from __future__ import annotations

import base64
import gzip
import logging

log = logging.getLogger("zhange.guide_raw")

GZIP_PREFIX = "gz1:"
GZIP_MIN_BYTES = 4 * 1024 * 1024
PACKET_BUDGET = 12 * 1024 * 1024


class RawTooLarge(Exception):
    """压缩后仍超过数据库单包上限。库里的旧行不要覆盖。"""


def pack_raw_text(
    text: str,
    *,
    min_bytes: int = GZIP_MIN_BYTES,
    packet_budget: int = PACKET_BUDGET,
) -> str:
    """大正文压到单包预算以内。小文档保持明文，方便直接看库。"""
    encoded = text.encode("utf-8")
    if len(encoded) < min_bytes:
        return text
    packed = _gzip_b64(encoded, compresslevel=6)
    if len(packed.encode("utf-8")) >= len(encoded):
        packed = text
    if len(packed.encode("utf-8")) > packet_budget and packed != text:
        tighter = _gzip_b64(encoded, compresslevel=9)
        if len(tighter) < len(packed):
            packed = tighter
    stored_bytes = len(packed.encode("utf-8"))
    if stored_bytes > packet_budget:
        raise RawTooLarge("图鉴 raw 压缩后仍超过数据库单包上限，已中止写入，库里的旧数据还在")
    if packed.startswith(GZIP_PREFIX):
        log.debug("guide raw packed %s bytes -> %s", len(encoded), stored_bytes)
    return packed


def unpack_raw_text(stored: str) -> str:
    if not stored.startswith(GZIP_PREFIX):
        return stored
    try:
        blob = base64.b64decode(stored[len(GZIP_PREFIX) :], validate=True)
        return gzip.decompress(blob).decode("utf-8")
    except (OSError, ValueError, EOFError, UnicodeDecodeError) as exc:
        raise ValueError("invalid gz1 raw") from exc


def _gzip_b64(encoded: bytes, *, compresslevel: int) -> str:
    blob = gzip.compress(encoded, compresslevel=compresslevel, mtime=0)
    return GZIP_PREFIX + base64.b64encode(blob).decode("ascii")
