"""森空岛 API package (URL paths unchanged)."""
from fastapi import APIRouter, Depends

from app.api.skland import arknights, checkin, endfield
from app.core.platform_deps import require_feature

router = APIRouter(
    prefix="/skland",
    tags=["skland"],
    dependencies=[Depends(require_feature("skland"))],
)
for _sub in (checkin, arknights, endfield):
    router.include_router(_sub.router)

__all__ = ["router"]
