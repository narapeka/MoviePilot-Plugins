from typing import Any, List, Dict, Tuple
import re
import json

from app.core.context import MediaInfo
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import ChainEventType, MediaType, NotificationType


class FileNameCategory(_PluginBase):
    # 插件名称
    plugin_name = "文件名二级分类"
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
    _rules = []

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled", False)
            # 优先从 rules_json 解析，如果没有则使用 rules
            rules_json = config.get("rules_json", "")
            if rules_json:
                try:
                    self._rules = json.loads(rules_json) if isinstance(rules_json, str) else rules_json
                except json.JSONDecodeError as e:
                    logger.error(f"文件名分类插件：规则JSON解析失败: {str(e)}")
                    self._rules = []
            else:
                self._rules = config.get("rules", [])

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
        rules = current_config.get("rules", [])
        rules_json = current_config.get("rules_json", "")
        if not rules_json and rules:
            try:
                rules_json = json.dumps(rules, ensure_ascii=False, indent=2)
            except Exception:
                rules_json = "[]"
        
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
                                            'text': '根据原始文件名中的关键字（支持正则表达式）来自定义媒体分类。规则按优先级排序（数字越小优先级越高），第一个匹配的规则生效。'
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
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'rules_json',
                                            'label': '分类规则（JSON格式）',
                                            'placeholder': '[\n  {\n    "pattern": "4K|UHD|2160p",\n    "category": "4K电影",\n    "media_type": "电影",\n    "priority": 1\n  },\n  {\n    "pattern": "1080p|BluRay",\n    "category": "高清电影",\n    "media_type": "",\n    "priority": 2\n  }\n]',
                                            'rows': 10,
                                            'hint': '规则列表，每个规则包含：pattern（正则表达式）、category（分类名称）、media_type（媒体类型，可选）、priority（优先级，数字越小优先级越高）',
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
                                            'text': '规则示例：\n- pattern: "4K|UHD|2160p" (匹配包含4K、UHD或2160p的文件名)\n- category: "4K电影" (匹配后设置的分类名称)\n- media_type: "电影" 或 "电视剧" 或 "" (空字符串表示匹配所有类型)\n- priority: 1 (数字越小优先级越高)'
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
            "rules": rules,
            "rules_json": rules_json if rules_json else "[]"
        }

    def update_config(self, config: dict):
        """
        更新配置时，将 rules 转换为 rules_json
        """
        if "rules" in config and "rules_json" not in config:
            try:
                config["rules_json"] = json.dumps(config["rules"], ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"文件名分类插件：规则JSON转换失败: {str(e)}")
        elif "rules_json" in config and isinstance(config["rules_json"], str):
            # 如果提供了 rules_json，同步更新 rules
            try:
                config["rules"] = json.loads(config["rules_json"])
            except json.JSONDecodeError as e:
                logger.error(f"文件名分类插件：规则JSON解析失败: {str(e)}")
                config["rules"] = []
        super().update_config(config)

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
            # 尝试多种方式获取原始文件名
            original_name = ""
            
            # 方法1: 从rename_dict获取
            original_name = rename_dict.get("original_name", "")
            
            # 方法2: 从__meta__获取
            if not original_name:
                meta = rename_dict.get("__meta__")
                if meta:
                    # 尝试获取原始字符串
                    if hasattr(meta, 'org_string') and meta.org_string:
                        original_name = meta.org_string
                    # 尝试获取title
                    elif hasattr(meta, 'title') and meta.title:
                        original_name = meta.title
                    # 尝试获取name
                    elif hasattr(meta, 'name') and meta.name:
                        original_name = meta.name
            
            # 方法3: 从path获取（如果path包含原始文件名）
            if not original_name and hasattr(data, 'path') and data.path:
                from pathlib import Path
                path_obj = Path(str(data.path))
                if path_obj.name:
                    original_name = path_obj.name
            
            if not original_name:
                logger.debug(f"文件名分类：无法获取原始文件名，跳过处理")
                return

            # 获取媒体类型（转换为中文）
            media_type = rename_dict.get("type", "")
            if not media_type:
                if media_info.type == MediaType.MOVIE:
                    media_type = "电影"
                elif media_info.type == MediaType.TV:
                    media_type = "电视剧"
                else:
                    media_type = ""

            # 检查是否有规则
            if not self._rules:
                logger.debug(f"文件名分类：没有配置规则，跳过处理")
                return

            # 按优先级排序规则
            sorted_rules = sorted(self._rules, key=lambda x: x.get("priority", 999))

            logger.debug(f"文件名分类：开始匹配文件名 '{original_name}'，媒体类型 '{media_type}'，共 {len(sorted_rules)} 条规则")

            # 获取当前分类（用于比较）
            current_category = media_info.category or ""
            new_category = None

            # 遍历规则进行匹配
            for rule in sorted_rules:
                pattern = rule.get("pattern", "")
                category = rule.get("category", "")
                rule_media_type = rule.get("media_type", "")

                if not pattern or not category:
                    logger.debug(f"文件名分类：跳过无效规则（pattern或category为空）")
                    continue

                # 检查媒体类型过滤
                if rule_media_type and rule_media_type != media_type:
                    logger.debug(f"文件名分类：规则 '{pattern}' 媒体类型不匹配（规则: {rule_media_type}, 实际: {media_type}）")
                    continue

                # 使用正则表达式匹配（不区分大小写）
                try:
                    if re.search(pattern, original_name, re.IGNORECASE):
                        new_category = category
                        logger.info(f"文件名分类：文件名 '{original_name}' 匹配规则 '{pattern}'，分类从 '{current_category}' 设置为 '{category}'")
                        # 更新MediaInfo中的分类
                        media_info.set_category(category)
                        break
                except re.error as e:
                    logger.error(f"文件名分类：正则表达式错误 '{pattern}': {str(e)}")
                    continue

            # 如果找到了新的分类，修改渲染路径
            if new_category and new_category != current_category:
                # 按照MultiClass插件的模式，直接在render_str开头添加新分类文件夹
                # 注意：path参数可能已经包含了旧分类（来自get_dest_dir），
                # 但通过修改render_str，我们可以让新分类出现在正确的位置
                # 最终路径结构会是: base_path / media_type / old_category / new_category / media_title
                # 虽然会有两个分类，但新分类会在正确的位置，MoviePilot会处理路径合并
                
                updated_render_str = render_str
                
                # 如果当前分类不为空，尝试从render_str开头移除当前分类文件夹
                # (以防render_str已经包含了当前分类)
                if current_category and render_str.startswith(f"{current_category}/"):
                    updated_render_str = render_str[len(f"{current_category}/"):]
                    logger.debug(f"文件名分类：从render_str中移除旧分类 '{current_category}'")
                
                # 在路径开头添加新分类文件夹
                if new_category:
                    updated_render_str = f"{new_category}/{updated_render_str}"
                    logger.debug(f"文件名分类：在render_str中添加新分类 '{new_category}'")
                
                # 更新事件数据（按照MultiClass的模式）
                event.event_data.updated_str = updated_render_str
                event.event_data.updated = True
                event.event_data.source = "FileNameCategory"
                
                logger.info(f"文件名分类：已更新渲染路径为 '{updated_render_str}' (原路径: '{render_str}')")
            else:
                if not new_category:
                    logger.debug(f"文件名分类：文件名 '{original_name}' 未匹配任何规则")
                else:
                    logger.debug(f"文件名分类：分类未变化，保持原路径")

        except Exception as e:
            logger.error(f"文件名分类异常: {str(e)}", exc_info=True)
            # 确保即使出错也不会影响原始数据
            if hasattr(event, 'event_data') and event.event_data:
                event.event_data.updated = False

    def stop_service(self):
        """
        停止服务
        """
        pass

