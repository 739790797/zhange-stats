"""
游戏数据适配器接口。

各平台/游戏实现应继承 BaseGameAdapter。
Steam 当前游玩状态见 steam.SteamAdapter。
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseGameAdapter(ABC):
    """游戏数据源适配器基类。"""

    game_key: str

    @abstractmethod
    def fetch_raw(self, external_id: str) -> Any:
        """从外部数据源拉取原始数据。"""

    @abstractmethod
    def parse(self, raw: Any) -> list[dict[str, Any]]:
        """将原始数据解析为统一结构的字典列表。"""
