"""
游戏数据适配器接口预留（第二期）。

各平台/游戏实现应继承 BaseGameAdapter，提供拉取原始战绩并解析为 MatchRecord 字段的能力。
第一期不实现真实爬虫或官方 API 调用。
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
        """将原始数据解析为可写入 MatchRecord 的字典列表。"""


# 示例：后续可添加 SteamAdapter / HonorOfKingsAdapter 等
