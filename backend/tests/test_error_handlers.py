"""驱动层整数越界：SQLite 路径参数超 64 位回 404，MySQL 1264 回 422，其它溢出仍 500。"""

from __future__ import annotations

import pymysql
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DataError

from app.core.error_handlers import install_error_handlers


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    engine = create_engine("sqlite:///:memory:")

    @app.get("/members/{member_id}")
    def get_member(member_id: int) -> dict:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT :id AS id"), {"id": member_id}).first()
        return {"id": row.id}

    @app.get("/mysql-out-of-range")
    def mysql_out_of_range() -> dict:
        raise DataError("INSERT ...", {}, pymysql.err.DataError(1264, "Out of range value for column 'id' at row 1"))

    @app.get("/other-overflow")
    def other_overflow() -> dict:
        raise OverflowError("date value out of range")

    return app


def test_sqlite_integer_overflow_is_404() -> None:
    client = TestClient(_app())
    assert client.get("/members/9223372036854775807").status_code == 200
    resp = client.get("/members/9223372036854775808")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "资源不存在"}


def test_mysql_out_of_range_is_422() -> None:
    resp = TestClient(_app()).get("/mysql-out-of-range")
    assert resp.status_code == 422
    assert resp.json() == {"detail": "数值超出范围"}


def test_unrelated_overflow_still_500() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    assert client.get("/other-overflow").status_code == 500


def test_unrelated_overflow_propagates() -> None:
    with pytest.raises(OverflowError):
        TestClient(_app()).get("/other-overflow")
