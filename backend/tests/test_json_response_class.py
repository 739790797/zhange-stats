"""JSON 成功响应不依赖 orjson（缺包时登录会 500）。"""

from fastapi.datastructures import DefaultPlaceholder
from fastapi.responses import JSONResponse, ORJSONResponse

from app.main import app


def test_app_default_response_does_not_require_orjson() -> None:
    cls = app.router.default_response_class
    if isinstance(cls, DefaultPlaceholder):
        cls = cls.value
    assert cls is not ORJSONResponse
    assert cls is JSONResponse
