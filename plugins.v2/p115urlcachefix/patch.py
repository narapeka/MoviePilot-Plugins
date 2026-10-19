"""仅接管 115StrmHelper 单例的 302 缓存，不修改源文件"""

import inspect
from datetime import datetime
from math import ceil
from time import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

from app.log import logger


class RedirectCachePatch:
    """为目标缓存单例保存固定到期时间，并管理方法恢复"""

    _RETENTION_SECONDS = 24 * 3600
    _SAFETY_SECONDS = 300
    _OWNER_ATTRIBUTE = "_p115_url_cache_fix_owner"

    def __init__(self, target: Any, mode: str, minutes: int) -> None:
        self._target = target
        self._mode = mode
        self._minutes = minutes
        self._cache = target._cache
        self._region = f"{target.region}:p115urlcachefix_v1"
        self._original = {}
        self._replacement = {
            "get": self._get,
            "set": self._set,
            "count_by_pick_code": self._count_by_pick_code,
            "clear": self._clear,
        }

    def enable(self) -> None:
        """检查目标方法后一次性替换，仅作用于这个缓存单例"""
        if getattr(self._target, self._OWNER_ATTRIBUTE, None) is not None:
            raise RuntimeError("已有缓存修正实例接管该插件，请只启用一个修正实例")
        arguments = {
            "get": ("pickcode", "ua"),
            "set": ("pickcode", "ua", "url", 1),
            "count_by_pick_code": ("pickcode",),
            "clear": (),
        }
        for name, args in arguments.items():
            method = getattr(self._target, name)
            if not inspect.iscoroutinefunction(method):
                raise TypeError(f"目标方法 {name} 已不再是异步方法")
            inspect.signature(method).bind(*args)
            self._original[name] = method
        setattr(self._target, self._OWNER_ATTRIBUTE, self)
        for name, method in self._replacement.items():
            setattr(self._target, name, method)

    def disable(self) -> None:
        """恢复仍由本实例持有的方法，不覆盖其他补丁的后续改动"""
        for name, method in self._replacement.items():
            if self._target.__dict__.get(name) is method:
                setattr(self._target, name, self._original[name])
        if getattr(self._target, self._OWNER_ATTRIBUTE, None) is self:
            delattr(self._target, self._OWNER_ATTRIBUTE)

    def _deadline(self, entry: Dict[str, Any]) -> float:
        return min(entry["expires_at"], entry["fetched_at"] + self._minutes * 60)

    @staticmethod
    def _format_time(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).astimezone().isoformat(" ", timespec="seconds")

    async def _get(self, pick_code: str, ua_code: str) -> Optional[str]:
        if self._mode == "bypass":
            logger.debug(f"【115直链缓存修正】跳过缓存读取 pickcode={pick_code}，返回未命中")
            return None
        entry = await self._cache.get(
            key=self._target._make_key(pick_code, ua_code), region=self._region
        )
        if entry is None:
            logger.debug(f"【115直链缓存修正】缓存未命中 pickcode={pick_code}，交由原插件处理")
            return None
        deadline = self._deadline(entry)
        remaining = deadline - time()
        if remaining <= 0:
            logger.debug(
                f"【115直链缓存修正】缓存已到期 pickcode={pick_code} "
                f"实际复用截止={self._format_time(deadline)}，返回未命中，交由原插件处理"
            )
            return None
        logger.debug(
            f"【115直链缓存修正】缓存命中 pickcode={pick_code} "
            f"剩余={ceil(remaining)}秒"
        )
        return entry["url"]

    async def _set(
        self, pick_code: str, ua_code: str, url: str, expires_time: float
    ) -> None:
        now = time()
        key = self._target._make_key(pick_code, ua_code)
        try:
            cdn_expires_at = int(parse_qs(urlsplit(url).query)["t"][0])
        except (KeyError, ValueError):
            await self._cache.delete(key=key, region=self._region)
            logger.debug(
                f"【115直链缓存修正】未缓存 pickcode={pick_code}，CDN的t参数缺失或无效"
            )
            return
        deadline = min(
            now + self._minutes * 60,
            float(expires_time),
            cdn_expires_at - self._SAFETY_SECONDS,
        )
        if deadline <= now:
            await self._cache.delete(key=key, region=self._region)
            logger.debug(
                f"【115直链缓存修正】未缓存 pickcode={pick_code}，已到安全截止时间 "
                f"截止={self._format_time(deadline)}"
            )
            return
        await self._cache.set(
            key=key,
            value={"url": url, "fetched_at": now, "expires_at": deadline},
            ttl=self._RETENTION_SECONDS,
            region=self._region,
        )
        if self._mode == "bypass":
            logger.debug(
                f"【115直链缓存修正】记录有效条目 pickcode={pick_code} "
                f"模式=跳过缓存，仅供多端计数，不复用直链 "
                f"条目截止={self._format_time(deadline)}"
            )
        else:
            logger.info(
                f"【115直链缓存修正】写入缓存 pickcode={pick_code} "
                f"模式=限时{self._minutes}分钟 "
                f"CDN到期={self._format_time(cdn_expires_at)} "
                f"原插件截止={self._format_time(float(expires_time))} "
                f"实际复用截止={self._format_time(deadline)} "
                f"剩余={max(0, ceil(deadline - time()))}秒"
            )

    async def _count_by_pick_code(self, pick_code: str) -> int:
        prefix = self._target._make_key(pick_code, "")
        now = time()
        count = 0
        async for key, entry in self._cache.items(region=self._region):
            if key.startswith(prefix) and now < self._deadline(entry):
                count += 1
        return count

    async def _clear(self) -> None:
        await self._cache.clear(region=self._region)
        await self._original["clear"]()
        logger.info("【115直链缓存修正】已清空接管区域及原插件302缓存")
