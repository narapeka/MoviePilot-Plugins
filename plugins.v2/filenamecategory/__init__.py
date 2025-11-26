from typing import Any, List, Dict, Tuple
import re

from app.core.context import MediaInfo
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import ChainEventType, MediaType, NotificationType


class FileNameCategory(_PluginBase):
    # 插件名称
    plugin_name = "文件名多级分类"
    # 插件描述
    plugin_desc = "根据原始文件名中的关键字（支持正则表达式）来自定义媒体分类。"
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
    _override_category = True
    _movie_rules = []
    _tv_rules = []

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled", False)
            self._override_category = config.get("override_category", True)
            # 解析电影规则
            self._movie_rules = self._parse_rules(config.get("movie_rules", ""))
            # 解析电视剧规则
            self._tv_rules = self._parse_rules(config.get("tv_rules", ""))

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
                # path#keyword#category
                path = parts[0].strip()
                pattern = parts[1].strip()
                category = parts[2].strip()
                
                if pattern and category:
                    rules.append({
                        "path": path,
                        "pattern": pattern,
                        "category": category
                    })
                else:
                    logger.warning(f"文件名分类：跳过无效规则（pattern或category为空）: {line}")
            elif len(parts) == 2:
                # keyword#category (无path限制)
                pattern = parts[0].strip()
                category = parts[1].strip()
                
                if pattern and category:
                    rules.append({
                        "path": "",
                        "pattern": pattern,
                        "category": category
                    })
                else:
                    logger.warning(f"文件名分类：跳过无效规则（pattern或category为空）: {line}")
            else:
                logger.warning(f"文件名分类：跳过格式错误的规则: {line}")
        
        return rules

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
                            },
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
                                            'model': 'override_category',
                                            'label': '覆盖二级分类',
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
                                            'text': '规则格式: 路径#关键字#分类 (每行一条规则，按顺序匹配，第一个匹配的规则生效)\n'
                                                    '- 路径: 源文件路径过滤，包含匹配，留空表示匹配所有路径\n'
                                                    '- 关键字: 支持正则表达式，不区分大小写，多个关键字用 | 分隔\n'
                                                    '- 分类: 目标分类名称，支持多级路径如 BHYS/UHD\n'
                                                    '- 覆盖二级分类: 开启时替换原分类，关闭时在原分类后追加'
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
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'movie_rules',
                                            'label': '电影分类规则',
                                            'placeholder': '/downloads/uhd#UHD|4K|2160p#UHD电影\n'
                                                           '/downloads/remux#REMUX|Blu-?Ray#REMUX电影\n'
                                                           '#1080p#高清电影',
                                            'rows': 8,
                                            'hint': '电影分类规则，每行一条',
                                            'persistent-hint': True
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'tv_rules',
                                            'label': '电视剧分类规则',
                                            'placeholder': '/downloads/uhd#UHD|4K|2160p#UHD剧集\n'
                                                           '/downloads/remux#REMUX|Blu-?Ray#REMUX剧集\n'
                                                           '#1080p#高清剧集',
                                            'rows': 8,
                                            'hint': '电视剧分类规则，每行一条',
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
                                            'text': '规则示例:\n'
                                                    '- /downloads/uhd#UHD|4K|2160p#UHD电影  (路径包含/downloads/uhd且文件名包含UHD、4K或2160p时，分类为UHD电影)\n'
                                                    '- #REMUX#REMUX电影  (任意路径，文件名包含REMUX时，分类为REMUX电影)\n'
                                                    '- /nas/movie#CAT|BHYS#字幕组/精选  (路径包含/nas/movie且文件名包含CAT或BHYS时，分类为字幕组/精选)'
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
            "override_category": current_config.get("override_category", True),
            "movie_rules": current_config.get("movie_rules", ""),
            "tv_rules": current_config.get("tv_rules", "")
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(ChainEventType.TransferRename)
    def category_handler(self, event: Event):
        """
        根据文件名关键字重新设置分类，并修改渲染路径以包含新的分类文件夹
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

            # 获取源文件路径（用于路径匹配）
            source_path = ""
            meta = rename_dict.get("__meta__")
            if meta and hasattr(meta, 'path') and meta.path:
                source_path = str(meta.path)
            elif hasattr(data, 'path') and data.path:
                source_path = str(data.path)

            # 获取媒体类型并选择对应的规则
            rules = []
            if media_info.type == MediaType.MOVIE:
                rules = self._movie_rules
                media_type = "电影"
            elif media_info.type == MediaType.TV:
                rules = self._tv_rules
                media_type = "电视剧"
            else:
                logger.debug(f"文件名分类：未知媒体类型，跳过处理")
                return

            # 检查是否有规则
            if not rules:
                logger.debug(f"文件名分类：没有配置{media_type}规则，跳过处理")
                return

            logger.debug(f"文件名分类：开始匹配文件名 '{original_name}'，源路径 '{source_path}'，媒体类型 '{media_type}'，共 {len(rules)} 条规则")

            # 获取当前分类
            current_category = media_info.category or ""
            new_category = None

            # 遍历规则进行匹配（按顺序，第一个匹配的生效）
            for rule in rules:
                rule_path = rule.get("path", "")
                pattern = rule.get("pattern", "")
                category = rule.get("category", "")

                # 检查路径过滤（包含匹配）
                if rule_path and rule_path not in source_path:
                    logger.debug(f"文件名分类：规则 '{pattern}' 路径不匹配（规则路径: {rule_path}, 源路径: {source_path}）")
                    continue

                # 使用正则表达式匹配（不区分大小写）
                try:
                    if re.search(pattern, original_name, re.IGNORECASE):
                        new_category = category
                        logger.info(f"文件名分类：文件名 '{original_name}' 匹配规则 '{pattern}'，分类从 '{current_category}' 设置为 '{category}'")
                        break
                except re.error as e:
                    logger.error(f"文件名分类：正则表达式错误 '{pattern}': {str(e)}")
                    continue

            # 如果找到了新的分类，修改渲染路径
            if new_category:
                # 计算最终分类
                if self._override_category:
                    # 覆盖模式：直接使用新分类
                    final_category = new_category
                else:
                    # 追加模式：在原分类后追加新分类
                    if current_category:
                        final_category = f"{current_category}/{new_category}"
                    else:
                        final_category = new_category
                
                # 更新MediaInfo中的分类
                media_info.set_category(final_category)
                
                updated_render_str = render_str
                
                # 如果当前分类不为空，尝试从render_str开头移除当前分类文件夹
                if current_category and render_str.startswith(f"{current_category}/"):
                    updated_render_str = render_str[len(f"{current_category}/"):]
                    logger.debug(f"文件名分类：从render_str中移除旧分类 '{current_category}'")
                
                # 在路径开头添加最终分类文件夹
                updated_render_str = f"{final_category}/{updated_render_str}"
                logger.debug(f"文件名分类：在render_str中添加分类 '{final_category}'")
                
                # 更新事件数据
                event.event_data.updated_str = updated_render_str
                event.event_data.updated = True
                event.event_data.source = "FileNameCategory"
                
                logger.info(f"文件名分类：已更新渲染路径为 '{updated_render_str}' (原路径: '{render_str}')")
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
