from fastapi import APIRouter, Depends

from app.api.skland import arknights, checkin, endfield, game_events
from app.core.platform_deps import require_feature

router = APIRouter(
    prefix="/skland",
    tags=["skland"],
    dependencies=[Depends(require_feature("skland"))],
)
for _sub in (checkin, arknights, endfield, game_events):
    router.include_router(_sub.router)

__all__ = ["router"]
