from datetime import datetime
from ..core import bgm_manager
from ..core.anime_session import set_session, get_user_session
from ..core.anime_formatting import format_season_results_page, format_week_results_page
from ..core.anime_time import get_current_season, parse_single_date, validate_year
from ..core.anime_permissons import is_private_or_allowed_group
from ..config import MONTH_NAMES
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.rule import Rule, to_me
from nonebot.params import CommandArg


# ==================== 番剧查看命令 ====================
anime_view = on_command("anime view", aliases={"番剧查看"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_view_week = on_command("anime view week", aliases={"星期查看"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_view_today = on_command("anime view today", aliases={"今天有什么番"}, priority=5, rule=Rule(is_private_or_allowed_group))


# ==================== 番剧查看处理 ====================
@anime_view.handle()
async def handle_anime_view(event: Event, arg: Message = CommandArg()):
    """处理番剧季度查看指令"""

    args = arg.extract_plain_text().strip()

    if not args:
        await anime_view.finish("请指定季度，格式如：2025年4月")

    # 解析参数
    result = parse_single_date(args)
    if not result[0]:
        await anime_view.finish("季度格式错误，请使用如：2025年4月")
    year, month = result

    # 验证年份范围
    if not validate_year(year):
        await anime_view.finish("年份范围超出")

    # 获取月份名称
    month_name = MONTH_NAMES.get(month, f"{month}月")

    # 获取该季度的番剧
    season_animes = bgm_manager.get_anime_by_season(year, month)

    if not season_animes:
        await anime_view.finish(f"{year}年{month_name}季度没有找到番剧数据")

    # 按评分降序排列（评分缺失的排在最后）
    def sort_key(item):
        title, info = item
        score = info.get('rating', {}).get('score')
        if score is None:
            return -1
        return float(score)

    season_animes.sort(key=sort_key, reverse=True)

    # 设置会话
    set_session(
        event,
        'view_season',  # 会话类型
        search_results=season_animes,  # 搜索结果
        search_type="季度查看",
        search_query=f"{year}-{month:02d}",
        current_page=0,
        page_size=20,  # 季度查看每页显示20条
        view_year=year,
        view_month=month,
        view_month_name=month_name
    )

    session = get_user_session(event)

    # 格式化输出第一页
    selection_msg = format_season_results_page(session, f"{year}年{month_name}番剧")
    await anime_view.send(selection_msg)


@anime_view_week.handle()
async def handle_anime_view_week(event: Event, arg: Message = CommandArg()):
    """处理番剧星期查看指令"""

    args = arg.extract_plain_text().strip()
    season_arg = None
    target_weekday = None

    if not args:
        await anime_view_week.finish("请指定季度，格式如：2025年4月 或 2025年4月 星期一")

    # 解析参数
    parts = args.split()
    if len(parts) == 1:
        season_arg = parts[0]
        target_weekday = None
    elif len(parts) == 2:
        season_arg = parts[0]
        target_weekday = parts[1]
    else:
        await anime_view_week.finish("参数格式错误，请使用：2025年4月 或 2025年4月 星期一")

    # 解析季度参数
    result = parse_single_date(season_arg)
    if not result[0]:
        await anime_view_week.finish("季度格式错误，请使用如：2025年4月")
    year, month = result

    # 验证年份范围
    if not validate_year(year):
        await anime_view_week.finish("年份范围超出")

    # 获取月份名称
    month_name = MONTH_NAMES.get(month, f"{month}月")

    weekday_mapping = {
        '星期一': '星期一', '周一': '星期一', '礼拜一': '星期一',
        '星期二': '星期二', '周二': '星期二', '礼拜二': '星期二',
        '星期三': '星期三', '周三': '星期三', '礼拜三': '星期三',
        '星期四': '星期四', '周四': '星期四', '礼拜四': '星期四',
        '星期五': '星期五', '周五': '星期五', '礼拜五': '星期五',
        '星期六': '星期六', '周六': '星期六', '礼拜六': '星期六',
        '星期日': '星期日', '周日': '星期日', '星期天': '星期日', '礼拜天': '星期日'
    }

    if target_weekday:
        normalized_weekday = weekday_mapping.get(target_weekday)
        if not normalized_weekday:
            await anime_view_week.finish("请使用正确的星期格式，如：星期一、周二、周三等")
        target_weekday = normalized_weekday

    # 获取该季度的番剧并按星期分组
    weekday_groups = bgm_manager.get_anime_by_season_and_weekday(year, month)

    if not weekday_groups or all(not animes for animes in weekday_groups.values()):
        await anime_view_week.finish(f"{year}年{month_name}季度没有找到番剧数据")

    # 根据是否指定星期，构建不同的番剧列表
    if target_weekday:
        # 只显示指定星期的番剧
        if target_weekday in weekday_groups and weekday_groups[target_weekday]:
            filtered_animes = weekday_groups[target_weekday]
            search_query = f"{year}-{month:02d} {target_weekday}"
        else:
            await anime_view_week.finish(f"{year}年{month_name}季度{target_weekday}没有找到番剧")
            return
    else:
        # 显示所有番剧，按星期顺序排列
        filtered_animes = []
        weekday_order = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日', '其他']

        for weekday in weekday_order:
            if weekday in weekday_groups and weekday_groups[weekday]:
                # 为每个星期的番剧添加星期标签
                for title, info in weekday_groups[weekday]:
                    # 在番剧信息中添加星期标签，方便显示
                    if 'weekday' not in info:
                        info['weekday'] = weekday
                    filtered_animes.append((title, info))

        search_query = f"{year}-{month:02d} 所有星期"

    # 设置会话
    set_session(
        event,
        'view_week',  # 会话类型
        search_results=filtered_animes,  # 搜索结果
        search_type="星期查看",
        search_query=search_query,
        current_page=0,
        page_size=30,  # 星期查看每页显示30条
        view_year=year,
        view_month=month,
        view_month_name=month_name,
        view_target_weekday=target_weekday,
        view_weekday_groups=weekday_groups  # 保留分组信息用于显示
    )

    session = get_user_session(event)

    # 格式化输出第一页
    selection_msg = format_week_results_page(session)
    await anime_view_week.send(selection_msg)


@anime_view_today.handle()
async def handle_anime_view_today(event: Event):
    """处理今天有什么番指令"""

    # 获取当前日期
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_day = now.day

    # 获取当前星期
    weekdays_chinese = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_num = now.weekday()
    current_weekday = weekdays_chinese[weekday_num]

    # 获取当前季度
    season_year, season_month = get_current_season()

    # 获取月份名称
    month_name = MONTH_NAMES.get(season_month, f"{season_month}月")

    # 获取今天播出的番剧
    today_animes = bgm_manager.get_today_animes()

    if not today_animes:
        await anime_view_today.finish(
            f"今天是{current_year}年{current_month}月{current_day}日 {current_weekday}\n"
            f"在{season_year}年{month_name}季度中，{current_weekday}没有找到番剧播出"
        )

    # 设置会话
    set_session(
        event,
        'view_season',  # 使用季度查看会话类型
        search_results=today_animes,
        search_type="今天番剧",
        search_query=f"today-{current_weekday}",
        current_page=0,
        page_size=30,
        view_year=season_year,
        view_month=season_month,
        view_month_name=month_name
    )

    # 格式化输出
    output_lines = [
        f"今天是{current_year}年{current_month}月{current_day}日 {current_weekday}",
        f"在{season_year}年{month_name}季度中，{current_weekday}播出的番剧有："
    ]

    for i, (title, anime_info) in enumerate(today_animes[:30], 1):  # 最多显示30条
        basic_info = anime_info.get('basic_info', {})

        # 使用chinese_title，如果没有则使用original_title
        chinese_title = basic_info.get('chinese_title', '').strip()
        original_title = basic_info.get('original_title', '').strip()
        display_title = chinese_title if chinese_title else original_title

        # 获取评分
        rating_info = anime_info.get('rating', {})
        score = rating_info.get('score')
        score_text = f" 评分：{score}" if score else " 评分：暂无"

        if display_title:
            output_lines.append(f"{i}. {display_title}{score_text}")

    # 如果番剧数量超过30条，显示翻页提示
    if len(today_animes) > 30:
        output_lines.append("")
        output_lines.append(f"共有 {len(today_animes)} 部番剧，输入编号查看详情，或输入 'n' 查看更多")
    else:
        output_lines.append("")
        output_lines.append("输入编号查看详情")

    await anime_view_today.send("\n".join(output_lines))



