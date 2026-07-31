from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import require_admin
from app.models.user import User
from app.services import updater

router = APIRouter(prefix="/update", tags=["update"])


def _safe_error(exc: Exception) -> str:
    text = str(exc).strip()
    if len(text) > 240:
        text = text[:240] + "…"
    return text or exc.__class__.__name__


@router.get("/check")
def check_update(_: User = Depends(require_admin)) -> dict:
    try:
        return updater.check_for_update()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"检查更新失败: {_safe_error(exc)}"
        ) from exc


@router.get("/status")
def update_status(_: User = Depends(require_admin)) -> dict:
    return updater.get_update_status()


@router.post("/do")
def do_update(_: User = Depends(require_admin)) -> dict:
    try:
        return updater.start_update()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=_safe_error(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"启动更新失败: {_safe_error(exc)}"
        ) from exc
