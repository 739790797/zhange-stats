"""平台凭证（bind.credentials_enc 里的 JSON）读写。

- 同进程同成员串行换票：轮换型 refresh token 并发刷新会把对方刚换到的票作废。
- 凭证没变不写；变了按读出时的密文 CAS，期间被重新绑定或别处先换票时放弃本次写入。
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Generic, Protocol, TypeVar

from sqlalchemy.orm import Session

from app.core.crypto_secret import encrypt_secret
from app.core.timeutil import now_naive

logger = logging.getLogger(__name__)


class _Creds(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


C = TypeVar("C", bound=_Creds)

_locks: dict[tuple[str, int], threading.RLock] = {}
_locks_guard = threading.Lock()


def credential_lock(platform: str, member_id: int) -> threading.RLock:
    key = (platform, int(member_id))
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = _locks[key] = threading.RLock()
        return lock


@dataclass(frozen=True)
class StoredCreds(Generic[C]):
    """凭证 + 读出时的密文与明文快照（平台函数会原地改凭证对象，只能和快照比）。"""

    creds: C
    loaded_enc: str
    loaded: dict[str, Any]

    @classmethod
    def snapshot(cls, bind: Any, creds: C) -> StoredCreds[C]:
        return cls(
            creds=creds,
            loaded_enc=bind.credentials_enc or "",
            loaded=dict(creds.to_dict()),
        )

    def with_creds(self, creds: C) -> StoredCreds[C]:
        return replace(self, creds=creds)


def store_creds_if_changed(
    db: Session,
    bind: Any,
    stored: StoredCreds[C],
    *,
    extra: dict[str, Any] | None = None,
) -> StoredCreds[C]:
    """调用方负责 commit。CAS 落空（库里已是别人写的凭证）时不写，返回原快照。"""
    current = dict(stored.creds.to_dict())
    if current == stored.loaded:
        return stored
    model = type(bind)
    new_enc = encrypt_secret(json.dumps(current, ensure_ascii=False))
    values: dict[str, Any] = {
        "credentials_enc": new_enc,
        "updated_at": now_naive(),
        **(extra or {}),
    }
    updated = (
        db.query(model)
        .filter(model.id == bind.id, model.credentials_enc == stored.loaded_enc)
        .update(values, synchronize_session=False)
    )
    db.expire(bind, list(values))
    if not updated:
        logger.debug(
            "%s credentials changed elsewhere, keep the newer row member_id=%s",
            model.__name__,
            bind.member_id,
        )
        return stored
    return StoredCreds(creds=stored.creds, loaded_enc=new_enc, loaded=current)


def refresh_creds_locked(
    db: Session,
    bind: Any,
    *,
    platform: str,
    load: Callable[[Any], C],
    refresh: Callable[[C], C],
    extra: Callable[[C], dict[str, Any]] | None = None,
) -> StoredCreds[C]:
    """进锁后开新事务重读（别的线程可能刚换过票）；打上游前交还连接；变了才 CAS 写回。"""
    with credential_lock(platform, bind.member_id):
        db.commit()
        db.refresh(bind)
        stored = StoredCreds.snapshot(bind, load(bind))
        db.commit()
        stored = stored.with_creds(refresh(stored.creds))
        stored = store_creds_if_changed(
            db, bind, stored, extra=extra(stored.creds) if extra else None
        )
        db.commit()
    return stored
