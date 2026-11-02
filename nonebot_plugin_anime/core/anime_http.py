from typing import Optional

import aiohttp

_SESSION: Optional[aiohttp.ClientSession] = None


def get_session() -> aiohttp.ClientSession:
    """获取共享会话（首次调用时在当前事件循环里创建）"""
    global _SESSION
    if _SESSION is None or _SESSION.closed:
        _SESSION = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=64,
                limit_per_host=16,
                ttl_dns_cache=300,
            ),
            timeout=aiohttp.ClientTimeout(total=30),
        )
    return _SESSION


async def close_session() -> None:
    """关闭共享会话（插件卸载 / 进程退出时调用）"""
    global _SESSION
    session, _SESSION = _SESSION, None
    if session is not None and not session.closed:
        await session.close()
