import math
from typing import Dict

from .anime_session import UserSession
from .anime_time import normalize_weekday


# ==================== 格式化函数 ====================
def format_search_results_page(session: UserSession, search_description: str) -> str:
    """格式化搜索结果页面"""
    total_results = len(session.search_results)
    session.total_pages = math.ceil(total_results / session.page_size)

    start_idx = session.current_page * session.page_size
    end_idx = min((session.current_page + 1) * session.page_size, total_results)
    current_results = session.search_results[start_idx:end_idx]

    result_list = []
    for i, (title, info) in enumerate(current_results, 1):
        # 根据会话类型显示不同信息
        if session.session_type == 'score_delete':
            # 评分删除会话：显示番剧名和分数
            score = info.get('score', '?')
            global_index = start_idx + i
            result_list.append(f"{global_index}. {title} {score}")
        else:
            # 其他会话：显示番剧基本信息
            basic_info = info.get('basic_info', {})
            episodes = basic_info.get('episodes', '?')
            year = basic_info.get('start_date', '')[:4] if basic_info.get('start_date') else '?'
            global_index = start_idx + i
            result_list.append(f"{global_index}. {title} ({episodes}话, {year}年)")

    page_info = f"第{session.current_page + 1}/{session.total_pages}页"

    page_commands = []
    if session.current_page > 0:
        page_commands.append("输入 'p' 或 '上一页' 查看上一页")
    if session.current_page < session.total_pages - 1:
        page_commands.append("输入 'n' 或 '下一页' 查看下一页")
    if session.total_pages > 1:
        page_commands.append(f"输入 'p2' 或 'page3' 跳转到指定页 (1~{session.total_pages})")

    page_navigation = "\n".join(page_commands) if page_commands else ""

    # 根据会话类型设置不同的提示信息
    if session.session_type == 'score_delete':
        message = f"{session.delete_username}已评分的番剧有 ({page_info}):\n" + "\n".join(result_list)
        message += f"\n\n请回复编号删除对应评分 (输入数字 1~{total_results})"
        message += "\n输入 '0' 退出删除模式"
    else:
        message = f"找到{total_results}个{search_description}的番剧 ({page_info}):\n" + "\n".join(result_list)
        message += f"\n\n请回复编号查看详情 (输入数字 1~{total_results})"

    if page_navigation:
        message += f"\n\n{page_navigation}"

    return message


def format_cv_select_page(session: UserSession, search_description: str) -> str:
    """格式化CV选择页面"""
    total_results = len(session.search_results)
    session.total_pages = math.ceil(total_results / session.page_size)

    start_idx = session.current_page * session.page_size
    end_idx = min((session.current_page + 1) * session.page_size, total_results)
    current_results = session.search_results[start_idx:end_idx]

    result_list = []
    for i, (cv_name, cv_info) in enumerate(current_results, 1):
        global_index = start_idx + i
        result_list.append(f"{global_index}. {cv_name}")

    page_info = f"第{session.current_page + 1}/{session.total_pages}页"

    page_commands = []
    if session.current_page > 0:
        page_commands.append("输入 'p' 或 '上一页' 查看上一页")
    if session.current_page < session.total_pages - 1:
        page_commands.append("输入 'n' 或 '下一页' 查看下一页")
    if session.total_pages > 1:
        page_commands.append(f"输入 'p2' 或 'page3' 跳转到指定页 (1~{session.total_pages})")

    page_navigation = "\n".join(page_commands) if page_commands else ""

    message = (
        f"找到{total_results}个{search_description}的CV ({page_info}):\n" +
        "\n".join(result_list)
    )

    if page_navigation:
        message += f"\n\n{page_navigation}"

    message += f"\n\n请回复编号选择CV (输入数字 1~{total_results})"
    return message


def _format_character_list_page(session: UserSession, title_template: str, action_hint: str) -> str:
    """角色列表模板"""
    total_results = len(session.search_results)
    session.total_pages = math.ceil(total_results / session.page_size)

    start_idx = session.current_page * session.page_size
    end_idx = min((session.current_page + 1) * session.page_size, total_results)
    current_results = session.search_results[start_idx:end_idx]

    result_list = []
    for i, (character_name, character_info) in enumerate(current_results, 1):
        anime_title = character_info.get('anime_title', '未知番剧')
        translated_name = character_info.get('translated_name', '')
        display_name = translated_name if translated_name else character_name
        global_index = start_idx + i
        result_list.append(f"{global_index}. {display_name} - {anime_title}")

    page_info = f"第{session.current_page + 1}/{session.total_pages}页"

    page_commands = []
    if session.current_page > 0:
        page_commands.append("输入 'p' 或 '上一页' 查看上一页")
    if session.current_page < session.total_pages - 1:
        page_commands.append("输入 'n' 或 '下一页' 查看下一页")
    if session.total_pages > 1:
        page_commands.append(f"输入 'p2' 或 'page3' 跳转到指定页 (1~{session.total_pages})")

    page_navigation = "\n".join(page_commands) if page_commands else ""

    message = title_template.format(total_results=total_results, page_info=page_info)
    message += "\n".join(result_list)

    if page_navigation:
        message += f"\n\n{page_navigation}"

    message += f"\n\n{action_hint} (输入数字 1~{total_results})"
    return message


def format_cv_search_results_page(session: UserSession, search_description: str) -> str:
    """格式化CV搜索结果页面"""
    return _format_character_list_page(
        session,
        title_template=f"找到{{total_results}}个{search_description}配音的角色 ({{page_info}}):\n",
        action_hint="请回复编号查看角色详细信息",
    )


def format_character_search_results_page(session: UserSession, search_description: str) -> str:
    """格式化角色搜索结果页面（角色评级用）"""
    return _format_character_list_page(
        session,
        title_template=f"找到{{total_results}}个{search_description}的角色 ({{page_info}}):\n",
        action_hint="请回复编号进行评级",
    )


def format_char_search_results_page(session: UserSession, search_description: str) -> str:
    """格式化角色名搜索结果页面（角色搜索用）"""
    return _format_character_list_page(
        session,
        title_template=f"找到{{total_results}}个{search_description}的角色 ({{page_info}}):\n",
        action_hint="请回复编号查看角色详细信息",
    )


def format_season_results_page(session: UserSession, title: str = "番剧列表") -> str:
    """格式化季度查看结果页面"""
    if not session.search_results:
        return f"没有找到{title}"

    total_results = len(session.search_results)
    session.total_pages = math.ceil(total_results / session.page_size)

    start_idx = session.current_page * session.page_size
    end_idx = min(start_idx + session.page_size, total_results)

    output_lines = [f"{title}（第{session.current_page + 1}/{session.total_pages}页）：",]
    output_lines.append("")

    for i in range(start_idx, end_idx):
        anime_title, anime_info = session.search_results[i]
        basic_info = anime_info.get('basic_info', {})

        # 使用chinese_title，如果没有则使用original_title
        chinese_title = basic_info.get('chinese_title', '').strip()
        original_title = basic_info.get('original_title', '').strip()
        display_title = chinese_title if chinese_title else original_title

        # 显示星期信息（如果有）
        broadcast_day = basic_info.get('broadcast_day', '').strip()
        day_info = f"【{broadcast_day}】" if broadcast_day else ""

        # 获取评分
        rating_info = anime_info.get('rating', {})
        score = rating_info.get('score')
        score_text = f" 评分：{score}" if score else " 评分：暂无"

        output_lines.append(f"{i + 1}. {display_title}{day_info}{score_text}")

    output_lines.append("")
    output_lines.append("输入编号查看详情，或输入 'n' 下一页 / 'p' 上一页")

    return "\n".join(output_lines)


def _weekday_index(weekday_groups: Dict) -> Dict[str, str]:
    """把 {星期: [(标题, 条目), ...]} 反向索引为 {条目id: 星期}"""
    index: Dict[str, str] = {}
    for day, items in (weekday_groups or {}).items():
        for _, info in items or []:
            if not isinstance(info, dict):
                continue
            anime_id = info.get('id')
            if anime_id is not None:
                index[str(anime_id)] = day
    return index


def _weekday_of(anime_info: Dict, index: Dict[str, str]) -> str:
    """条目的星期：优先取会话里的分组，退回 broadcast_day"""
    anime_id = anime_info.get('id')
    day = index.get(str(anime_id)) if anime_id is not None else None
    if day:
        return day
    basic_info = anime_info.get('basic_info') or {}
    return normalize_weekday(basic_info.get('broadcast_day', '')) or '其他'


def format_week_results_page(session: UserSession) -> str:
    """格式化星期查看结果页面"""
    if not session.search_results:
        target_weekday = getattr(session, 'view_target_weekday', None)
        if target_weekday:
            month_name = getattr(session, 'view_month_name', f"{getattr(session, 'view_month', '')}月")
            return f"{getattr(session, 'view_year', '')}年{month_name}季度{target_weekday}没有找到番剧"
        else:
            month_name = getattr(session, 'view_month_name', f"{getattr(session, 'view_month', '')}月")
            return f"{getattr(session, 'view_year', '')}年{month_name}季度没有找到番剧"

    total_results = len(session.search_results)
    session.total_pages = math.ceil(total_results / session.page_size)

    start_idx = session.current_page * session.page_size
    end_idx = min(start_idx + session.page_size, total_results)

    # 根据是否指定星期，显示不同的标题
    target_weekday = getattr(session, 'view_target_weekday', None)
    view_year = getattr(session, 'view_year', '')
    view_month_name = getattr(session, 'view_month_name', '')

    if target_weekday:
        title = f"{view_year}年{view_month_name}季度{target_weekday}番剧"
    else:
        title = f"{view_year}年{view_month_name}季度所有番剧"

    output_lines = [f"{title}（第{session.current_page + 1}/{session.total_pages}页）：",]
    output_lines.append("")  # 空行

    # 分组信息取自会话，条目本身不携带渲染字段
    weekday_groups = getattr(session, 'view_weekday_groups', {})
    if not target_weekday and weekday_groups:
        # 按星期顺序显示当前页（列表顺序即分组顺序）
        weekday_index = _weekday_index(weekday_groups)
        current_weekday = None

        for i, (anime_title, anime_info) in enumerate(session.search_results[start_idx:end_idx]):
            weekday = _weekday_of(anime_info, weekday_index)
            if weekday != current_weekday:
                if current_weekday is not None:  # 不同星期之间空一行
                    output_lines.append("")

                output_lines.append(f"{weekday}：")
                current_weekday = weekday

            basic_info = anime_info.get('basic_info', {})

            # 使用chinese_title，如果没有则使用original_title
            chinese_title = basic_info.get('chinese_title', '').strip()
            original_title = basic_info.get('original_title', '').strip()
            display_title = chinese_title if chinese_title else original_title

            # 获取评分
            rating_info = anime_info.get('rating', {})
            score = rating_info.get('score')
            score_text = f" 评分：{score}" if score else " 评分：暂无"

            output_lines.append(f"  {start_idx + i + 1}. {display_title}{score_text}")
    else:
        # 如果指定了具体星期或没有分组信息，直接显示列表
        for i in range(start_idx, end_idx):
            anime_title, anime_info = session.search_results[i]
            basic_info = anime_info.get('basic_info', {})

            # 使用chinese_title，如果没有则使用original_title
            chinese_title = basic_info.get('chinese_title', '').strip()
            original_title = basic_info.get('original_title', '').strip()
            display_title = chinese_title if chinese_title else original_title

            rating_info = anime_info.get('rating', {})
            score = rating_info.get('score')
            score_text = f" 评分：{score}" if score else " 评分：暂无"

            output_lines.append(f"{i + 1}. {display_title}{score_text}")

    output_lines.append("")
    output_lines.append("输入编号查看详情，或输入 'n' 下一页 / 'p' 上一页")

    return "\n".join(output_lines)