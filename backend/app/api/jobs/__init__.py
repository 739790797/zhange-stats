"""管理员定时任务 API 包（URL 路径不变）。"""
from fastapi import APIRouter

from app.api.jobs import checkin_queries, list_update, trigger_runs
from app.api.jobs.catalog import JOB_CATALOG
from app.api.jobs.checkin_queries import query_checkin_logs, query_user_checkin_tasks

router = APIRouter(prefix="/settings", tags=["settings"])
for _sub in (list_update, checkin_queries, trigger_runs):
    router.include_router(_sub.router)

__all__ = [
    "router",
    "JOB_CATALOG",
    "query_user_checkin_tasks",
    "query_checkin_logs",
]
