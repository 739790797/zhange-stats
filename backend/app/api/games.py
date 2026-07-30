from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.game import Game
from app.models.user import User
from app.schemas import GameCreate, GameOut, GameUpdate

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=list[GameOut])
def list_games(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Game]:
    return db.query(Game).order_by(Game.id.asc()).all()


@router.get("/{game_id}", response_model=GameOut)
def get_game(
    game_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Game:
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    return game


@router.post("", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def create_game(
    body: GameCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Game:
    exists = db.query(Game).filter(Game.name == body.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="游戏名称已存在")
    game = Game(name=body.name, platform=body.platform, icon_url=body.icon_url)
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


@router.patch("/{game_id}", response_model=GameOut)
def update_game(
    game_id: int,
    body: GameUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Game:
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        conflict = (
            db.query(Game)
            .filter(Game.name == data["name"], Game.id != game_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail="游戏名称已存在")
    for key, value in data.items():
        setattr(game, key, value)
    db.commit()
    db.refresh(game)
    return game


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(
    game_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    db.delete(game)
    db.commit()
