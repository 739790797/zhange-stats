"""用户附件登记：相对路径、流水号、写盘、存量回填。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.member import Member
from app.models.user import User, UserRole
from app.models.user_files import UserFile
from app.services.user_files.backfill import (
    backfill_all,
    backfill_namespace,
    ensure_user_files_registered,
    guess_content_type,
    owner_user_id_for_rel,
)
from app.services.user_files.store import (
    STATUS_DELETED,
    STATUS_STORED,
    UserFileError,
    format_serial,
    get_by_rel_path,
    get_by_serial,
    mark_deleted,
    normalize_rel_path,
    public_file_url,
    register_existing,
    replace_bytes,
    store_bytes,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine, tables=[User.__table__, Member.__table__, UserFile.__table__]
    )
    return sessionmaker(bind=engine)()


def test_format_serial() -> None:
    assert format_serial(1) == "UF00000001"
    assert format_serial(123) == "UF00000123"
    with pytest.raises(UserFileError):
        format_serial(0)


def test_normalize_rel_path_rejects_escape() -> None:
    assert normalize_rel_path("articles/2026/09/a.png") == "articles/2026/09/a.png"
    assert normalize_rel_path("articles\\2026\\09\\x.pdf") == "articles/2026/09/x.pdf"
    with pytest.raises(UserFileError):
        normalize_rel_path("../secret")
    with pytest.raises(UserFileError):
        normalize_rel_path("articles/../../etc/passwd")
    with pytest.raises(UserFileError):
        normalize_rel_path("/uploads/articles/a.png")


def test_public_file_url() -> None:
    assert public_file_url("articles/2026/09/ab.png") == "/uploads/articles/2026/09/ab.png"


def test_guess_content_type() -> None:
    assert guess_content_type("a.PNG") == "image/png"
    assert guess_content_type("note.tar.gz") == "application/gzip"
    assert guess_content_type("x.bin") is None


def test_store_bytes_registers_serial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.user_files.store.upload_root", lambda: tmp_path)
    db = _session()
    user = User(
        username="writer",
        display_name="作者",
        password_hash="x",
        role=UserRole.user,
    )
    db.add(user)
    db.flush()
    stored = store_bytes(
        db,
        namespace="articles",
        raw=b"%PDF-1.4\n%",
        ext=".pdf",
        original_name="r\\\\notes.pdf",
        content_type="application/pdf",
        owner_user_id=user.id,
        root=tmp_path,
    )
    assert stored.serial == "UF00000001"
    assert stored.url.startswith("/uploads/articles/")
    assert stored.url.endswith(".pdf")
    disk = tmp_path / stored.rel_path
    assert disk.is_file()
    assert disk.read_bytes().startswith(b"%PDF")
    row = get_by_serial(db, "uf00000001")
    assert row is not None
    assert row.owner_user_id == user.id
    assert row.original_name == "notes.pdf"
    assert row.namespace == "articles"
    assert row.visibility == "public"
    with pytest.raises(UserFileError):
        store_bytes(db, namespace="avatars", raw=b"x", ext=".jpg", root=tmp_path)


def test_store_unlinks_when_insert_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.user_files.store.upload_root", lambda: tmp_path)
    db = _session()

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr("app.services.user_files.store._insert_row", _boom)
    with pytest.raises(RuntimeError):
        store_bytes(db, namespace="articles", raw=b"hello", ext=".txt", root=tmp_path)
    leftover = list(tmp_path.rglob("*"))
    assert not any(p.is_file() for p in leftover)


def test_backfill_articles_nested_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.user_files.store.upload_root", lambda: tmp_path)
    monkeypatch.setattr("app.services.user_files.backfill.upload_root", lambda: tmp_path)
    (tmp_path / "articles" / "2026" / "09").mkdir(parents=True)
    (tmp_path / "articles" / "2026" / "08").mkdir(parents=True)
    new_file = tmp_path / "articles" / "2026" / "09" / "aabbcc.png"
    old_file = tmp_path / "articles" / "2026" / "08" / "old.jpg"
    new_file.write_bytes(b"png-bytes")
    old_file.write_bytes(b"jpg-bytes")
    db = _session()
    first = backfill_namespace(db, namespace="articles", root=tmp_path)
    assert first == {"added": 2, "skipped": 0}
    rows = db.query(UserFile).order_by(UserFile.rel_path).all()
    assert [row.rel_path for row in rows] == [
        "articles/2026/08/old.jpg",
        "articles/2026/09/aabbcc.png",
    ]
    assert rows[0].serial == "UF00000001"
    assert rows[0].owner_user_id is None
    assert get_by_serial(db, rows[1].serial) is not None
    second = backfill_namespace(db, namespace="articles", root=tmp_path)
    assert second == {"added": 0, "skipped": 2}
    assert db.query(UserFile).count() == 2


def _user(db: Session, username: str = "alice") -> User:
    user = User(
        username=username,
        display_name=username,
        password_hash="x",
        role=UserRole.user,
    )
    db.add(user)
    db.flush()
    return user


def test_replace_bytes_overwrites_same_serial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.user_files.store.upload_root", lambda: tmp_path)
    db = _session()
    user = _user(db)
    first = replace_bytes(
        db,
        namespace="avatars",
        rel_path="avatars/7.jpg",
        raw=b"jpeg-one",
        original_name="face.png",
        content_type="image/jpeg",
        owner_user_id=user.id,
        root=tmp_path,
    )
    assert first.serial == "UF00000001"
    assert first.url == "/uploads/avatars/7.jpg"
    disk = tmp_path / "avatars" / "7.jpg"
    assert disk.read_bytes() == b"jpeg-one"
    second = replace_bytes(
        db,
        namespace="avatars",
        rel_path="avatars/7.jpg",
        raw=b"jpeg-two-longer",
        original_name="next.jpg",
        content_type="image/jpeg",
        owner_user_id=user.id,
        root=tmp_path,
    )
    assert second.serial == first.serial
    assert db.query(UserFile).count() == 1
    row = get_by_rel_path(db, "avatars/7.jpg")
    assert row is not None
    assert row.size_bytes == len(b"jpeg-two-longer")
    assert row.original_name == "next.jpg"
    assert row.status == STATUS_STORED
    assert disk.read_bytes() == b"jpeg-two-longer"


def test_mark_deleted_then_replace_revives_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.user_files.store.upload_root", lambda: tmp_path)
    db = _session()
    replace_bytes(
        db,
        namespace="avatars",
        rel_path="avatars/3.jpg",
        raw=b"old",
        root=tmp_path,
    )
    row = mark_deleted(db, "avatars/3.jpg", root=tmp_path)
    assert row is not None
    assert row.status == STATUS_DELETED
    assert not (tmp_path / "avatars" / "3.jpg").exists()
    stored = replace_bytes(
        db,
        namespace="avatars",
        rel_path="avatars/3.jpg",
        raw=b"new",
        root=tmp_path,
    )
    assert stored.serial == row.serial
    revived = get_by_serial(db, stored.serial)
    assert revived is not None
    assert revived.status == STATUS_STORED
    assert (tmp_path / "avatars" / "3.jpg").read_bytes() == b"new"


def test_backfill_avatars_resolves_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.user_files.store.upload_root", lambda: tmp_path)
    monkeypatch.setattr("app.services.user_files.backfill.upload_root", lambda: tmp_path)
    db = _session()
    user = _user(db)
    member = Member(nickname="alice", user_id=user.id)
    db.add(member)
    db.flush()
    avatar = tmp_path / "avatars" / f"{member.id}.jpg"
    avatar.parent.mkdir(parents=True)
    avatar.write_bytes(b"jpg-bytes")
    orphan = tmp_path / "avatars" / "999.jpg"
    orphan.write_bytes(b"orphan")
    (tmp_path / "articles" / "2026" / "09").mkdir(parents=True)
    (tmp_path / "articles" / "2026" / "09" / "aabb.png").write_bytes(b"png")
    assert owner_user_id_for_rel(db, "avatars", f"avatars/{member.id}.jpg") == user.id
    assert owner_user_id_for_rel(db, "avatars", "avatars/999.jpg") is None
    stats = backfill_all(db, root=tmp_path)
    assert stats["avatars"] == {"added": 2, "skipped": 0}
    assert stats["articles"] == {"added": 1, "skipped": 0}
    owned = get_by_rel_path(db, f"avatars/{member.id}.jpg")
    assert owned is not None
    assert owned.owner_user_id == user.id
    assert owned.namespace == "avatars"
    leftover = get_by_rel_path(db, "avatars/999.jpg")
    assert leftover is not None
    assert leftover.owner_user_id is None
    again = backfill_namespace(db, namespace="avatars", root=tmp_path)
    assert again == {"added": 0, "skipped": 2}


def test_ensure_registers_and_fills_existing_avatar_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.user_files.store.upload_root", lambda: tmp_path)
    monkeypatch.setattr("app.services.user_files.backfill.upload_root", lambda: tmp_path)
    db = _session()
    user = _user(db)
    member = Member(nickname="alice", user_id=user.id)
    db.add(member)
    db.flush()
    rel = f"avatars/{member.id}.jpg"
    disk = tmp_path / rel
    disk.parent.mkdir(parents=True)
    disk.write_bytes(b"jpg-bytes")
    register_existing(
        db,
        namespace="avatars",
        rel_path=rel,
        original_name=f"{member.id}.jpg",
        content_type="image/jpeg",
        size_bytes=9,
        owner_user_id=None,
        commit=True,
    )
    assert get_by_rel_path(db, rel).owner_user_id is None
    stats = ensure_user_files_registered(db, root=tmp_path)
    assert stats["avatars"] == {"added": 0, "skipped": 1}
    assert get_by_rel_path(db, rel).owner_user_id == user.id
