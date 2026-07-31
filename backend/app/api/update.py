from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import require_admin
from app.models.user import User
from app.services import updater

router = APIRouter(prefix="/update", tags=["update"])


@router.get("/check")
def check_update(_: User = Depends(require_admin)) -> dict:
    try:
        return updater.check_for_update()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"检查更新失败: {exc}") from exc


@router.get("/status")
def update_status(_: User = Depends(require_admin)) -> dict:
    return updater.get_update_status()


@router.post("/do")
def do_update(_: User = Depends(require_admin)) -> dict:
    try:
        return updater.start_update()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"启动更新失败: {exc}") from exc
