"""把驱动层的整数越界映射成 4xx，其它同类异常照常 500。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError

# pysqlite 绑定超出 64 位的 Python int 时抛裸 OverflowError（SQLAlchemy 不包装）
_SQLITE_INT_OVERFLOW = "too large to convert to SQLite INTEGER"
# PyMySQL：写入越界数值 → (1264, "Out of range value for column ...")
_MYSQL_OUT_OF_RANGE = 1264


def _mysql_error_code(exc: DataError) -> int | None:
    orig = getattr(exc, "orig", None)
    args = getattr(orig, "args", None) or ()
    return args[0] if args and isinstance(args[0], int) else None


async def _integer_overflow(request: Request, exc: OverflowError) -> JSONResponse:
    if _SQLITE_INT_OVERFLOW in str(exc):
        return JSONResponse(status_code=404, content={"detail": "资源不存在"})
    raise exc


async def _db_data_error(request: Request, exc: DataError) -> JSONResponse:
    if _mysql_error_code(exc) == _MYSQL_OUT_OF_RANGE:
        return JSONResponse(status_code=422, content={"detail": "数值超出范围"})
    raise exc


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(OverflowError, _integer_overflow)
    app.add_exception_handler(DataError, _db_data_error)
