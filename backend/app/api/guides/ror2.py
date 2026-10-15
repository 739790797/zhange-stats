"""雨中冒险 2 图鉴。数据只来自 riskofrain2.wiki.gg。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.platform_deps import require_feature
from app.services.ror2.catalog import Ror2WikiError
from app.services.ror2.schemas import Ror2CatalogOut
from app.services.ror2.wiki import get_catalog

router = APIRouter(prefix="/ror2", tags=["guides"])


@router.get(
    "/catalog",
    response_model=Ror2CatalogOut,
    summary="雨中冒险2图鉴",
    description="道具、装备、幸存者、怪物、无人机、环境、成就、可交互物、神器。Wiki 模块先落入 guide_raws，再解析展示。库空时冷启动回源。",
    dependencies=[Depends(require_feature("guides.ror2"))],
)
def ror2_catalog(db: Session = Depends(get_db)) -> Ror2CatalogOut:
    try:
        return get_catalog(db)
    except Ror2WikiError as exc:
        headers = {"Retry-After": "30"} if "同步中" in str(exc) else None
        raise HTTPException(status_code=503, detail="图鉴暂时拉不下来，请稍后再试", headers=headers) from None
