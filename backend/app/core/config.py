from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import DEFAULT_DATA_DIR, DEFAULT_UPLOAD_DIR, resolve_runtime_path
from app.core.secret import DEFAULT_SECRET_KEY, ensure_secret_key


def _read_version_file() -> str:
    for candidate in (
        Path("/app/VERSION"),
        Path(__file__).resolve().parents[3] / "VERSION",
        Path.cwd() / "VERSION",
        Path.cwd().parent / "VERSION",
    ):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "mysql+pymysql://root:password@127.0.0.1:3306/zhange_stats_dev"
    # 请求线程 + 调度任务共用；按 MariaDB max_connections 留余量
    DB_POOL_SIZE: int = 15
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 10
    # 留空或保持占位值时，首次启动会自动生成并写入 DATA_DIR/.secret_key
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    # 默认 24 小时；管理端可在 system_configs 再调（最长 1 年）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    # 留空：本地 Vite + Tauri 2 用 allow_origin_regex；生产同域一般无需 CORS
    CORS_ORIGINS: str = ""
    # 留空用默认正则（localhost / 127.0.0.1 / tauri.localhost）；非空则整段覆盖
    CORS_ORIGIN_REGEX: str = ""
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "123456"
    ADMIN_DISPLAY_NAME: str = "管理员"
    ADMIN_EMAIL: str = "admin@localhost"
    # 默认走安装向导；仅 CI/脚本可设 true 用上面 ADMIN_* 自动种子
    ALLOW_ENV_ADMIN_SEED: bool = False
    # development | production（production 下弱口令默认拒绝启动；也可在安全设置覆盖）
    APP_ENV: str = "development"
    # 遗留：未写入库策略前作为默认；新部署请在管理端「安全设置」配置
    REJECT_WEAK_ADMIN_PASSWORD: bool | None = None
    # 遗留：仅作库策略初始默认；请在「安全设置」开关
    ENFORCE_SINGLE_ADMIN: bool = False

    # 可选 Redis（限流跨实例）；留空则进程内滑动窗口
    REDIS_URL: str = ""
    # 为 true 时限流信任 X-Forwarded-For 首段（仅置于受信反代后开启）
    TRUST_X_FORWARDED_FOR: bool = False

    STEAM_API_KEY: str = ""
    STEAM_POLL_INTERVAL_MINUTES: int = 3
    STEAM_POLL_ENABLED: bool = True
    MINECRAFT_POLL_INTERVAL_MINUTES: int = 1
    # 可选手动覆盖 OAuth 回调基址；留空则从请求 Host / Origin / X-Forwarded-* 推断
    PUBLIC_BACKEND_URL: str = ""
    PUBLIC_FRONTEND_URL: str = ""

    # QQ 互联（个人中心绑定；审核中仅调试 QQ 号可用）
    QQ_APP_ID: str = ""
    QQ_APP_KEY: str = ""

    # 森空岛每日签到（明日方舟 / 终末地）— 默认北京时间 00:01
    SKLAND_CHECKIN_ENABLED: bool = True
    SKLAND_CHECKIN_HOUR: int = 0
    SKLAND_CHECKIN_MINUTE: int = 1
    # 明日方舟盒子练度日更（默认 00:20，可与签到错开）
    ARKNIGHTS_BOX_SYNC_ENABLED: bool = True
    ARKNIGHTS_BOX_SYNC_HOUR: int = 0
    ARKNIGHTS_BOX_SYNC_MINUTE: int = 20
    # 明日方舟开源图鉴（ArknightsGameResource character_table，默认 04:00）
    ARKNIGHTS_CATALOG_SYNC_ENABLED: bool = True
    ARKNIGHTS_CATALOG_SYNC_HOUR: int = 4
    ARKNIGHTS_CATALOG_SYNC_MINUTE: int = 0
    # 森空岛活动日历（game-schedule，默认 05:00）
    GAME_SCHEDULE_SYNC_ENABLED: bool = True
    GAME_SCHEDULE_SYNC_HOUR: int = 5
    GAME_SCHEDULE_SYNC_MINUTE: int = 0
    # 逃离塔科夫全量（物品+任务+商人+BOSS+藏身处+门锁缓存，默认 04:25）
    TARKOV_FULL_SYNC_ENABLED: bool = True
    TARKOV_FULL_SYNC_HOUR: int = 4
    TARKOV_FULL_SYNC_MINUTE: int = 25
    # 分项定时默认关，避免与全量重复拉上游；接口仍可单独回源
    TARKOV_ITEMS_SYNC_ENABLED: bool = False
    TARKOV_ITEMS_SYNC_HOUR: int = 4
    TARKOV_ITEMS_SYNC_MINUTE: int = 30
    TARKOV_TASKS_SYNC_ENABLED: bool = False
    TARKOV_TASKS_SYNC_HOUR: int = 4
    TARKOV_TASKS_SYNC_MINUTE: int = 35
    TARKOV_TRADERS_SYNC_ENABLED: bool = False
    TARKOV_TRADERS_SYNC_HOUR: int = 4
    TARKOV_TRADERS_SYNC_MINUTE: int = 40
    TARKOV_BOSSES_SYNC_ENABLED: bool = False
    TARKOV_BOSSES_SYNC_HOUR: int = 4
    TARKOV_BOSSES_SYNC_MINUTE: int = 45
    TARKOV_GUIDES_SYNC_ENABLED: bool = False
    TARKOV_GUIDES_SYNC_HOUR: int = 4
    TARKOV_GUIDES_SYNC_MINUTE: int = 50
    # 兼容旧 .env；调度已合并为 TARKOV_ITEMS_*
    TARKOV_AMMO_SYNC_ENABLED: bool = True
    TARKOV_AMMO_SYNC_HOUR: int = 4
    TARKOV_AMMO_SYNC_MINUTE: int = 30
    TARKOV_GUN_SYNC_ENABLED: bool = True
    TARKOV_GUN_SYNC_HOUR: int = 4
    TARKOV_GUN_SYNC_MINUTE: int = 40
    # 塔吉多每日签到（异环）
    TAYGEDO_CHECKIN_ENABLED: bool = True
    TAYGEDO_CHECKIN_HOUR: int = 0
    TAYGEDO_CHECKIN_MINUTE: int = 1
    # 追放社区每日签到
    EXILIUM_CHECKIN_ENABLED: bool = True
    EXILIUM_CHECKIN_HOUR: int = 0
    EXILIUM_CHECKIN_MINUTE: int = 1
    # 库街区每日签到（社区 + 鸣潮/战双）
    KUJIEQU_CHECKIN_ENABLED: bool = True
    KUJIEQU_CHECKIN_HOUR: int = 0
    KUJIEQU_CHECKIN_MINUTE: int = 1

    MIHOYO_CHECKIN_ENABLED: bool = True
    MIHOYO_CHECKIN_HOUR: int = 0
    MIHOYO_CHECKIN_MINUTE: int = 1
    # 运行时数据目录（密钥/日志等；相对路径相对安装根，默认 var/data）
    DATA_DIR: str = DEFAULT_DATA_DIR
    # 应用日志：级别 / 内存环缓冲 / JSONL 持久化（DATA_DIR/logs/app.jsonl）
    APP_LOG_LEVEL: str = "INFO"
    APP_LOG_RING_CAPACITY: int = 5000
    APP_LOG_FILE: bool = True
    APP_LOG_FILE_MAX_MB: int = 50
    APP_LOG_FILE_BACKUP_COUNT: int = 5
    # 头像等本地上传目录（相对安装根或绝对路径，默认 var/uploads）
    UPLOAD_DIR: str = DEFAULT_UPLOAD_DIR

    # 邮件（不配置则默认拒绝发码；本地可开 ALLOW_EMAIL_CODE_LOG 把验证码打到日志）
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_SSL: bool = True
    SMTP_STARTTLS: bool = False
    EMAIL_CODE_EXPIRE_MINUTES: int = 15
    # 仅本地调试：SMTP 未配时允许把完整验证码写入日志/stdout（生产启动会拒绝）
    ALLOW_EMAIL_CODE_LOG: bool = False

    # 部署版本号（镜像/本地 VERSION 文件）
    APP_VERSION: str = _read_version_file()
    STATIC_DIR: str = ""

    # 源码/LXC 部署根目录（含 VERSION 与 backend/）；空则自动探测
    APP_INSTALL_DIR: str = ""
    # 应用内一键更新：None 时仅 production 默认允许
    ALLOW_IN_APP_UPDATE: bool | None = None
    # GitHub Releases（检查/下载更新）
    UPDATE_GITHUB_REPO: str = "739790797/zhange-stats"
    UPDATE_GITHUB_API: str = "https://api.github.com"
    UPDATE_GITHUB_TOKEN: str = ""

    # 活动日历上游（game-schedule Cloudflare Worker，见 jacket-sikaha/game-schedule）
    GAME_SCHEDULE_BASE_URL: str = "https://gebc.lee-sikaha.cloudns.ch"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return (self.APP_ENV or "").strip().lower() in ("production", "prod")

    @property
    def allow_in_app_update(self) -> bool:
        if self.ALLOW_IN_APP_UPDATE is not None:
            return bool(self.ALLOW_IN_APP_UPDATE)
        return self.is_production

    @property
    def reject_weak_admin_password(self) -> bool:
        """显式 REJECT_* 优先；否则 production 默认拒绝。"""
        if self.REJECT_WEAK_ADMIN_PASSWORD is not None:
            return bool(self.REJECT_WEAK_ADMIN_PASSWORD)
        return self.is_production

    @property
    def data_dir_path(self) -> Path:
        return resolve_runtime_path(self.DATA_DIR, configured_install=self.APP_INSTALL_DIR)

    @property
    def upload_dir_path(self) -> Path:
        return resolve_runtime_path(self.UPLOAD_DIR, configured_install=self.APP_INSTALL_DIR)

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.SECRET_KEY = ensure_secret_key(
        settings.SECRET_KEY,
        data_dir=settings.DATA_DIR,
        upload_dir=settings.UPLOAD_DIR,
        install_dir=settings.APP_INSTALL_DIR,
    )
    return settings
