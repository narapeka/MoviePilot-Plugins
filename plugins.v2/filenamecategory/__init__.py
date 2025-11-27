from typing import Any, List, Dict, Tuple
import re

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import ChainEventType


class FileNameCategory(_PluginBase):
    # 插件名称
    plugin_name = "文件名多级分类"
    # 插件描述
    plugin_desc = "根据原始文件名中的关键字（支持正则表达式）在原分类下创建子分类。"
    # 插件图标
    plugin_icon = "Bookstack_A.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "narapeka"
    # 作者主页
    author_url = ""
    # 插件配置项ID前缀
    plugin_config_prefix = "filenamecategory_"
    # 加载顺序
    plugin_order = 1
    # 可使用的用户级别
    auth_level = 1

    _enabled = False
    _rules = []

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled", False)
            # 解析分类规则
            self._rules = self._parse_rules(config.get("rules", ""))

    def _parse_rules(self, rules_text: str) -> List[Dict[str, str]]:
        """
        解析文本格式的规则
        格式: path#keyword#category (每行一条规则)
        """
        rules = []
        if not rules_text:
            return rules
        
        for line in rules_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                # 跳过空行和注释行
                continue
            
            parts = line.split('#')
            if len(parts) >= 3:
                # path#keyword#category (keyword可为空表示匹配所有)
                path = parts[0].strip()
                pattern = parts[1].strip()
                category = parts[2].strip()
                
                if category:  # pattern可为空（表示匹配所有）
                    rules.append({
                        "path": path,
                        "pattern": pattern,
                        "category": category
                    })
                else:
                    logger.warning(f"文件名分类：跳过无效规则（category为空）: {line}")
            elif len(parts) == 2:
                # keyword#category (无path限制)
                pattern = parts[0].strip()
                category = parts[1].strip()
                
                if category:  # pattern可为空（表示匹配所有）
                    rules.append({
                        "path": "",
                        "pattern": pattern,
                        "category": category
                    })
                else:
                    logger.warning(f"文件名分类：跳过无效规则（category为空）: {line}")
            else:
                logger.warning(f"文件名分类：跳过格式错误的规则: {line}")
        
        return rules

    def _get_decade(self, year) -> str:
        """
        将年份转换为年代字符串 (例如: 1994 -> '1990s')
        """
        if not year:
            return "未知年代"
        try:
            decade = (int(year) // 10) * 10
            return f"{decade}s"
        except (ValueError, TypeError):
            return "未知年代"

    def _get_first_letter(self, name: str) -> str:
        """
        获取首字母用于分类
        - 中文: 使用拼音首字母
        - 英文: 使用首字符
        - 数字: 返回 "0-9"
        """
        if not name:
            return "其他"
        
        first_char = name[0]
        
        # 如果是数字，返回 "0-9"
        if first_char.isdigit():
            return "0-9"
        
        # 如果是ASCII字母，返回大写
        if first_char.isalpha() and ord(first_char) < 128:
            return first_char.upper()
        
        # 对于中文/其他字符，使用拼音
        try:
            import pypinyin
            pinyin = pypinyin.pinyin(first_char, style=pypinyin.Style.FIRST_LETTER)
            if pinyin and pinyin[0][0].isalpha():
                return pinyin[0][0].upper()
        except ImportError:
            logger.warning("pypinyin未安装，无法处理中文首字母")
        except Exception as e:
            logger.warning(f"获取首字母失败: {e}")
        
        return "其他"

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 获取当前配置
        current_config = self.get_config() or {}
        
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'style': 'white-space: pre-line; font-size: 13px',
                                            'text': '规则格式: 路径#关键字#分类\n'
                                                    '• 路径: 目标路径过滤，包含匹配，留空表示匹配所有路径\n'
                                                    '• 关键字: 支持正则表达式，不区分大小写，多个关键字用 | 分隔；留空或 .* 表示匹配所有文件\n'
                                                    '• 分类: 子分类名称，支持多级路径如 UHD/杜比视界，支持模板变量 {年代} {首字母}\n'
                                                    '说明: 每行一条规则，按顺序匹配，第一个匹配的规则生效。匹配后会在原分类下创建子分类。'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'rules',
                                            'label': '分类规则',
                                            'placeholder': '#HDHome#HDHome\n#CHD|CHDBits#CHDBits\n/电影##经典/{年代}\n##{首字母}',
                                            'rows': 8,
                                            'hint': '分类规则，每行一条，适用于电影和电视剧',
                                            'persistent-hint': True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'warning',
                                            'variant': 'tonal',
                                            'style': 'white-space: pre-line; font-size: 13px',
                                            'text': '规则示例:\n'
                                                    '• #CHD|CHDBits#CHDBits/原盘\n'
                                                    '   文件名包含 CHD 或 CHDBits 时，创建子分类: CHDBits/原盘/\n'
                                                    '• /电影##经典/{年代}\n'
                                                    '   目标路径包含 /电影 的所有文件，按年代分类: 经典/1990s/\n'
                                                    '• ##{首字母}\n'
                                                    '   所有文件按首字母分类: 黑客帝国 -> H/, Avatar -> A/, 12猴子 -> 0-9/\n'
                                                    '• /path/已整理#UHD|4K#4K\n'
                                                    '   目标路径包含 /path/已整理 且文件名包含 UHD 或 4K 时，创建 4K 子分类'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": current_config.get("enabled", False),
            "rules": current_config.get("rules", "")
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(ChainEventType.TransferRename)
    def category_handler(self, event: Event):
        """
        根据文件名关键字在原分类下创建子分类
        """
        logger.debug(f"文件名分类插件触发！")

        # 基础验证
        if not self.get_state():
            logger.debug(f"文件名分类插件未启用！")
            return
        if not event:
            logger.warning(f"文件名分类异常：事件对象为空")
            return
        if not hasattr(event, 'event_data'):
            logger.warning(f"文件名分类异常：事件数据为空")
            return

        try:
            data = event.event_data

            # 验证必要的数据字段
            if not hasattr(data, 'rename_dict') or not data.rename_dict:
                logger.warning(f"文件名分类异常：rename_dict为空")
                return

            if not hasattr(data, 'render_str') or not data.render_str:
                logger.warning(f"文件名分类异常：render_str为空")
                return

            rename_dict = data.rename_dict
            media_info = rename_dict.get("__mediainfo__")
            render_str = data.render_str
            
            if not media_info:
                logger.warning(f"文件名分类异常：__mediainfo__为空")
                return

            # 获取原始文件名
            original_name = ""
            
            # 方法1: 从rename_dict获取
            original_name = rename_dict.get("original_name", "")
            
            # 方法2: 从__meta__获取
            if not original_name:
                meta = rename_dict.get("__meta__")
                if meta:
                    if hasattr(meta, 'org_string') and meta.org_string:
                        original_name = meta.org_string
                    elif hasattr(meta, 'title') and meta.title:
                        original_name = meta.title
                    elif hasattr(meta, 'name') and meta.name:
                        original_name = meta.name
            
            # 方法3: 从path获取
            if not original_name and hasattr(data, 'path') and data.path:
                from pathlib import Path
                path_obj = Path(str(data.path))
                if path_obj.name:
                    original_name = path_obj.name
            
            if not original_name:
                logger.debug(f"文件名分类：无法获取原始文件名，跳过处理")
                return

            # 获取目标路径（用于路径匹配）
            target_path = ""
            if hasattr(data, 'path') and data.path:
                target_path = str(data.path)

            # 检查是否有规则
            if not self._rules:
                logger.debug(f"文件名分类：没有配置规则，跳过处理")
                return

            # 获取当前分类
            current_category = media_info.category or ""
            new_category = None

            logger.debug(f"文件名分类：原分类 '{current_category}'，开始匹配 {len(self._rules)} 条规则...")

            # 遍历规则进行匹配（按顺序，第一个匹配的生效）
            for rule in self._rules:
                rule_path = rule.get("path", "")
                pattern = rule.get("pattern", "")
                category = rule.get("category", "")

                # 检查路径过滤（包含匹配）
                if rule_path and rule_path not in target_path:
                    logger.debug(f"文件名分类：规则 '{pattern}' 跳过（目标路径不包含 '{rule_path}'）")
                    continue

                # 匹配文件名（空pattern或.*表示匹配所有）
                matched = False
                if not pattern or pattern == ".*":
                    # 空pattern或.*表示匹配所有文件
                    matched = True
                else:
                    # 使用正则表达式匹配（不区分大小写）
                    try:
                        if re.search(pattern, original_name, re.IGNORECASE):
                            matched = True
                    except re.error as e:
                        logger.error(f"文件名分类：正则表达式错误 '{pattern}': {str(e)}")
                        continue
                
                if matched:
                    new_category = category
                    break

            # 如果找到了新的分类，修改渲染路径
            if new_category:
                # 处理模板变量 {年代}
                if "{年代}" in new_category:
                    year = rename_dict.get("year")
                    decade = self._get_decade(year)
                    new_category = new_category.replace("{年代}", decade)
                
                # 处理模板变量 {首字母}
                if "{首字母}" in new_category:
                    # 优先使用中文标题，如果没有则使用英文标题
                    name = rename_dict.get("title") or rename_dict.get("en_title", "")
                    first_letter = self._get_first_letter(name)
                    new_category = new_category.replace("{首字母}", first_letter)
                
                # 计算最终分类（在原分类后追加新分类）
                if current_category:
                    final_category = f"{current_category}/{new_category}"
                else:
                    final_category = new_category
                
                # 更新MediaInfo中的分类
                media_info.set_category(final_category)
                
                # 在render_str开头添加子分类（原分类已在path中）
                updated_render_str = f"{new_category}/{render_str}"
                
                # 更新事件数据
                event.event_data.updated_str = updated_render_str
                event.event_data.updated = True
                event.event_data.source = "FileNameCategory"
                
                logger.info(f"文件名分类：匹配成功！'{original_name}' -> 规则 '{pattern}' -> 最终分类 '{final_category}'")
            else:
                logger.debug(f"文件名分类：文件名 '{original_name}' 未匹配任何规则")

        except Exception as e:
            logger.error(f"文件名分类异常: {str(e)}", exc_info=True)
            if hasattr(event, 'event_data') and event.event_data:
                event.event_data.updated = False

    def stop_service(self):
        """
        停止服务
        """
        pass
