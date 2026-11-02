from typing import Dict, List, Optional

from .anime_data import BGMDataManager

from nonebot import logger


# ==================== 标签管理器 ====================
class TagManager:
    """BGM 标签管理器"""

    def __init__(self, bgm_manager: BGMDataManager):
        self.bgm_manager = bgm_manager

    # ---------- 数据访问 ----------

    def ensure_loaded(self) -> Dict:
        """确保数据已加载，返回当前数据本身"""
        if self.bgm_manager.all_data is None:
            self.bgm_manager.load_all_data()
        return self.bgm_manager.all_data or {}

    def find_anime(self, anime_info: Dict) -> Optional[Dict]:
        """按条目 id 在最新数据中定位记录（会话里可能留着旧对象）"""
        if not isinstance(anime_info, dict):
            return None
        anime_id = anime_info.get('id')
        if anime_id is None:
            return None
        return self.ensure_loaded().get(str(anime_id))

    def save_all_data(self) -> bool:
        """落盘交给 BGMDataManager，保持单一写出口"""
        return self.bgm_manager.save_all_data()

    def get_anime_tags(self, anime_info: Dict) -> List[str]:
        """获取番剧的标签列表"""
        if not isinstance(anime_info, dict):
            return []
        tags = anime_info.get('tags', [])
        return [tag['name'] for tag in tags] if isinstance(tags, list) else []

    # ---------- 标签增删 ----------

    def add_tag(self, anime_info: Dict, tag_name: str, title: str = "") -> bool:
        """为番剧添加标签"""
        try:
            target_anime = self.find_anime(anime_info)
            if target_anime is None:
                logger.warning(f"标签操作: 找不到番剧 '{title or anime_info}'")
                return False

            if 'tags' not in target_anime or not isinstance(target_anime['tags'], list):
                target_anime['tags'] = []

            if any(t.get('name') == tag_name for t in target_anime['tags']):
                return False

            target_anime['tags'].append({'name': tag_name, 'count': 0})

            if anime_info is not target_anime:
                if 'tags' not in anime_info or not isinstance(anime_info['tags'], list):
                    anime_info['tags'] = []
                if not any(t.get('name') == tag_name for t in anime_info['tags']):
                    anime_info['tags'].append({'name': tag_name, 'count': 0})

            if self.save_all_data():
                logger.info(f"添加标签 '{tag_name}' 到《{title}》(id={target_anime.get('id')})")
                return True
            return False

        except Exception:
            logger.opt(exception=True).error("添加标签失败")
            return False

    def remove_tag(self, anime_info: Dict, tag_name: str, title: str = "") -> bool:
        """删除番剧的标签"""
        try:
            target_anime = self.find_anime(anime_info)
            if target_anime is None:
                logger.warning(f"标签操作: 找不到番剧 '{title or anime_info}'")
                return False

            if 'tags' not in target_anime or not isinstance(target_anime['tags'], list):
                return False

            original_length = len(target_anime['tags'])
            target_anime['tags'] = [tag for tag in target_anime['tags']
                                    if tag.get('name') != tag_name]

            if len(target_anime['tags']) == original_length:
                return False

            if anime_info is not target_anime and isinstance(anime_info, dict):
                if 'tags' in anime_info and isinstance(anime_info['tags'], list):
                    anime_info['tags'] = [tag for tag in anime_info['tags']
                                          if tag.get('name') != tag_name]

            if self.save_all_data():
                logger.info(f"删除标签 '{tag_name}' 从《{title}》(id={target_anime.get('id')})")
                return True
            return False

        except Exception:
            logger.opt(exception=True).error("删除标签失败")
            return False

    # ---------- 展示 ----------

    def format_tags_display(self, tags: List[str]) -> str:
        """格式化标签显示"""
        if not tags:
            return "暂无标签"

        return "，".join(tags)
