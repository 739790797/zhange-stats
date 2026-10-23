from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.skland import endfield as api
from app.core.database import get_db
from app.core import platform_deps


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(platform_deps, "is_feature_enabled", lambda _db, _feature: True)
    app = FastAPI()
    app.include_router(api.router, prefix="/api/skland")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def test_inn_endpoints_are_in_openapi_and_do_not_require_skland_binding(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "list_topics",
        lambda: {
            "topics": [{"id": "topic", "name": "主题", "unlock_level": 1, "private_chef": False}],
            "expansions": [],
        },
    )
    seen: dict[str, object] = {}

    def fake_plan(topic_id: str, level: int, expansions=None):
        seen.update(topic_id=topic_id, level=level, expansions=expansions)
        return {
            "topic_id": topic_id,
            "topic_name": "主题",
            "level": level,
            "menu": [],
            "chefs": [],
            "star": {
                "private_chef": False,
                "star_scores": [100],
                "kpi_cap": 50,
                "profit_cap": 30,
                "needs_objective": False,
                "objective": "",
                "estimate": "估算",
            },
        }

    monkeypatch.setattr(api, "build_plan", fake_plan)

    def fake_query(**kwargs):
        seen["query"] = kwargs
        return {
            "level": kwargs["level"],
            "topic_id": kwargs["topic_id"],
            "kitchen_count": 1,
            "chef_slot_count": 1,
            "jsspsi_bonus_tier": kwargs["jsspsi_bonus_tier"],
            "jsspsi_rare_rate_bonus": 0.03,
            "dishes": [],
            "drinks": [],
            "chef_catalog": [],
            "recommendations": None,
        }

    monkeypatch.setattr(api, "build_inn_query", fake_query)
    client = _client(monkeypatch)
    topics = client.get("/api/skland/endfield/inn/topics")
    plan = client.get(
        "/api/skland/endfield/inn/plan",
        params=[("topic_id", "topic"), ("level", "2"), ("expansions", "a"), ("expansions", "b")],
    )
    query = client.post(
        "/api/skland/endfield/inn/query",
        json={
            "level": 2,
            "expansions": ["a", "b"],
            "topic_id": "topic",
            "topic_stars": {"topic": 3},
            "jsspsi_bonus_tier": 2,
        },
    )

    assert topics.status_code == 200
    assert topics.json()["topics"][0]["id"] == "topic"
    assert plan.status_code == 200
    assert seen["topic_id"] == "topic"
    assert seen["level"] == 2
    assert seen["expansions"] == ["a", "b"]
    assert seen["query"] == {
        "level": 2,
        "expansions": ["a", "b"],
        "topic_id": "topic",
        "topic_stars": {"topic": 3},
        "jsspsi_bonus_tier": 2,
    }
    assert query.status_code == 200
    assert query.json()["recommendations"] is None
    schema = client.app.openapi()
    assert schema["paths"]["/api/skland/endfield/inn/topics"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("InnTopicsOut")
    assert schema["paths"]["/api/skland/endfield/inn/plan"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("InnPlanOut")
    assert schema["paths"]["/api/skland/endfield/inn/query"]["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("InnQueryOut")
