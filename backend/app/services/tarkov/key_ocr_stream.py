"""钥匙箱识别逐步进度（NDJSON）：识别在工作线程跑，事件循环只读队列，Session 不进线程。"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any

from PIL import Image

from app.services.ocr.types import OcrError
from app.services.tarkov import key_ocr

logger = logging.getLogger("zhange.ocr")

POLL_SEC = 0.35

SerializeResult = Callable[[dict[str, Any]], dict[str, Any]]
IsDisconnected = Callable[[], Awaitable[bool]]

_EMPTY = object()


def start_recognize_stream(
    image: Image.Image,
    catalog: list[dict[str, str]],
    recognizers: Sequence[key_ocr.NamedRecognizer],
    *,
    serialize: SerializeResult,
    is_disconnected: IsDisconnected,
) -> AsyncIterator[str]:
    """调用方须已占到识别槽；工作线程结束时归还。客户端断开后在下一刀切块前停。"""
    events: queue.Queue[dict[str, Any] | None] = queue.Queue()
    cancel = threading.Event()

    def on_progress(message: str, stats: dict[str, Any]) -> None:
        events.put(key_ocr.progress_payload(message, stats))

    def work() -> None:
        try:
            result = key_ocr.recognize_image(
                image,
                catalog,
                recognizers=recognizers,
                progress=on_progress,
                cancel=cancel,
            )
            events.put({"event": "done", "result": serialize(result)})
        except key_ocr.RecognizeCancelled:
            pass
        except OcrError as exc:
            events.put(
                {
                    "event": "error",
                    "status_code": exc.status_code,
                    "detail": exc.message,
                }
            )
        except Exception:
            logger.exception("tarkov key ocr stream failed")
            events.put(
                {
                    "event": "error",
                    "status_code": 500,
                    "detail": "识别失败，请重试",
                }
            )
        finally:
            key_ocr.end_recognize()
            events.put(None)

    def pull() -> dict[str, Any] | None | object:
        try:
            return events.get(timeout=POLL_SEC)
        except queue.Empty:
            return _EMPTY

    threading.Thread(target=work, name="tarkov-key-ocr", daemon=True).start()

    async def lines() -> AsyncIterator[str]:
        try:
            while True:
                if await is_disconnected():
                    break
                item = await asyncio.to_thread(pull)
                if item is _EMPTY:
                    continue
                if item is None:
                    break
                yield json.dumps(item, ensure_ascii=False) + "\n"
        finally:
            # 断开、任务取消或响应提前 aclose 都要让工作线程停下、早点还槽。
            cancel.set()

    return lines()
