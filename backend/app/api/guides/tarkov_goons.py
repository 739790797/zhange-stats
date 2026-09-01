"""三狗社区位置 REST + WebSocket。"""

from fastapi import APIRouter, Depends, WebSocket

from app.api.guides.schemas import TarkovGoonTrackerOut
from app.core.deps import get_current_user
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services.tarkov import goon_tracker as goon_svc
from app.services.tarkov import goon_tracker_ws as goon_ws_svc

router = APIRouter()
_FEATURE = Depends(require_feature("guides.tarkov"))


@router.get(
    "/goons",
    response_model=TarkovGoonTrackerOut,
    dependencies=[_FEATURE],
)
def guides_tarkov_goons(user: User = Depends(get_current_user)) -> TarkovGoonTrackerOut:
    """当前模式三狗最近出现的地图；数据来自 Stammtisch 聚合。"""
    _ = user
    return TarkovGoonTrackerOut.model_validate(goon_svc.get_status())


@router.websocket("/goons/ws")
async def tarkov_goons_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await goon_ws_svc.run_goon_session(websocket)
