"""攻略区 API。"""
from fastapi import APIRouter

from app.api.guides import tarkov

router = APIRouter(prefix="/guides", tags=["guides"])
router.include_router(tarkov.router)

__all__ = ["router"]
