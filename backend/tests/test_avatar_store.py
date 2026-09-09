"""站内头像：裁剪后覆盖写并登记 user_files。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.member import Member
from app.models.user import User, UserRole
from app.models.user_files import UserFile
from app.services.avatar_store import (
    AVATAR_SIZE,
    delete_avatar_file,
    encode_avatar_jpeg,
    is_custom_avatar_url,
    save_avatar_bytes,
)
from app.services.user_files.store import STATUS_DELETED, get_by_rel_path


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine, tables=[User.__table__, Member.__table__, UserFile.__table__]
    )
    return sessionmaker(bind=engine)()


def _png_bytes(width: int = 40, height: int = 20) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def test_encode_avatar_jpeg_is_square() -> None:
    jpeg = encode_avatar_jpeg(_png_bytes(40, 20))
    img = Image.open(io.BytesIO(jpeg))
    assert img.format == "JPEG"
    assert img.size == (AVATAR_SIZE, AVATAR_SIZE)


def test_save_avatar_bytes_registers_and_overwrites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.user_files.store.upload_root", lambda: tmp_path)
    db = _session()
    user = User(
        username="alice",
        display_name="alice",
        password_hash="x",
        role=UserRole.user,
    )
    db.add(user)
    db.flush()
    member = Member(nickname="alice", user_id=user.id)
    db.add(member)
    db.flush()

    url = save_avatar_bytes(
        db,
        member.id,
        _png_bytes(),
        owner_user_id=user.id,
        original_name="face.png",
    )
    assert is_custom_avatar_url(url)
    assert f"/uploads/avatars/{member.id}.jpg" in url
    rel = f"avatars/{member.id}.jpg"
    row = get_by_rel_path(db, rel)
    assert row is not None
    assert row.serial == "UF00000001"
    assert row.owner_user_id == user.id
    assert row.content_type == "image/jpeg"
    disk = tmp_path / rel
    assert disk.is_file()
    with Image.open(disk) as img:
        assert img.size == (AVATAR_SIZE, AVATAR_SIZE)

    save_avatar_bytes(
        db,
        member.id,
        _png_bytes(80, 80),
        owner_user_id=user.id,
        original_name="next.png",
    )
    assert db.query(UserFile).count() == 1
    db.refresh(row)
    assert row.serial == "UF00000001"
    assert row.original_name == "next.png"

    delete_avatar_file(member.id, db=db)
    assert row.status == STATUS_DELETED
    assert get_by_rel_path(db, rel) is row
    assert not disk.exists()
