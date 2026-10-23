"""雨中冒险 2 图鉴。数据只来自 riskofrain2.wiki.gg。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.platform_deps import require_feature
from app.services.ror2.catalog import Ror2WikiError
from app.services.ror2.schemas import Ror2CatalogResponse, Ror2SurvivorDetailResponse
from app.services.ror2.survivor_page import Ror2MissingSurvivor
from app.services.ror2.wiki import translated_catalog, translated_detail

router = APIRouter(prefix="/ror2", tags=["guides"])


@router.get(
    "/catalog",
    response_model=Ror2CatalogResponse,
    summary="雨中冒险2图鉴",
    description="Wiki 来源文本统一返回显示文本、Wiki 原文与真实 Weblate context；无匹配源单元时使用原文且不附令牌，只有已审核且原文指纹匹配的译文会替换显示文本。",
    dependencies=[Depends(require_feature("guides.ror2"))],
)
def ror2_catalog(db: Session = Depends(get_db)) -> Ror2CatalogResponse:
    try:
        return translated_catalog(db)
    except Ror2WikiError as exc:
        headers = {"Retry-After": "30"} if "同步中" in str(exc) else None
        raise HTTPException(status_code=503, detail="图鉴暂时拉不下来，请稍后再试", headers=headers) from None


@router.get(
    "/survivors/{name}",
    response_model=Ror2SurvivorDetailResponse,
    summary="雨中冒险2幸存者",
    description="从 Wiki 原文解析幸存者详情；已审核且原文指纹匹配的令牌展示译文，其余字段展示原文。",
    dependencies=[Depends(require_feature("guides.ror2"))],
)
def ror2_survivor(name: str, db: Session = Depends(get_db)) -> Ror2SurvivorDetailResponse:
    try:
        return translated_detail(db, name)
    except Ror2MissingSurvivor:
        raise HTTPException(status_code=404, detail="没有这个幸存者") from None
    except Ror2WikiError as exc:
        headers = {"Retry-After": "30"} if "同步中" in str(exc) else None
        raise HTTPException(status_code=503, detail="图鉴暂时拉不下来，请稍后再试", headers=headers) from None
