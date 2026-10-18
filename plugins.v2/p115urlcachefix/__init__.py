"""115 直链缓存修正插件的 MoviePilot V2 入口"""

import sys
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType

from .patch import RedirectCachePatch


class P115UrlCacheFix(_PluginBase):
    """在运行时接管官方 115StrmHelper 的 302 缓存"""

    plugin_name = "115直链缓存修正"
    plugin_desc = "为115网盘STRM助手限制直链缓存时长，或跳过缓存读取"
    plugin_icon = "https://raw.githubusercontent.com/narapeka/MoviePilot-Plugins/main/icons/P115UrlCacheFix.svg"
    plugin_version = "1.0.1"
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
        if self._enabled and event.event_data.get("plugin_id", "").lower() == "p115strmhelper":
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
        fields = [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "density": "compact",
                    "class": "text-body-2",
                    "text": "适用于直链有效期较短、疑似复用过期直链导致播放或续播失败的情况。原插件使用正常时，不建议开启。",
                },
            },
            {
                "component": "VSwitch",
                "props": {
                    "model": "enabled",
                    "label": "启用缓存修正",
                    "color": "primary",
                    "density": "compact",
                    "hideDetails": True,
                },
            },
            {
                "component": "VSelect",
                "props": {
                    "variant": "outlined",
                    "density": "comfortable",
                    "hideDetails": True,
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
                    "variant": "outlined",
                    "density": "comfortable",
                    "hideDetails": True,
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
            {
                "component": "div",
                "props": {"class": "text-body-2 text-medium-emphasis"},
                "text": f"当前生效状态：{self._status}。修改后点击保存生效，无需重启。",
            },
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "density": "compact",
                    "class": "text-body-2",
                    "text": "读取不续期，且不晚于CDN到期前5分钟；不同UA分开缓存。首次使用会重新解析直链，跳过模式会增加接口请求。本补丁不会延长直链有效期。",
                },
            },
        ]
        return [
            {
                "component": "VForm",
                "props": {"style": {"max-width": "720px", "margin": "0 auto"}},
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12}, "content": [field]}
                            for field in fields
                        ],
                    }
                ],
            }
        ], {"enabled": False, "mode": "limit", "minutes": 15}

    def get_page(self) -> Optional[List[dict]]:
        """不提供独立详情页，点击插件卡片直接打开配置"""
        pass

    def stop_service(self) -> None:
        """禁用或卸载时恢复原方法，保留原插件配置和数据库"""
        with self._lock:
            self._enabled = False
            if self._patch is not None:
                self._patch.disable()
                self._patch = None
                logger.info("115直链缓存修正：已恢复原插件缓存方法")
            self._status = "未启用"
