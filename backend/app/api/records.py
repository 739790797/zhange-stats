from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.game import Game
from app.models.match_record import MatchRecord, MatchResult, MatchSource
from app.models.member import Member
from app.models.user import User
from app.schemas import RecordCreate, RecordOut, RecordUpdate

router = APIRouter(prefix="/records", tags=["records"])


def _parse_result(value: str) -> MatchResult:
    try:
        return MatchResult(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"无效的 result: {value}") from exc


def _parse_source(value: str) -> MatchSource:
    try:
        return MatchSource(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"无效的 source: {value}") from exc


def _to_out(record: MatchRecord, nickname: str | None = None, game_name: str | None = None) -> RecordOut:
    return RecordOut(
        id=record.id,
        member_id=record.member_id,
        game_id=record.game_id,
        played_at=record.played_at,
        result=record.result.value if hasattr(record.result, "value") else str(record.result),
        mode=record.mode,
        stats=record.stats,
        raw_text=record.raw_text,
        source=record.source.value if hasattr(record.source, "value") else str(record.source),
        created_at=record.created_at,
        member_nickname=nickname or (record.member.nickname if record.member else None),
        game_name=game_name or (record.game.name if record.game else None),
    )


@router.get("", response_model=list[RecordOut])
def list_records(
    member_id: int | None = None,
    game_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RecordOut]:
    q = (
        db.query(MatchRecord, Member.nickname, Game.name)
        .join(Member, MatchRecord.member_id == Member.id)
        .join(Game, MatchRecord.game_id == Game.id)
    )
    if member_id is not None:
        q = q.filter(MatchRecord.member_id == member_id)
    if game_id is not None:
        q = q.filter(MatchRecord.game_id == game_id)
    if date_from is not None:
        q = q.filter(MatchRecord.played_at >= date_from)
    if date_to is not None:
        q = q.filter(MatchRecord.played_at <= date_to)
    rows = q.order_by(MatchRecord.played_at.desc()).limit(limit).all()
    return [_to_out(r, nickname, game_name) for r, nickname, game_name in rows]


@router.get("/{record_id}", response_model=RecordOut)
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RecordOut:
    row = (
        db.query(MatchRecord, Member.nickname, Game.name)
        .join(Member, MatchRecord.member_id == Member.id)
        .join(Game, MatchRecord.game_id == Game.id)
        .filter(MatchRecord.id == record_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="战绩不存在")
    record, nickname, game_name = row
    return _to_out(record, nickname, game_name)


@router.post("", response_model=RecordOut, status_code=status.HTTP_201_CREATED)
def create_record(
    body: RecordCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RecordOut:
    member = db.query(Member).filter(Member.id == body.member_id).first()
    if not member:
        raise HTTPException(status_code=400, detail="成员不存在")
    game = db.query(Game).filter(Game.id == body.game_id).first()
    if not game:
        raise HTTPException(status_code=400, detail="游戏不存在")

    record = MatchRecord(
        member_id=body.member_id,
        game_id=body.game_id,
        played_at=body.played_at,
        result=_parse_result(body.result),
        mode=body.mode,
        stats=body.stats,
        raw_text=body.raw_text,
        source=_parse_source(body.source),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_out(record, member.nickname, game.name)


@router.patch("/{record_id}", response_model=RecordOut)
def update_record(
    record_id: int,
    body: RecordUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RecordOut:
    record = db.query(MatchRecord).filter(MatchRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="战绩不存在")
    data = body.model_dump(exclude_unset=True)
    if "result" in data and data["result"] is not None:
        data["result"] = _parse_result(data["result"])
    if "member_id" in data:
        member = db.query(Member).filter(Member.id == data["member_id"]).first()
        if not member:
            raise HTTPException(status_code=400, detail="成员不存在")
    if "game_id" in data:
        game = db.query(Game).filter(Game.id == data["game_id"]).first()
        if not game:
            raise HTTPException(status_code=400, detail="游戏不存在")
    for key, value in data.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return _to_out(record)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> None:
    record = db.query(MatchRecord).filter(MatchRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="战绩不存在")
    db.delete(record)
    db.commit()
