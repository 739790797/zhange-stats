"""签到平台 Adapter 契约：会话 / 查今日 / 执行签到；HTTP 细节留在 *_attendance。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.services.checkin.common import CheckinResult
from app.services.checkin.role_prefs import RoleKey


class SkipPolicy(str, Enum):
    """执行签到前是否用今日 logs 跳过。"""

    LOGS_AUTHORITY = "logs_authority"
    ALWAYS_RUN = "always_run"


@dataclass
class CheckinRunOutcome:
    """run_checkins 出口；early_response 非空时编排层直接返回、不落库。"""

    session: Any
    results: list[CheckinResult] = field(default_factory=list)
    early_response: dict[str, Any] | None = None


@runtime_checkable
class CheckinPlatformAdapter(Protocol):
    platform: str
    job_key: str
    bind_model: type
    log_model: type
    api_error_cls: type[Exception]
    empty_message: str
    skip_policy: SkipPolicy

    def get_bind(self, db: Session, member_id: int) -> Any | None: ...

    def load_session(self, db: Session, bind: Any) -> Any:
        """解密/登录得到可喂给 attendance 的 session/creds。"""

    def save_session(self, db: Session, bind: Any, session: Any) -> None:
        """刷新后的凭证回写；无刷新则 no-op。"""

    def query_today_all(self, session: Any) -> tuple[Any, list[CheckinResult]]:
        """统一出口：(session, results)。"""

    def run_checkins(
        self,
        session: Any,
        *,
        force: bool,
        role_keys: set[RoleKey] | None,
    ) -> CheckinRunOutcome:
        """含 probe-before-post / 每日任务等平台策略。"""

    def after_checkin(
        self, db: Session, bind: Any, results: list[CheckinResult]
    ) -> None:
        """签到动作后副作用（invalidate raw 等）；默认 no-op。"""

    def friendly_error(self, message: str) -> str: ...

    def prepare_cached_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult] | None:
        """今日 logs 命中时加工；返回 None 表示放弃缓存、强制回源。"""

    def normalize_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult]:
        """落库前后排序/本地化等。"""

    def enrich_summary(self, summary: str, results: list[CheckinResult]) -> str: ...

    def mark_as_skipped(
        self,
        bind: Any,
        results: list[CheckinResult],
        *,
        force: bool,
        checkin_date: Any,
    ) -> bool:
        """ALWAYS_RUN 等：是否把本次响应标为 skipped（仍已执行上游）。"""

    def reraise_api_error(self, exc: Exception) -> None:
        """把上游异常转成带友好文案的 api_error_cls 并 raise。"""


class CheckinAdapterBase:
    """可选基类：为钩子提供默认实现。"""

    skip_policy: SkipPolicy = SkipPolicy.LOGS_AUTHORITY

    def save_session(self, db: Session, bind: Any, session: Any) -> None:
        return None

    def after_checkin(
        self, db: Session, bind: Any, results: list[CheckinResult]
    ) -> None:
        return None

    def prepare_cached_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult] | None:
        return results

    def normalize_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult]:
        return results

    def enrich_summary(self, summary: str, results: list[CheckinResult]) -> str:
        return summary

    def mark_as_skipped(
        self,
        bind: Any,
        results: list[CheckinResult],
        *,
        force: bool,
        checkin_date: Any,
    ) -> bool:
        return False

    def reraise_api_error(self, exc: Exception) -> None:
        msg = getattr(exc, "message", None) or str(exc)
        friendly = self.friendly_error(msg)
        code = getattr(exc, "code", None)
        cls = self.api_error_cls
        try:
            if code is not None:
                raise cls(friendly, code=code) from exc
        except TypeError:
            pass
        raise cls(friendly) from exc
