"""平台功能开关依赖。"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.platform_features import is_feature_enabled


def require_feature(feature_id: str):
    def _dep(db: Session = Depends(get_db)) -> None:
        if not is_feature_enabled(db, feature_id):
            raise HTTPException(status_code=403, detail="该功能未启用")

    return _dep
