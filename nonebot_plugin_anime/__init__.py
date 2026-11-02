from .core import *
from .handlers import *
from .config import Config, ensure_dirs
from .core.anime_http import close_session

from nonebot import get_driver
from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-anime",
    description="Bangumi 番剧查询等查看番剧角色详情",
    usage="使用anime help查看详情",
    type="application",
    config=Config,
    supported_adapters={"~onebot.v11"},
    homepage="https://github.com/ShioMI39/nonebot-plugin-anime"
)

ensure_dirs()


@get_driver().on_shutdown
async def _close_http_session() -> None:
    """进程退出时释放共享 HTTP 会话"""
    await close_session()