"""115 直链缓存修正插件的 MoviePilot V3 入口"""

import sys
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase
from app.schemas.types import EventType

from .patch import RedirectCachePatch


class P115UrlCacheFix(_PluginBase):
    """在运行时接管官方 115StrmHelper 的 302 缓存"""

    plugin_name = "115直链缓存修正"
    plugin_desc = "为115网盘STRM助手限制直链缓存时长，或跳过缓存读取"
    plugin_icon = "https://raw.githubusercontent.com/narapeka/MoviePilot-Plugins/main/icons/P115UrlCacheFix.svg"
    plugin_version = "3.0.0"
    plugin_author = "narapeka"
    author_url = "https://github.com/narapeka/MoviePilot-Plugins"
    plugin_config_prefix = "p115urlcachefix_"
    plugin_order = 100
    auth_level = 1

    def __init__(self) -> None:
        super().__init__()
        self._lock = RLock()
        self._enabled = False
        self._mode = "limit"
        self._minutes = 15
        self._patch: Optional[RedirectCachePatch] = None
        self._status = "未启用"

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """读取配置并接管当前已加载的目标单例"""
        with self._lock:
            self.stop_service()
            config = config or {}
            self._enabled = config.get("enabled", False)
            self._mode = config.get("mode", "limit")
            self._minutes = int(config.get("minutes", 15))
            if self._mode not in ("limit", "bypass") or self._minutes not in (15, 30, 60, 120, 360, 720):
                self._enabled = False
                self._status = "配置无效，请重新选择缓存模式和时长"
                logger.error(f"115直链缓存修正：{self._status}")
                return
            if self._enabled:
                self._apply_patch()

    def _apply_patch(self) -> None:
        with self._lock:
            module = sys.modules.get("app.plugins.p115strmhelper.core.cache")
            target = getattr(module, "r302cacher", None)
            if self._patch is not None and self._patch._target is target:
                return
            if self._patch is not None:
                self._patch.disable()
                self._patch = None
            if target is None:
                self._status = "等待115网盘STRM助手加载，请先安装并启用该插件"
                logger.info(f"115直链缓存修正：{self._status}")
                return
            try:
                patch = RedirectCachePatch(target, self._mode, self._minutes)
                patch.enable()
            except (AttributeError, TypeError, ValueError, RuntimeError) as error:
                self._status = f"接管失败：{error}"
                logger.error(f"115直链缓存修正：{self._status}")
                return
            self._patch = patch
            duration = f"{self._minutes}分钟" if self._minutes < 60 else f"{self._minutes // 60}小时"
            mode = "跳过缓存读取" if self._mode == "bypass" else f"限时缓存，最长{duration}"
            self._status = f"已接管：{mode}，CDN到期前5分钟停止复用"
            logger.info(f"115直链缓存修正：{self._status}")

    @eventmanager.register(EventType.PluginReload)
    def on_plugin_reload(self, event: Event) -> None:
        """目标更新或重载后重新接管新模块中的单例"""
        payload = event.snapshot().payload
        if self._enabled and payload and payload.plugin_id.lower() == "p115strmhelper":
            self._apply_patch()

    def get_state(self) -> bool:
        """启用时继续监听目标插件的重载事件"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """不注册远程命令"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """不提供额外的网络接口"""
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """提供启用开关、缓存模式、固定时长及接管状态"""
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "text": "本补丁适用于CDN直链有效期较短、疑似复用过期直链导致播放或续播失败的情况。原插件使用正常时不建议开启；本补丁不会延长CDN直链的有效期。",
                        },
                    },
                    {
                        "component": "VSwitch",
                        "props": {"model": "enabled", "label": "启用缓存修正"},
                    },
                    {
                        "component": "VSelect",
                        "props": {
                            "model": "mode",
                            "label": "缓存模式",
                            "items": [
                                {"title": "限时缓存（推荐）", "value": "limit"},
                                {"title": "跳过缓存读取（排查用）", "value": "bypass"},
                            ],
                        },
                    },
                    {
                        "component": "VSelect",
                        "props": {
                            "model": "minutes",
                            "label": "最长缓存时间",
                            "items": [
                                {
                                    "title": f"{minutes}分钟" if minutes < 60 else f"{minutes // 60}小时",
                                    "value": minutes,
                                }
                                for minutes in (15, 30, 60, 120, 360, 720)
                            ],
                        },
                    },
                    {"component": "VAlert", "props": {"type": "info", "text": self._status}},
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "text": "限时缓存从获取直链时计时，读取不会续期；同时遵守CDN的t参数和原插件到期时间。不同UA分开缓存。启用后不导入旧直链，首次播放会重新解析。跳过模式每次请求都重新解析，会增加115接口请求。",
                        },
                    },
                ],
            }
        ], {"enabled": False, "mode": "limit", "minutes": 15}

    def get_page(self) -> List[dict]:
        """展示当前接管状态"""
        return [{"component": "VAlert", "props": {"type": "info", "text": self._status}}]

    def stop_service(self) -> None:
        """禁用或卸载时恢复原方法，保留原插件配置和数据库"""
        with self._lock:
            self._enabled = False
            if self._patch is not None:
                self._patch.disable()
                self._patch = None
                logger.info("115直链缓存修正：已恢复原插件缓存方法")
            self._status = "未启用"
