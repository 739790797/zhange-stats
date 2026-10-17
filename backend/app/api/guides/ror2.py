"""雨中冒险 2 图鉴。数据只来自 riskofrain2.wiki.gg。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.platform_deps import require_feature
from app.services.ror2.catalog import Ror2WikiError
from app.services.ror2.schemas import Ror2CatalogOut, Ror2SurvivorDetailOut
from app.services.ror2.survivor_page import Ror2MissingSurvivor
from app.services.ror2.wiki import translated_catalog, translated_detail

router = APIRouter(prefix="/ror2", tags=["guides"])


@router.get(
    "/catalog",
    response_model=Ror2CatalogOut,
    summary="雨中冒险2图鉴",
    description="只解析已审且原文未变的译文文件。没有译文的栏目是空的。原文仍由定时任务落入 guide_raws。",
    dependencies=[Depends(require_feature("guides.ror2"))],
)
def ror2_catalog(db: Session = Depends(get_db)) -> Ror2CatalogOut:
    try:
        return translated_catalog(db)
    except Ror2WikiError as exc:
        headers = {"Retry-After": "30"} if "同步中" in str(exc) else None
        raise HTTPException(status_code=503, detail="图鉴暂时拉不下来，请稍后再试", headers=headers) from None


@router.get(
    "/survivors/{name}",
    response_model=Ror2SurvivorDetailOut,
    summary="雨中冒险2幸存者",
    description="只解析该幸存者的译文文件。没有译文时段落是空的。",
    dependencies=[Depends(require_feature("guides.ror2"))],
)
def ror2_survivor(name: str, db: Session = Depends(get_db)) -> Ror2SurvivorDetailOut:
    try:
        return translated_detail(db, name)
    except Ror2MissingSurvivor:
        raise HTTPException(status_code=404, detail="没有这个幸存者") from None
    except Ror2WikiError as exc:
        headers = {"Retry-After": "30"} if "同步中" in str(exc) else None
        raise HTTPException(status_code=503, detail="图鉴暂时拉不下来，请稍后再试", headers=headers) from None
