import tempfile
import re

from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Optional, Tuple
from .anime_data import BGMDataManager
from .anime_score import CharacterScoreManager, UserScoreManager
from ..config import FONTS_DIR

from nonebot import logger


# ==================== 角色评级图片生成器 ====================
class CharacterScoreImageGenerator:
    """角色评级图片生成器"""

    def __init__(self, bgm_manager: BGMDataManager, score_manager: CharacterScoreManager):
        self.bgm_manager = bgm_manager
        self.score_manager = score_manager
        self.cache_dir = bgm_manager.cache_dir

    async def generate_character_score_image(self, username: str) -> Optional[str]:
        """生成角色评级图片 - 添加调试信息"""
        try:
            self.score_manager.scores = self.score_manager.load_scores()

            # 获取用户角色评级数据
            user_scores = self.score_manager.get_character_scores_by_user(username)

            # 检查是否有评级数据
            total_characters = sum(len(chars) for chars in user_scores.values())
            if total_characters == 0:
                logger.debug(f"用户 {username} 没有角色评级数据")
                return None

            # 图片参数
            image_size = 300  # 每个角色图片的大小
            title_block_size = 335  # 等级标题块大小
            margin = 20  # 边距
            title_height = 250  # 头部标题高度
            level_spacing = 40  # 等级之间的间距
            row_spacing = 10  # 行内间距
            border_padding = 18  # 边框向外扩展的单位

            # 圆角参数
            corner_radius = 7  # 圆角半径

            # 颜色方案
            level_colors = {
                5: (255, 0, 0),  # 红色 - 夯
                4: (255, 255, 0),  # 黄色 - 顶级
                3: (255, 165, 0),  # 橙色 - 人上人
                2: (0, 0, 255),  # 蓝色 - 路边
                1: (144, 238, 144)  # 浅绿色 - 拉完了
            }

            # 计算图片总尺寸
            max_per_row = 10  # 每行最多图像数

            # 计算每个等级的行数和高度
            level_layouts = {}
            total_height = title_height + margin * 2

            for level in [5, 4, 3, 2, 1]:
                characters = user_scores[level]
                if not characters:
                    continue

                # 计算行数
                rows = (len(characters) + max_per_row - 1) // max_per_row
                # 计算角色区域的实际高度
                character_area_height = rows * image_size + (rows - 1) * row_spacing if rows > 0 else image_size
                # 等级区域高度 = 标题块高度与角色行高度的最大值
                level_height = max(title_block_size, character_area_height)

                level_layouts[level] = {
                    'characters': characters,
                    'rows': rows,
                    'height': level_height,
                    'character_area_height': character_area_height
                }

                total_height += level_height + level_spacing

            total_height = total_height - level_spacing + margin + 100

            # 计算最大宽度
            # 宽度 = 左侧标题块 + 右侧角色图片区域
            max_characters_per_row = 0
            for level in [5, 4, 3, 2, 1]:
                if level in level_layouts:
                    characters = level_layouts[level]['characters']
                    max_characters_per_row = max(max_characters_per_row, min(len(characters), max_per_row))

            total_width = title_block_size + margin + (10 * image_size) + margin * 2 + 30

            # 创建画布
            img = Image.new('RGB', (total_width, total_height), 'white')
            draw = ImageDraw.Draw(img)

            title_font = ImageFont.truetype(str(FONTS_DIR / "Alimama_DongFangDaKai_Regular.ttf"), 180)
            level_font = ImageFont.truetype(str(FONTS_DIR / "Alimama_DongFangDaKai_Regular.ttf"), 90)
            name_font = ImageFont.truetype(str(FONTS_DIR / "Alimama_DongFangDaKai_Regular.ttf"), 16)

            # 绘制头部标题
            title = f"{username} 角色排行"
            try:
                title_bbox = draw.textbbox((0, 0), title, font=title_font)
                title_width = title_bbox[2] - title_bbox[0]
                title_height_actual = title_bbox[3] - title_bbox[1]
            except:
                title_width = len(title) * 30
                title_height_actual = 50

            title_x = (total_width - title_width) // 2
            title_y = margin
            draw.text((title_x, title_y), title, fill='black', font=title_font)

            current_y = title_height

            # 下载所有角色图片
            all_characters = []
            for level in [5, 4, 3, 2, 1]:
                if level in level_layouts:
                    all_characters.extend([(level, char_name, anime_title, image_url)
                                           for char_name, anime_title, _, image_url in
                                           level_layouts[level]['characters']])

            character_images = await self.download_character_images_batch(all_characters)

            # 绘制每个等级
            for level in [5, 4, 3, 2, 1]:
                if level not in level_layouts:
                    continue

                layout = level_layouts[level]
                characters = layout['characters']
                level_height = layout['height']
                character_area_height = layout['character_area_height']
                rows = layout['rows']

                # 固定贴图区域宽度为10个角色的宽度
                character_area_width = 10 * image_size

                # 创建等级标题块
                level_name = self.score_manager.get_level_display_name(level)
                level_color = level_colors.get(level, (200, 200, 200))

                # 创建等级标题块的图像
                title_block = Image.new('RGBA', (title_block_size, title_block_size), (0, 0, 0, 0))
                title_draw = ImageDraw.Draw(title_block)
                title_draw.rectangle([0, 0, title_block_size, title_block_size], fill=level_color)
                title_block = self.circle_corner(title_block, corner_radius)

                img.paste(title_block, (margin, current_y), title_block)

                # 在等级标题块上绘制文字
                try:
                    level_bbox = draw.textbbox((0, 0), level_name, font=level_font)
                    level_width = level_bbox[2] - level_bbox[0]
                    level_text_height = level_bbox[3] - level_bbox[1]
                except:
                    level_width = len(level_name) * 50
                    level_text_height = 60

                level_x = margin + (title_block_size - level_width) // 2
                level_y = current_y + (title_block_size - level_text_height) // 2
                draw.text((level_x, level_y), level_name, fill='black', font=level_font)

                # 绘制角色图片
                char_start_x = margin + title_block_size + margin + 20
                char_current_y = current_y + 18

                # 创建贴图区域的圆角边框
                border_width = 10
                border_rect = [
                    char_start_x - border_padding,
                    char_current_y - border_padding,
                    char_start_x + character_area_width + border_padding,
                    char_current_y + character_area_height + border_padding
                ]

                # 创建边框图像
                border_img = Image.new('RGBA', (
                    int(border_rect[2] - border_rect[0]),
                    int(border_rect[3] - border_rect[1])
                ), (0, 0, 0, 0))

                border_draw = ImageDraw.Draw(border_img)
                border_draw.rectangle([0, 0, border_img.width, border_img.height],
                                      outline=level_color, width=border_width)
                border_img = self.circle_corner(border_img, corner_radius)

                img.paste(border_img, (int(border_rect[0]), int(border_rect[1])), border_img)

                # 分组处理角色
                for i in range(0, len(characters), max_per_row):
                    row_chars = characters[i:i + max_per_row]

                    # 绘制一行角色
                    for j, (char_name, anime_title, _, image_url) in enumerate(row_chars):
                        x = char_start_x + j * image_size

                        # 获取角色图片
                        image_key = f"{char_name}||{anime_title}"
                        char_image = character_images.get(image_key)

                        if char_image:
                            # 粘贴处理后的图片
                            img.paste(char_image, (x, char_current_y))
                        else:
                            # 绘制占位框和角色名
                            draw.rectangle([x, char_current_y, x + image_size, char_current_y + image_size],
                                           outline='gray', fill='lightgray')

                            # 处理角色名显示
                            display_name = self.format_character_name(char_name)
                            try:
                                name_bbox = draw.textbbox((0, 0), display_name, font=name_font)
                                name_width = name_bbox[2] - name_bbox[0]
                                name_height = name_bbox[3] - name_bbox[1]
                            except:
                                name_width = len(display_name) * 10
                                name_height = 20

                            name_x = x + (image_size - name_width) // 2
                            name_y = char_current_y + (image_size - name_height) // 2

                            draw.text((name_x, name_y), display_name, fill='black', font=name_font)

                    char_current_y += image_size + row_spacing

                # 计算当前等级的实际高度（包括边框扩展）
                current_level_actual_height = max(level_height, border_rect[3] - current_y)

                # 移动到下一个等级区域
                current_y += current_level_actual_height + level_spacing

            final_height = min(total_height, current_y + 100)
            if final_height < total_height:
                img = img.crop((0, 0, total_width, final_height))

            # 保存图片
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            img.save(temp_file.name, 'JPEG', quality=90)

            return temp_file.name

        except Exception as e:
            logger.opt(exception=True).error("生成角色评级图片失败")
            return None

    @staticmethod
    def circle_corner(img, radii):
        """创建圆角效果"""
        circle = Image.new('L', (radii * 2, radii * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, radii * 2, radii * 2), fill=255)

        if img.mode != 'RGBA':
            img = img.convert("RGBA")

        w, h = img.size

        alpha = Image.new('L', img.size, 255)
        alpha.paste(circle.crop((0, 0, radii, radii)), (0, 0))
        alpha.paste(circle.crop((radii, 0, radii * 2, radii)), (w - radii, 0))
        alpha.paste(circle.crop((radii, radii, radii * 2, radii * 2)), (w - radii, h - radii))
        alpha.paste(circle.crop((0, radii, radii, radii * 2)), (0, h - radii))

        white_bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        white_bg.paste(img, (0, 0), img)
        white_bg.putalpha(alpha)

        return white_bg

    def format_character_name(self, name: str) -> str:
        """格式化角色名显示"""
        if len(name) <= 9:
            return name

        # 如果超过9个字符，每3个字符换行
        chunks = [name[i:i + 3] for i in range(0, min(len(name), 9), 3)]
        return '\n'.join(chunks)

    def generate_cache_filename(self, character_name: str, anime_title: str) -> str:
        """生成缓存文件名：使用角色名和番剧名的组合"""

        # 清理文件名中的非法字符
        safe_char_name = re.sub(r'[<>:"/\\|?*]', '_', character_name)
        safe_anime_title = re.sub(r'[<>:"/\\|?*]', '_', anime_title)

        # 限制文件名长度
        max_length = 50
        if len(safe_char_name) > max_length:
            safe_char_name = safe_char_name[:max_length]
        if len(safe_anime_title) > max_length:
            safe_anime_title = safe_anime_title[:max_length]

        return f"character_{safe_char_name}_{safe_anime_title}.jpg"

    async def download_character_images_batch(self, characters: List[Tuple[int, str, str, str]]) -> Dict[str, Image.Image]:
        """批量下载角色图片"""
        character_images = {}

        download_tasks = []
        for level, char_name, anime_title, image_url in characters:
            if image_url:
                task = (image_url, "character", char_name, anime_title)
                download_tasks.append(task)

        downloaded_images = await self.bgm_manager.image_manager.batch_download_images(download_tasks)

        # 处理下载的图片
        for level, char_name, anime_title, image_url in characters:
            try:
                cache_key = self.bgm_manager.image_manager.get_cache_key(
                    "character", char_name, anime_title
                )

                if cache_key in downloaded_images:
                    image_path = downloaded_images[cache_key]
                    char_image = Image.open(image_path)
                    processed_image = self.process_character_image(char_image)
                    character_images[f"{char_name}||{anime_title}"] = processed_image
            except Exception as e:
                logger.warning(f"处理角色图片失败: {char_name}")

        return character_images

    def process_character_image(self, image: Image.Image) -> Image.Image:
        """处理角色图片尺寸为300x300"""
        target_size = 300

        # 获取原始尺寸
        width, height = image.size

        if width >= target_size:
            scale_factor = target_size / width
            new_height = int(height * scale_factor)
            resized_image = image.resize((target_size, new_height), Image.Resampling.LANCZOS)

            if new_height > target_size:
                cropped_image = resized_image.crop((0, 0, target_size, target_size))
                return cropped_image
            else:
                final_image = Image.new('RGB', (target_size, target_size), 'white')
                y_offset = (target_size - new_height) // 2
                final_image.paste(resized_image, (0, y_offset))
                return final_image

        else:
            # 宽度小于300，尝试放大
            if width * 2 <= target_size:
                max_scale = min(target_size / width, 3)
                new_width = int(width * max_scale)
                new_height = int(height * max_scale)

                if new_width > target_size:
                    new_width = target_size
                    new_height = int(height * (target_size / width))

                resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # 创建目标尺寸的画布
                final_image = Image.new('RGB', (target_size, target_size), 'white')
                x_offset = (target_size - new_width) // 2
                y_offset = (target_size - new_height) // 2
                final_image.paste(resized_image, (x_offset, y_offset))
                return final_image
            else:
                # 无法有效放大，使用原始尺寸居中显示
                final_image = Image.new('RGB', (target_size, target_size), 'white')
                x_offset = (target_size - width) // 2
                y_offset = (target_size - height) // 2
                final_image.paste(image, (x_offset, y_offset))
                return final_image


# ==================== 番剧评分图片生成器 ====================
class AnimeScoreImageGenerator:
    """番剧评分图片生成器"""

    def __init__(self, bgm_manager: BGMDataManager, score_manager: UserScoreManager):
        self.bgm_manager = bgm_manager
        self.score_manager = score_manager
        self.cache_dir = bgm_manager.cache_dir

    async def generate_anime_score_image(self, username: str, score_range: str = None) -> Optional[str]:
        """生成番剧评分图片"""
        try:
            self.score_manager.scores = self.score_manager.load_scores()

            # 获取用户所有评分
            all_scores = self.score_manager.get_all_scores_by_user(username)

            if not all_scores:
                logger.debug(f"用户 {username} 没有番剧评分数据")
                return None

            # 如果有分数范围，进行筛选
            if score_range:
                try:
                    # 解析分数范围
                    if '-' in score_range:
                        range_parts = score_range.split('-')
                        min_score = float(range_parts[0])
                        max_score = float(range_parts[1])

                        if min_score > max_score:
                            min_score, max_score = max_score, min_score
                    else:
                        # 单个数值
                        min_score = max_score = float(score_range)

                    filtered_scores = [(anime, score) for anime, score in all_scores
                                       if min_score <= score <= max_score]
                except Exception as e:
                    logger.warning("解析分数范围失败")
                    filtered_scores = all_scores
            else:
                filtered_scores = all_scores

            if not filtered_scores:
                logger.debug(f"用户 {username} 在指定范围内没有评分数据")
                return None

            sorted_scores = sorted(filtered_scores, key=lambda x: x[1], reverse=True)

            # 获取番剧详细信息
            anime_details = []
            for anime_title, score in sorted_scores:
                anime_info = self.bgm_manager.all_data.get(anime_title)
                if anime_info:
                    cover_url = anime_info.get('cover_url')
                    basic_info = anime_info.get('basic_info', {})
                    japanese_title = basic_info.get('original_title', '') or anime_info.get('title_jp', '')
                    chinese_title = basic_info.get('chinese_title', '') or anime_info.get('title_cn', '')

                    anime_details.append({
                        'title_cn': anime_title,
                        'title_jp': japanese_title or chinese_title,  # 优先日文名
                        'score': score,
                        'cover_url': cover_url,
                        'anime_info': anime_info
                    })

            if not anime_details:
                logger.warning("无法获取番剧详细信息")
                return None

            # 创建图片
            return await self._create_score_image(username, anime_details, score_range)

        except Exception as e:
            logger.opt(exception=True).error("生成番剧评分图片失败")
            return None

    async def _create_score_image(self, username: str, anime_details: List[Dict], score_range: str = None) -> Optional[str]:
        """创建评分图片"""
        try:
            scores = [anime['score'] for anime in anime_details]
            unique_scores = sorted(set(scores), reverse=True)

            # 图片参数
            image_size = 267  # 每个番剧封面的大小
            title_block_size = 300  # 左侧标题块大小
            margin = 20  # 边距
            title_height = 250  # 头部标题高度
            level_spacing = 40  # 等级之间的间距
            row_spacing = 10  # 行内间距
            border_padding = 18  # 边框向外扩展的单位

            # 圆角参数
            corner_radius = 7  # 圆角半径

            # （红→橙→黄→绿→蓝→浅蓝）
            level_count = len(unique_scores)
            level_colors = self._generate_gradient_colors(level_count)

            # 将等级颜色映射到具体的分数
            score_to_color = {score: level_colors[i] for i, score in enumerate(unique_scores)}

            # 按分数分组番剧
            level_groups = {}
            for score in unique_scores:
                level_groups[score] = [anime for anime in anime_details if anime['score'] == score]

            # 计算每个等级的行数和高度
            level_layouts = {}
            total_height = title_height + margin * 2
            max_per_row = 10

            for score in unique_scores:
                animes = level_groups[score]
                if not animes:
                    continue

                # 计算行数
                rows = (len(animes) + max_per_row - 1) // max_per_row
                # 计算番剧区域的实际高度
                anime_area_height = rows * image_size + (rows - 1) * row_spacing if rows > 0 else image_size
                # 等级区域高度
                level_height = max(title_block_size, anime_area_height)

                level_layouts[score] = {
                    'animes': animes,
                    'rows': rows,
                    'height': level_height,
                    'anime_area_height': anime_area_height
                }

                # 使用实际内容高度计算总高度
                total_height += level_height + level_spacing

            total_height = total_height - level_spacing + margin + 100

            # 计算最大宽度
            # 宽度 = 左侧标题块 + 右侧番剧封面区域
            max_animes_per_row = 0
            for score in unique_scores:
                if score in level_layouts:
                    animes = level_layouts[score]['animes']
                    max_animes_per_row = max(max_animes_per_row, min(len(animes), max_per_row))

            total_width = title_block_size + margin + (max_animes_per_row * image_size) + margin * 2 + 30

            img = Image.new('RGB', (total_width, total_height), 'white')
            draw = ImageDraw.Draw(img)

            title_font = ImageFont.truetype(str(FONTS_DIR / "Alimama_DongFangDaKai_Regular.ttf"), 120)
            level_font = ImageFont.truetype(str(FONTS_DIR / "Alimama_DongFangDaKai_Regular.ttf"), 80)
            anime_font = ImageFont.truetype(str(FONTS_DIR / "Alimama_DongFangDaKai_Regular.ttf"), 14)

            # 绘制头部标题
            range_text = f" ({score_range})" if score_range else ""
            title = f"{username} 番剧评分{range_text}"
            try:
                title_bbox = draw.textbbox((0, 0), title, font=title_font)
                title_width = title_bbox[2] - title_bbox[0]
                title_height_actual = title_bbox[3] - title_bbox[1]
            except:
                title_width = len(title) * 30
                title_height_actual = 50

            title_x = (total_width - title_width) // 2
            title_y = margin + 15
            draw.text((title_x, title_y), title, fill='black', font=title_font)

            current_y = title_height

            # 下载所有番剧封面
            download_tasks = []
            for score in unique_scores:
                if score in level_layouts:
                    for anime in level_layouts[score]['animes']:
                        if anime['cover_url']:
                            anime_id = anime['anime_info'].get('id', 'unknown')
                            task = (anime['cover_url'], "cover", anime_id)
                            download_tasks.append(task)

            downloaded_images = await self.bgm_manager.image_manager.batch_download_images(download_tasks)

            # 绘制每个评分等级
            for score in unique_scores:
                if score not in level_layouts:
                    continue

                layout = level_layouts[score]
                animes = layout['animes']
                level_height = layout['height']
                anime_area_height = layout['anime_area_height']
                rows = layout['rows']

                # 计算贴图区域宽度
                anime_area_width = min(len(animes), max_per_row) * image_size

                # 等级颜色
                level_color = score_to_color[score]

                # 创建等级标题块（带圆角）
                level_name = f"{score:.1f}"

                title_block = Image.new('RGBA', (title_block_size, title_block_size), (0, 0, 0, 0))
                title_draw = ImageDraw.Draw(title_block)
                title_draw.rectangle([0, 0, title_block_size, title_block_size], fill=level_color)
                title_block = CharacterScoreImageGenerator.circle_corner(title_block, corner_radius)

                # 将等级标题块粘贴到主图像
                img.paste(title_block, (margin, current_y), title_block)

                # 在等级标题块上绘制评分
                try:
                    level_bbox = draw.textbbox((0, 0), level_name, font=level_font)
                    level_width = level_bbox[2] - level_bbox[0]
                    level_text_height = level_bbox[3] - level_bbox[1]
                except:
                    level_width = len(level_name) * 30
                    level_text_height = 40

                level_x = margin + (title_block_size - level_width) // 2
                level_y = current_y + (title_block_size - level_text_height) // 2
                draw.text((level_x, level_y), level_name, fill='black', font=level_font)

                # 绘制番剧封面（从标题块右侧开始）
                anime_start_x = margin + title_block_size + margin + 20
                anime_current_y = current_y + 18

                # 创建贴图区域的圆角边框
                border_width = 10
                border_rect = [
                    anime_start_x - border_padding,
                    anime_current_y - border_padding,
                    anime_start_x + anime_area_width + border_padding,
                    anime_current_y + anime_area_height + border_padding
                ]

                # 创建边框图像
                border_img = Image.new('RGBA', (
                    int(border_rect[2] - border_rect[0]),
                    int(border_rect[3] - border_rect[1])
                ), (0, 0, 0, 0))

                border_draw = ImageDraw.Draw(border_img)
                border_draw.rectangle([0, 0, border_img.width, border_img.height],
                                      outline=level_color, width=border_width)
                border_img = CharacterScoreImageGenerator.circle_corner(border_img, corner_radius)

                # 将边框粘贴到主图像
                img.paste(border_img, (int(border_rect[0]), int(border_rect[1])), border_img)

                # 分组处理番剧
                for i in range(0, len(animes), max_per_row):
                    row_animes = animes[i:i + max_per_row]

                    # 绘制一行番剧
                    for j, anime in enumerate(row_animes):
                        x = anime_start_x + j * image_size

                        # 下载并处理封面
                        anime_id = anime['anime_info'].get('id', 'unknown')
                        cache_key = self.bgm_manager.image_manager.get_cache_key("cover", anime_id)

                        if cache_key in downloaded_images:
                            cover_path = downloaded_images[cache_key]
                            try:
                                cover_image = Image.open(cover_path)
                                processed_cover = self._process_cover_image(cover_image, image_size)

                                # 粘贴封面
                                img.paste(processed_cover, (x, anime_current_y))

                            except Exception as e:
                                logger.warning(f"处理封面失败: {anime['title_cn']}")
                                # 绘制占位框
                                draw.rectangle([x, anime_current_y, x + image_size, anime_current_y + image_size],
                                               outline='gray', fill='lightgray')
                                # 在占位框上绘制番剧名
                                anime_name = anime['title_cn'][:6] if anime['title_cn'] else "无封面"
                                name_bbox = draw.textbbox((0, 0), anime_name, font=anime_font)
                                name_width = name_bbox[2] - name_bbox[0]
                                name_x = x + (image_size - name_width) // 2
                                name_y = anime_current_y + (image_size - 20) // 2
                                draw.text((name_x, name_y), anime_name, fill='black', font=anime_font)
                        else:
                            # 绘制占位框
                            draw.rectangle([x, anime_current_y, x + image_size, anime_current_y + image_size],
                                           outline='gray', fill='lightgray')
                            # 在占位框上绘制番剧名
                            anime_name = anime['title_cn'][:6] if anime['title_cn'] else "无封面"
                            name_bbox = draw.textbbox((0, 0), anime_name, font=anime_font)
                            name_width = name_bbox[2] - name_bbox[0]
                            name_x = x + (image_size - name_width) // 2
                            name_y = anime_current_y + (image_size - 20) // 2
                            draw.text((name_x, name_y), anime_name, fill='black', font=anime_font)

                    anime_current_y += image_size + row_spacing

                # 计算当前等级的实际高度
                current_level_actual_height = max(level_height, border_rect[3] - current_y)

                # 移动到下一个等级区域
                current_y += current_level_actual_height + level_spacing

            final_height = min(total_height, current_y + 100)
            if final_height < total_height:
                img = img.crop((0, 0, total_width, final_height))

            # 保存图片
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            img.save(temp_file.name, 'JPEG', quality=90)

            return temp_file.name

        except Exception as e:
            logger.opt(exception=True).error("创建番剧评分图片失败")
            return None

    @staticmethod
    def _generate_gradient_colors(level_count: int) -> List[tuple]:
        """根据等级数量生成渐变色（红→橙→黄→绿→蓝→浅蓝）"""
        if level_count <= 0:
            return [(255, 255, 255)]

        key_colors = [
            (255, 0, 0),  # 红色
            (255, 165, 0),  # 橙色
            (255, 255, 0),  # 黄色
            (0, 255, 0),  # 绿色
            (0, 0, 255),  # 蓝色
            (173, 216, 230)  # 浅蓝色
        ]

        # 如果等级数量少于关键颜色数量，直接取前几个颜色
        if level_count <= len(key_colors):
            return key_colors[:level_count]

        # 生成渐变颜色
        colors = []
        for i in range(level_count):
            # 在关键颜色之间插值
            t = i / (level_count - 1) if level_count > 1 else 0
            # 计算在关键颜色列表中的位置
            color_idx = t * (len(key_colors) - 1)
            idx1 = int(color_idx)
            idx2 = min(idx1 + 1, len(key_colors) - 1)

            # 插值因子
            factor = color_idx - idx1

            # 线性插值
            r = int(key_colors[idx1][0] + (key_colors[idx2][0] - key_colors[idx1][0]) * factor)
            g = int(key_colors[idx1][1] + (key_colors[idx2][1] - key_colors[idx1][1]) * factor)
            b = int(key_colors[idx1][2] + (key_colors[idx2][2] - key_colors[idx1][2]) * factor)

            colors.append((r, g, b))

        return colors

    def _process_cover_image(self, image: Image.Image, target_size: int) -> Image.Image:
        """处理番剧封面图片尺寸"""
        # 获取原始尺寸
        width, height = image.size

        if width >= target_size:
            # 缩放宽度到目标大小，保持比例
            scale_factor = target_size / width
            new_height = int(height * scale_factor)
            resized_image = image.resize((target_size, new_height), Image.Resampling.LANCZOS)

            # 如果高度大于目标大小，从顶部截取
            if new_height > target_size:
                cropped_image = resized_image.crop((0, 0, target_size, target_size))
                return cropped_image
            else:
                # 高度不足，创建白色背景并居中粘贴
                final_image = Image.new('RGB', (target_size, target_size), 'white')
                y_offset = (target_size - new_height) // 2
                final_image.paste(resized_image, (0, y_offset))
                return final_image
        else:
            # 宽度小于目标大小，尝试放大
            if width * 2 <= target_size:
                # 计算最大可能的放大倍数
                max_scale = min(target_size / width, 3)
                new_width = int(width * max_scale)
                new_height = int(height * max_scale)

                if new_width > target_size:
                    new_width = target_size
                    new_height = int(height * (target_size / width))

                resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # 创建目标尺寸的画布
                final_image = Image.new('RGB', (target_size, target_size), 'white')
                x_offset = (target_size - new_width) // 2
                y_offset = (target_size - new_height) // 2
                final_image.paste(resized_image, (x_offset, y_offset))
                return final_image
            else:
                # 无法有效放大，使用原始尺寸居中显示
                final_image = Image.new('RGB', (target_size, target_size), 'white')
                x_offset = (target_size - width) // 2
                y_offset = (target_size - height) // 2
                final_image.paste(image, (x_offset, y_offset))
                return final_image