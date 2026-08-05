"""oauth ticket 服务单测（内存 SQLite Session 可选；此处测纯逻辑失败路径）。"""

import pytest

from app.services.oauth_ticket import consume_oauth_ticket


def test_consume_empty_raises() -> None:
    class DummySession:
        def get(self, *_a, **_k):
            return None

        def delete(self, *_a, **_k):
            return None

        def flush(self):
            return None

    with pytest.raises(ValueError, match="缺少"):
        consume_oauth_ticket(DummySession(), "")  # type: ignore[arg-type]
