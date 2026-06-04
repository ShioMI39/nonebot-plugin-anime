import json

from typing import Dict, List, Tuple, Optional
from ..config import SCORE_JSON, CHARACTER_SCORE_JSON

from nonebot import logger




# ==================== 用户评分管理器 ====================
class UserScoreManager:
    """用户评分管理器"""

    def __init__(self):
        self.score_file = SCORE_JSON
        self.scores = self.load_scores()

    def load_scores(self) -> Dict:
        """加载用户评分数据"""
        try:
            if self.score_file.exists():
                with open(self.score_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception:
            logger.opt(exception=True).error("加载评分数据失败")
            return {}

    def save_scores(self) -> bool:
        """保存用户评分数据"""
        try:
            self.score_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.score_file, 'w', encoding='utf-8') as f:
                json.dump(self.scores, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            logger.opt(exception=True).error("保存评分数据失败")
            return False

    def add_user_score(self, anime_title: str, username: str, score: float) -> bool:
        """添加用户评分"""
        try:
            if anime_title not in self.scores:
                self.scores[anime_title] = {}
            self.scores[anime_title][username] = score
            logger.info(f"用户 {username} 对《{anime_title}》评分: {score}")
            return self.save_scores()
        except Exception:
            logger.opt(exception=True).error("添加用户评分失败")
            return False

    def get_user_scores_by_anime(self, anime_title: str) -> Dict[str, float]:
        """获取番剧的所有用户评分"""
        return self.scores.get(anime_title, {})

    def search_scores_by_user_and_score(self, username: str, target_score: float) -> List[str]:
        """搜索用户给的特定分数的所有番剧"""
        results = []

        for anime_title, user_scores in self.scores.items():
            for user, score in user_scores.items():
                if user == username and float(score) == target_score:
                    results.append(anime_title)
                    break

        return results

    def search_scores_by_user_and_score_range(self, username: str, min_score: float, max_score: float) -> Dict[
        float, List[str]]:
        """搜索用户给的特定分数范围内的所有番剧，按分数分组"""
        results = {}

        for anime_title, user_scores in self.scores.items():
            for user, score in user_scores.items():
                if user == username and min_score <= float(score) <= max_score:
                    score_float = float(score)
                    if score_float not in results:
                        results[score_float] = []
                    results[score_float].append(anime_title)

        # 按分数从高到低排序
        return dict(sorted(results.items(), key=lambda x: x[0], reverse=True))

    def format_user_scores_display(self, user_scores: Dict[str, float]) -> str:
        """格式化用户评分显示"""
        if not user_scores:
            return "暂无用户评分"

        score_list = [f"{user}{score}" for user, score in user_scores.items()]
        return "，".join(score_list)

    def get_sorted_user_scores(self, anime_title: str) -> List[Tuple[str, float]]:
        """获取番剧的用户评分并按分数排序（从高到低）"""
        user_scores = self.get_user_scores_by_anime(anime_title)
        return sorted(user_scores.items(), key=lambda x: x[1], reverse=True)

    def delete_user_score(self, anime_title: str, username: str) -> bool:
        """删除特定用户对特定番剧的评分"""
        try:
            if anime_title in self.scores and username in self.scores[anime_title]:
                del self.scores[anime_title][username]
                # 如果这个番剧没有其他评分了，删除整个番剧条目
                if not self.scores[anime_title]:
                    del self.scores[anime_title]
                return self.save_scores()
            return False
        except Exception:
            logger.opt(exception=True).error("删除用户评分失败")
            return False

    def get_all_scores_by_user(self, username: str) -> List[Tuple[str, float]]:
        """获取特定用户的所有评分，按分数从高到低排序"""
        user_scores = []
        for anime_title, scores_dict in self.scores.items():
            if username in scores_dict:
                user_scores.append((anime_title, scores_dict[username]))
        return sorted(user_scores, key=lambda x: x[1], reverse=True)

    def delete_all_scores_by_user(self, username: str) -> bool:
        """删除特定用户的所有评分"""
        try:
            anime_to_remove = []
            for anime_title, scores_dict in self.scores.items():
                if username in scores_dict:
                    del scores_dict[username]
                    if not scores_dict:
                        anime_to_remove.append(anime_title)

            for anime_title in anime_to_remove:
                del self.scores[anime_title]

            logger.info(f"已删除用户 {username} 的所有评分")
            return self.save_scores()
        except Exception:
            logger.opt(exception=True).error("删除用户所有评分失败")
            return False


# ==================== 角色评级管理器 ====================
class CharacterScoreManager:
    """角色评级管理器 - 修复版"""

    def __init__(self, bgm_manager):
        self.character_score_file = CHARACTER_SCORE_JSON
        self.scores = self.load_scores()
        self.bgm_manager = bgm_manager

        # 等级映射
        self.level_mapping = {
            5: "夯",
            4: "顶级",
            3: "人上人",
            2: "路边",
            1: "拉完了"
        }

    def load_scores(self) -> Dict:
        """加载角色评级数据"""
        try:
            if self.character_score_file.exists():
                with open(self.character_score_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"加载角色评分数据（{len(data)} 条）")
                    return self.validate_and_fix_data(data)
            else:
                logger.warning("角色评分文件不存在，创建空数据")
                return {}
        except Exception:
            logger.opt(exception=True).error("加载角色评级数据失败")
            return {}

    def validate_and_fix_data(self, data: Dict) -> Dict:
        fixed_data = {}
        needs_fix = False

        for character_key, character_data in data.items():
            if isinstance(character_data, dict) and 'scores' in character_data:
                fixed_data[character_key] = character_data
            else:
                needs_fix = True
                if '||' in character_key:
                    character_name, anime_title = character_key.split('||', 1)
                else:
                    character_name = character_key
                    anime_title = "未知番剧"

                fixed_data[character_key] = {
                    'character_name': character_name,
                    'anime_title': anime_title,
                    'image_url': None,
                    'scores': character_data,
                }

        if needs_fix:
            self.save_scores_immediate(fixed_data)

        return fixed_data

    def save_scores_immediate(self, data: Dict) -> bool:
        """保存数据"""
        try:
            self.character_score_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.character_score_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            logger.opt(exception=True).error("保存角色评级数据失败")
            return False

    def save_scores(self) -> bool:
        """保存角色评级数据"""
        try:
            self.character_score_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.character_score_file, 'w', encoding='utf-8') as f:
                json.dump(self.scores, f, ensure_ascii=False, indent=2)
            logger.debug(f"角色评分保存成功（{len(self.scores)} 条）")
            return True
        except Exception:
            logger.opt(exception=True).error("保存角色评级数据失败")
            return False

    def add_character_score(self, character_name: str, anime_title: str, username: str, score: int, image_url: str = None) -> bool:
        """添加角色评级"""
        try:
            character_key = f"{character_name}||{anime_title}"

            if character_key not in self.scores:
                if image_url is None:
                    image_url = self.find_character_image_url(character_name, anime_title)

                self.scores[character_key] = {
                    'character_name': character_name,
                    'anime_title': anime_title,
                    'image_url': image_url,
                    'scores': {}
                }

            self.scores[character_key]['scores'][username] = score
            logger.info(f"角色评分: {character_name}（{anime_title}）→ {username}: {score}")
            return self.save_scores()
        except Exception:
            logger.opt(exception=True).error("添加角色评级失败")
            return False

    def find_character_image_url(self, character_name: str, anime_title: str) -> Optional[str]:
        """查找角色图片URL"""
        try:
            results = self.bgm_manager.search_characters_by_name(character_name)

            for found_char_name, char_info in results:
                result_anime_title = char_info.get('anime_title', '')
                if (result_anime_title == anime_title
                        and found_char_name == character_name):
                    return char_info.get('image_url')

            for found_char_name, char_info in results:
                result_anime_title = char_info.get('anime_title', '')
                if (character_name in found_char_name or found_char_name in character_name
                        or anime_title in result_anime_title):
                    return char_info.get('image_url')

            if results:
                return results[0][1].get('image_url')

            return None

        except Exception:
            logger.warning("查找角色图片URL失败")
            return None

    def get_character_scores_by_user(self, username: str) -> Dict[str, List[Tuple[str, str, int, str]]]:
        """获取特定用户的所有角色评级，按等级分组（包含图片URL）- 修复版"""
        user_scores = {
            5: [],  # 夯
            4: [],  # 顶级
            3: [],  # 人上人
            2: [],  # 路边
            1: []  # 拉完了
        }

        for character_key, character_data in self.scores.items():
            scores_dict = character_data.get('scores', {})
            if username in scores_dict:
                score = scores_dict[username]
                character_name = character_data['character_name']
                anime_title = character_data['anime_title']
                image_url = character_data.get('image_url')

                user_scores[score].append((character_name, anime_title, score, image_url))

        return user_scores

    def delete_character_score(self, character_name: str, anime_title: str, username: str) -> bool:
        """删除特定用户对特定角色的评级"""
        try:
            character_key = f"{character_name}||{anime_title}"

            if character_key in self.scores and username in self.scores[character_key]['scores']:
                del self.scores[character_key]['scores'][username]

                if not self.scores[character_key]['scores']:
                    del self.scores[character_key]

                logger.info(f"已删除角色评分: {character_name} - {username}")
                return self.save_scores()

            logger.debug(f"未找到要删除的评分: {character_key} - {username}")
            return False
        except Exception:
            logger.opt(exception=True).error("删除角色评级失败")
            return False

    def get_all_character_scores_by_user(self, username: str) -> List[Tuple[str, str, int]]:
        """获取特定用户的所有角色评级，按等级从高到低排序"""
        user_scores = []

        for character_key, character_data in self.scores.items():
            scores_dict = character_data.get('scores', {})
            if username in scores_dict:
                score = scores_dict[username]
                character_name = character_data['character_name']
                anime_title = character_data['anime_title']
                user_scores.append((character_name, anime_title, score))

        return sorted(user_scores, key=lambda x: x[2], reverse=True)

    def delete_all_character_scores_by_user(self, username: str) -> bool:
        """删除特定用户的所有角色评级"""
        try:
            characters_to_remove = []

            for character_key, character_data in self.scores.items():
                scores_dict = character_data.get('scores', {})
                if username in scores_dict:
                    del scores_dict[username]
                    if not scores_dict:
                        characters_to_remove.append(character_key)

            for character_key in characters_to_remove:
                del self.scores[character_key]

            logger.info(f"已删除用户 {username} 的所有角色评分")
            return self.save_scores()

        except Exception:
            logger.opt(exception=True).error("删除用户所有角色评级失败")
            return False

    def get_level_display_name(self, score: int) -> str:
        """获取等级显示名称"""
        return self.level_mapping.get(score, f"未知({score})")

    def format_user_character_scores_display(self, username: str) -> str:
        """格式化用户角色评级显示"""
        user_scores = self.get_all_character_scores_by_user(username)

        if not user_scores:
            return f"{username} 暂无角色评级"

        message_parts = [f"{username} 角色排行榜\n"]

        # 按等级分组
        level_groups = {5: [], 4: [], 3: [], 2: [], 1: []}
        for char_name, anime_title, score in user_scores:
            level_groups[score].append((char_name, anime_title))

        # 从高到低显示等级
        for level in [5, 4, 3, 2, 1]:
            characters = level_groups[level]
            if characters:
                level_name = self.get_level_display_name(level)
                message_parts.append(f"{level_name}：")

                # 为每个角色添加编号
                for i, (char_name, anime_title) in enumerate(characters, 1):
                    message_parts.append(f"{i}. {char_name}（{anime_title}）")

                # 等级之间添加空行
                message_parts.append("")

        # 移除最后一个空行
        if message_parts and message_parts[-1] == "":
            message_parts.pop()

        return "\n".join(message_parts)