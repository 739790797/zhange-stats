"""游戏区 API（塔科夫攻略、Minecraft 等）。"""
from fastapi import APIRouter

from app.api.guides import minecraft, tarkov

router = APIRouter(prefix="/guides", tags=["guides"])
router.include_router(tarkov.router)
router.include_router(minecraft.router)

__all__ = ["router"]
