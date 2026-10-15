"""游戏区 API（塔科夫攻略、雨中冒险 2、Minecraft 等）。"""
from fastapi import APIRouter

from app.api.guides import minecraft, ror2, tarkov

router = APIRouter(prefix="/guides", tags=["guides"])
router.include_router(tarkov.router)
router.include_router(ror2.router)
# 页面、侧栏和功能开关已停用。路由仍挂着，避免改 OpenAPI；
# guides.minecraft 不在功能树里，这些接口会拒绝。
router.include_router(minecraft.router)

__all__ = ["router"]
