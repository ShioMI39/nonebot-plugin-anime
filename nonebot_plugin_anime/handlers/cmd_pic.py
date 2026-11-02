import asyncio
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core import bgm_manager, season_poster_generator
from ..core.anime_session import set_session
from ..core.anime_time import parse_single_date, validate_year, normalize_weekday
from ..core.anime_permissons import is_private_or_allowed_group
from ..config import MONTH_NAMES, POSTER_DIR, WEEKDAY_ORDER
from .cmd_season import _send_nodes, _bot_uin

from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import Rule


# ==================== 绘图命令 ====================
anime_view_poster = on_command("anime view poster", aliases={"番剧查看图"}, priority=5,
                               rule=Rule(is_private_or_allowed_group))
anime_week_poster = on_command("anime view week poster", aliases={"星期查看图"}, priority=5,
                               rule=Rule(is_private_or_allowed_group))
anime_view_poster_update = on_command("anime view poster update", aliases={"番剧图更新"}, priority=5,
                                      rule=Rule(is_private_or_allowed_group))
anime_week_poster_update = on_command("anime view week poster update", aliases={"星期图更新"}, priority=5,
                                      rule=Rule(is_private_or_allowed_group))

MIN_VOTES = 50          # 排行门槛：评分人数不足的番剧排在榜尾
POSTER_TTL = 7 * 86400              # 图缓存有效期（7 天，过期自动重建）
REFRESH_INTERVAL = 0.3              # 批量刷新评分的请求间隔（秒）


def _to_poster_items(pairs: List[Tuple[str, Dict]]) -> List[Dict]:
    """把 (显示名, 条目) 列表转成绘图用数据"""
    items = []
    for title, info in pairs:
        bi = info.get('basic_info') or {}
        tags = sorted((info.get('tags') or []), key=lambda t: t.get('count', 0), reverse=True)
        items.append({
            'id': str(info.get('id') or ''),
            'title': title,
            'jp': (bi.get('original_title') or '').strip(),
            'date': (bi.get('start_date') or '').strip(),
            'eps': str(bi.get('episodes') or '').strip(),
            'day': (bi.get('broadcast_day') or '').strip() or '其他',
            'score': (info.get('rating') or {}).get('score') or 0,
            'tags': [t.get('name', '') for t in tags if t.get('name')][:season_poster_generator.MAX_TAGS],
            'cover_url': info.get('cover_url'),
        })
    return items


async def _send_poster_pages(bot: Bot, event: Event, pages: List[Tuple[str, str]]) -> bool:
    """合并转发每页一张图；失败则提示"""
    if not pages:
        return False

    nodes = [
        MessageSegment.node_custom(
            user_id=_bot_uin(bot),
            nickname=nickname[:60],
            content=Message(MessageSegment.image(f"file:///{path}")),
        )
        for nickname, path in pages
    ]

    ok = await _send_nodes(bot, event, nodes)
    if not ok:
        await bot.send(f"发送番剧图失败，请稍后再试")
    return ok


def _rank_key(pair: Tuple[str, Dict]) -> Tuple[int, float, int]:
    """排行排序 key：评分人数达标(≥MIN_VOTES)优先，其次 bgm 评分降序，再按评分人数降序

    人数不足的番剧 qualified=0，统一排在榜尾。
    """
    rating = pair[1].get('rating') or {}
    votes = int(rating.get('votes') or 0)
    score = float(rating.get('score') or 0)
    return (1 if votes >= MIN_VOTES else 0, score, votes)


def _has_month(text: str) -> bool:
    """参数里是否显式指定了月份（未指定则视为全年）"""
    return bool(re.search(r'\d{1,2}\s*月', text) or re.search(r'\d{4}\s*[-/.]\s*\d{1,2}', text))


# ==================== 图缓存 ====================
INDEX_VERSION = 1
INDEX_SUFFIX = '.index.json'


def _cache_path(key: str) -> Path:
    return POSTER_DIR / f"{key}.jpg"


def _index_path(prefix: str) -> Path:
    return POSTER_DIR / f"{prefix}{INDEX_SUFFIX}"


def _load_index(prefix: str) -> Optional[dict]:
    """读取并校验索引；损坏、版本不符、过期或缺图一律返回 None（视为未命中）"""
    try:
        data = json.loads(_index_path(prefix).read_text(encoding='utf-8'))
    except Exception:
        return None

    if not isinstance(data, dict) or data.get('version') != INDEX_VERSION:
        return None

    try:
        if time.time() - float(data.get('created_at', 0)) >= POSTER_TTL:
            return None
    except (TypeError, ValueError):
        return None

    pages = data.get('pages')
    if not isinstance(pages, list) or not pages:
        return None

    for page in pages:
        if not isinstance(page, dict):
            return None
        key, ids = page.get('key'), page.get('ids')
        if not isinstance(key, str) or not isinstance(ids, list):
            return None
        if not _cache_path(key).exists():
            return None

    return data


def _write_index(prefix: str, total: int, pages: List[dict]) -> bool:
    """写入索引：先写临时文件再替换，中途失败不会留下半套索引"""
    try:
        POSTER_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            'version': INDEX_VERSION,
            'created_at': time.time(),
            'total': total,
            'pages': pages,
        }
        target = _index_path(prefix)
        tmp = target.with_name(target.name + '.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(target)
        return True
    except Exception:
        logger.opt(exception=True).warning(f"写入图片缓存索引失败: {prefix}")
        return False


def _clear_cache(prefix: str) -> int:
    """删除指定前缀的缓存（图片 + 索引 + 临时文件），返回删除的图片数"""
    removed = 0
    files: List[Path] = []
    try:
        for pattern in (f"{prefix}*.jpg", f"{prefix}*.index.json", f"{prefix}*.tmp"):
            files.extend(POSTER_DIR.glob(pattern))
    except OSError:
        return 0
    for path in files:
        try:
            path.unlink()
            if path.suffix == '.jpg':
                removed += 1
        except OSError:
            pass
    return removed


def _page_keys(n_items: int, prefix: str, start_at: int, per: int) -> List[str]:
    keys = []
    for i in range(0, n_items, per):
        keys.append(f"{prefix}_{start_at + i}-{start_at + min(i + per, n_items) - 1}")
    return keys


# 同一 prefix 一把锁：海报重建串行
_locks: Dict[str, asyncio.Lock] = {}


def _prefix_lock(prefix: str) -> asyncio.Lock:
    lock = _locks.get(prefix)
    if lock is None:
        lock = _locks[prefix] = asyncio.Lock()
    return lock


def _reuse_cache(keys: List[str], total: int, prefix: str) -> Optional[List[Tuple[str, Dict]]]:
    """按索引还原缓存页对应的 pairs；任何不一致都返回 None（触发重建）"""
    index = _load_index(prefix)
    if not index or index.get('total') != total:
        return None

    cached = {page['key']: page['ids'] for page in index['pages']}
    if not all(k in cached for k in keys):
        return None

    ordered: List[Tuple[str, Dict]] = []
    for k in keys:
        for aid in cached[k]:
            info = bgm_manager.all_data.get(str(aid))
            if info is None:
                return None
            ordered.append((bgm_manager.get_display_name_by_id(aid), info))

    return ordered if len(ordered) == total else None


async def _build_and_cache(pairs: List[Tuple[str, Dict]], prefix: str, title: str,
                           *, force: bool = False, start_at: int = 1, refresh: bool = True,
                           ) -> Tuple[List[Tuple[str, str]], List[Tuple[str, Dict]]]:
    """生成（或复用缓存）海报页

    - 每页 PER_IMAGE 部，图片为 {prefix}_{起始编号}-{结束编号}.jpg，
      顺序记录在 {prefix}.index.json

    返回 ([(气泡昵称, 图片路径)], 最终顺序的 pairs)
    """
    per = season_poster_generator.PER_IMAGE
    total = len(pairs)
    if not total:
        return [], []

    def _nicknames(keys: List[str]) -> List[Tuple[str, str]]:
        pages = []
        for i, k in enumerate(keys):
            s = start_at + i * per
            e = min(s + per - 1, start_at + total - 1)
            nickname = f"{title}（{s}-{e}）" if total > per else title
            pages.append((nickname, str(_cache_path(k))))
        return pages

    keys = _page_keys(total, prefix, start_at, per)

    async with _prefix_lock(prefix):
        # 1. 复用缓存
        if not force:
            ordered = _reuse_cache(keys, total, prefix)
            if ordered is not None:
                return _nicknames(keys), ordered

        # 2. 重建：刷新评分 → 排序 → 重绘
        if refresh:
            try:
                ids = [str(info.get('id')) for _, info in pairs if info.get('id')]
                updated = await bgm_manager.refresh_scores(ids, interval=REFRESH_INTERVAL)
                if updated:
                    bgm_manager.save_all_data()      # 整个任务只写一次盘
                    logger.info(f"已刷新 {updated} 条番剧评分并写回")
            except Exception:
                logger.opt(exception=True).warning("刷新评分失败，继续使用本地数据")

        pairs.sort(key=_rank_key, reverse=True)

        written: Dict[str, List[str]] = {}
        for i, k in enumerate(keys):
            s = start_at + i * per
            page_pairs = pairs[i * per:(i + 1) * per]
            path = await season_poster_generator.generate_page(
                _to_poster_items(page_pairs), title, start=s, total=total, out_path=_cache_path(k))
            if path:
                written[k] = [str(info.get('id')) for _, info in page_pairs if info.get('id')]

        # 3. 所有页面都写成功才落索引，否则保持「未命中」，下次重建
        if all(k in written for k in keys):
            _write_index(prefix, total, [{'key': k, 'ids': written[k]} for k in keys])
        else:
            logger.warning(f"海报生成不完整，跳过索引写入: {prefix}")

        return _nicknames(keys), pairs


# ==================== 番剧查看图 ====================
@anime_view_poster.handle()
async def handle_anime_view_poster(bot: Bot, event: Event, arg: Message = CommandArg()):
    """番剧查看图 <年月|年份>：季度图；只给年份时绘制全年排行"""
    args = arg.extract_plain_text().strip()

    if not args:
        await anime_view_poster.finish(
            "使用方法：\n"
            "番剧查看图 <年月>\n"
            "例如：番剧查看图 2026年4月")

    result = parse_single_date(args)
    if not result[0]:
        await anime_view_poster.finish("格式错误，请使用如：2026年4月 或 2026年")
    year, month = result

    if not validate_year(year):
        await anime_view_poster.finish("年份范围超出")

    if not _has_month(args):
        # 全年：合并四个季度后按 bgm 评分全局降序排行（跨季度混排，编号即全年排名）
        pairs: List[Tuple[str, Dict]] = []
        for m in (1, 4, 7, 10):
            pairs.extend(bgm_manager.get_anime_by_season(year, m))
        if not pairs:
            await anime_view_poster.finish(f"{year}年没有找到番剧数据")
        prefix, title = f"{year}_all", f"{year}年番剧排行"
        search_type, search_query = "全年排行图", str(year)
        view_month, view_month_name = 0, "全年"
    else:
        month_name = MONTH_NAMES.get(month, f"{month}月")
        pairs = bgm_manager.get_anime_by_season(year, month)
        if not pairs:
            await anime_view_poster.finish(f"{year}年{month_name}季度没有找到番剧数据")
        prefix, title = f"{year}-{month:02d}", f"{year}年{month_name}番剧"
        search_type, search_query = "季度查看图", f"{year}-{month:02d}"
        view_month, view_month_name = month, month_name

    await anime_view_poster.send("正在绘制，请稍候...")

    pages, pairs = await _build_and_cache(pairs, prefix, title)
    if not pages:
        await anime_view_poster.finish("绘图失败，请稍后重试")

    # 会话顺序与图片编号一致（缓存复用时按缓存记录的顺序）
    set_session(
        event,
        'view_season',
        search_results=pairs,
        search_type=search_type,
        search_query=search_query,
        current_page=0,
        page_size=len(pairs),
        total_pages=1,
        view_year=year,
        view_month=view_month,
        view_month_name=view_month_name
    )

    await _send_poster_pages(bot, event, pages)
    await anime_view_poster.send(f"共 {len(pairs)} 部，输入编号查看详情（1~{len(pairs)}）")


# ==================== 星期查看图 ====================
@anime_week_poster.handle()
async def handle_anime_week_poster(bot: Bot, event: Event, arg: Message = CommandArg()):
    """星期查看图 <年月> [星期X]：按星期分组绘图（缓存 7 天）"""
    args = arg.extract_plain_text().strip()

    if not args:
        await anime_week_poster.finish(
            "使用方法：\n"
            "星期查看图 <年月> [星期X]\n"
            "例如：星期查看图 2026年4月")

    parts = args.split()
    if len(parts) > 2:
        await anime_week_poster.finish("参数格式错误，请使用：2026年4月 或 2026年4月 星期一")

    target_weekday = None
    if len(parts) == 2:
        target_weekday = normalize_weekday(parts[1])
        if not target_weekday:
            await anime_week_poster.finish("请使用正确的星期格式，如：星期一、周二、周三等")

    result = parse_single_date(parts[0])
    if not result[0]:
        await anime_week_poster.finish("季度格式错误，请使用如：2026年4月")
    year, month = result

    if not validate_year(year):
        await anime_week_poster.finish("年份范围超出")

    month_name = MONTH_NAMES.get(month, f"{month}月")
    weekday_groups = bgm_manager.get_anime_by_season_and_weekday(year, month)

    if not weekday_groups or all(not animes for animes in weekday_groups.values()):
        await anime_week_poster.finish(f"{year}年{month_name}季度没有找到番剧数据")

    days = [target_weekday] if target_weekday else WEEKDAY_ORDER

    await anime_week_poster.send("正在绘制，请稍候...")

    pages: List[Tuple[str, str]] = []
    flat: List[Tuple[str, Dict]] = []
    index = 0
    for day in days:
        group = weekday_groups.get(day) or []
        if not group:
            continue
        day_pairs = list(group)
        day_pages, day_pairs = await _build_and_cache(
            day_pairs, f"{year}-{month:02d}_{day}", f"{year}年{month_name} {day}", start_at=index + 1)
        pages.extend(day_pages)
        flat.extend(day_pairs)
        index += len(day_pairs)

    if not flat:
        which = target_weekday or '该季度'
        await anime_week_poster.finish(f"{year}年{month_name}{which}没有找到番剧")

    set_session(
        event,
        'view_week',
        search_results=flat,
        search_type="星期查看图",
        search_query=f"{year}-{month:02d} {target_weekday or '所有星期'}",
        current_page=0,
        page_size=len(flat),
        total_pages=1,
        view_year=year,
        view_month=month,
        view_month_name=month_name,
        view_target_weekday=target_weekday,
        view_weekday_groups=weekday_groups
    )

    await _send_poster_pages(bot, event, pages)
    await anime_week_poster.send(f"共 {len(flat)} 部，输入编号查看详情（1~{len(flat)}）")


# ==================== 番剧图更新 ====================
@anime_view_poster_update.handle()
async def handle_anime_view_poster_update(bot: Bot, event: Event, arg: Message = CommandArg()):
    """番剧图更新 <年月|年份>：清缓存并重新拉取评分、重绘"""
    args = arg.extract_plain_text().strip()

    if not args:
        await anime_view_poster_update.finish(
            "使用方法：\n"
            "番剧图更新 <年月>\n"
            "例如：番剧图更新 2026年4月")

    result = parse_single_date(args)
    if not result[0]:
        await anime_view_poster_update.finish("格式错误，请使用如：2026年4月")
    year, month = result

    if not validate_year(year):
        await anime_view_poster_update.finish("年份范围超出")

    if not _has_month(args):
        pairs: List[Tuple[str, Dict]] = []
        for m in (1, 4, 7, 10):
            pairs.extend(bgm_manager.get_anime_by_season(year, m))
        if not pairs:
            await anime_view_poster_update.finish(f"{year}年没有找到番剧数据")
        prefix, title = f"{year}_all", f"{year}年番剧排行"
        search_type, search_query = "全年排行图", str(year)
        view_month, view_month_name = 0, "全年"
    else:
        month_name = MONTH_NAMES.get(month, f"{month}月")
        pairs = bgm_manager.get_anime_by_season(year, month)
        if not pairs:
            await anime_view_poster_update.finish(f"{year}年{month_name}季度没有找到番剧数据")
        prefix, title = f"{year}-{month:02d}", f"{year}年{month_name}番剧"
        search_type, search_query = "季度查看图", f"{year}-{month:02d}"
        view_month, view_month_name = month, month_name

    removed = _clear_cache(prefix)
    await anime_view_poster_update.send("正在更新评分并重新绘制，请稍候...")

    pages, pairs = await _build_and_cache(pairs, prefix, title, force=True)
    if not pages:
        await anime_view_poster_update.finish("绘图失败，请稍后重试")

    set_session(
        event,
        'view_season',
        search_results=pairs,
        search_type=search_type,
        search_query=search_query,
        current_page=0,
        page_size=len(pairs),
        total_pages=1,
        view_year=year,
        view_month=view_month,
        view_month_name=view_month_name
    )

    await _send_poster_pages(bot, event, pages)
    await anime_view_poster_update.send(
        f"已更新（清理 {removed} 张旧图）· 共 {len(pairs)} 部，输入编号查看详情（1~{len(pairs)}）")


# ==================== 星期图更新 ====================
@anime_week_poster_update.handle()
async def handle_anime_week_poster_update(bot: Bot, event: Event, arg: Message = CommandArg()):
    """星期图更新 <年月> [星期X]：清缓存并重新拉取评分、重绘"""
    args = arg.extract_plain_text().strip()

    if not args:
        await anime_week_poster_update.finish(
            "使用方法：\n"
            "星期图更新 <年月> [星期X]\n"
            "例如：星期图更新 2026年4月")

    parts = args.split()
    if len(parts) > 2:
        await anime_week_poster_update.finish("参数格式错误，请使用：2026年4月 或 2026年4月 星期一")

    target_weekday = None
    if len(parts) == 2:
        target_weekday = normalize_weekday(parts[1])
        if not target_weekday:
            await anime_week_poster_update.finish("请使用正确的星期格式，如：星期一、周二、周三等")

    result = parse_single_date(parts[0])
    if not result[0]:
        await anime_week_poster_update.finish("季度格式错误，请使用如：2026年4月")
    year, month = result

    if not validate_year(year):
        await anime_week_poster_update.finish("年份范围超出")

    month_name = MONTH_NAMES.get(month, f"{month}月")
    weekday_groups = bgm_manager.get_anime_by_season_and_weekday(year, month)

    if not weekday_groups or all(not animes for animes in weekday_groups.values()):
        await anime_week_poster_update.finish(f"{year}年{month_name}季度没有找到番剧数据")

    days = [target_weekday] if target_weekday else WEEKDAY_ORDER

    await anime_week_poster_update.send("正在更新评分并重新绘制，请稍候...")

    removed = 0
    pages: List[Tuple[str, str]] = []
    flat: List[Tuple[str, Dict]] = []
    index = 0
    for day in days:
        group = weekday_groups.get(day) or []
        if not group:
            continue
        prefix = f"{year}-{month:02d}_{day}"
        removed += _clear_cache(prefix)
        day_pages, day_pairs = await _build_and_cache(
            list(group), prefix, f"{year}年{month_name} {day}", force=True, start_at=index + 1)
        pages.extend(day_pages)
        flat.extend(day_pairs)
        index += len(day_pairs)

    if not flat:
        await anime_week_poster_update.finish(f"{year}年{month_name}没有找到番剧")

    set_session(
        event,
        'view_week',
        search_results=flat,
        search_type="星期查看图",
        search_query=f"{year}-{month:02d} {target_weekday or '所有星期'}",
        current_page=0,
        page_size=len(flat),
        total_pages=1,
        view_year=year,
        view_month=month,
        view_month_name=month_name,
        view_target_weekday=target_weekday,
        view_weekday_groups=weekday_groups
    )

    await _send_poster_pages(bot, event, pages)
    await anime_week_poster_update.send(
        f"已更新（清理 {removed} 张旧图）· 共 {len(flat)} 部，输入编号查看详情（1~{len(flat)}）")
