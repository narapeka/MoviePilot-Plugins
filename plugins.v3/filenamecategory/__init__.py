from typing import Any, List, Dict, Tuple
import re

from app.sdk.events import eventmanager, Event
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase
from app.schemas.types import ChainEventType


class FileNameCategory(_PluginBase):
    """根据原始文件名为整理路径追加多级子分类"""

    # 插件名称
    plugin_name = "文件名多级分类"
    # 插件描述
    plugin_desc = "根据原始文件名中的关键字（支持正则表达式）在原分类下创建子分类。"
    # 插件图标
    plugin_icon = "Bookstack_A.png"
    # 插件版本
    plugin_version = "3.0.0"
    # 插件作者
    plugin_author = "narapeka"
    # 作者主页
    author_url = "https://github.com/narapeka/MoviePilot-Plugins"
    # 插件配置项ID前缀
    plugin_config_prefix = "filenamecategory_"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1

    _enabled = False
    _rules = []

    def init_plugin(self, config: dict = None) -> None:
        """加载插件开关和分类规则"""
        config = config or {}
        self._enabled = config.get("enabled", False)
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
            if not line:
                # 跳过空行
                continue

            parts = line.split('#')

            if len(parts) >= 3:
                # path#keyword#category (keyword可为空表示匹配所有)
                # 如果以#开头，parts[0]会是空字符串，表示路径为空
                path = parts[0].strip()
                pattern = parts[1].strip()
                category = parts[2].strip()

                if category:  # category必须存在
                    rules.append({
                        "path": path,
                        "pattern": pattern,
                        "category": category
                    })
                else:
                    logger.warning(f"文件名分类：跳过无效规则（category为空）: {line}")
            elif len(parts) == 2:
                # keyword#category (无path限制，path为空)
                pattern = parts[0].strip()
                category = parts[1].strip()

                if category:  # category必须存在
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
        """返回插件启用状态"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """不注册远程命令"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """不注册额外接口"""
        return []

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
                                                    '• 路径: 目标路径过滤，限定此条规则仅对目标路径包含该文本的文件生效，留空表示匹配所有路径\n'
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
                                            'placeholder': '#HDHome#HDHome\n#CHD|CHDBits#CHDBits/ISO\n/downloads##/{年代}',
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
                                                    '• /downloads##/{年代}\n'
                                                    '   目标路径包含 /downloads 的所有文件，按年代分类: /1990s/，/2000s/，/2010s/，/2020s/\n'
                                                    '• /我的接收#UHD|4K#4K/{首字母}\n'
                                                    '   目标路径包含 /我的接收 且文件名包含 UHD 或 4K 时，创建 4K 子分类，并按照首字母分类: 4K/A/, 4K/B/, 4K/C/, ...'
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
        """不提供独立详情页"""
        return []

    @eventmanager.register(ChainEventType.TransferRename)
    def category_handler(self, event: Event) -> None:
        """按首个匹配规则通过事件输出追加子分类"""
        if not self._enabled or not self._rules:
            return
        data = event.event_data
        rename_dict = data.rename_dict
        original_name = self._original_name(data)
        if not original_name:
            return
        target_path = str(data.path or "")
        for rule in self._rules:
            if rule["path"] and rule["path"] not in target_path:
                continue
            try:
                matched = not rule["pattern"] or re.search(
                    rule["pattern"], original_name, re.IGNORECASE
                )
            except re.error as error:
                logger.error(f"文件名分类：正则表达式错误 {rule['pattern']}: {error}")
                continue
            if not matched:
                continue
            category = rule["category"]
            if "{年代}" in category:
                category = category.replace("{年代}", self._get_decade(rename_dict.get("year")))
            if "{首字母}" in category:
                name = rename_dict.get("title") or rename_dict.get("en_title", "")
                category = category.replace("{首字母}", self._get_first_letter(name))
            category = category.replace("\\", "/").strip("/")
            render_str = data.updated_str if data.updated and data.updated_str else data.render_str
            data.updated_str = f"{category}/{render_str}" if category else render_str
            data.updated = True
            data.source = "FileNameCategory"
            logger.info(f"文件名分类：{original_name} -> {category}")
            return

    @staticmethod
    def _original_name(data: Any) -> str:
        """优先使用源文件名，兼容预览场景中的渲染上下文"""
        if data.source_item and data.source_item.name:
            return data.source_item.name
        if data.source_path:
            return str(data.source_path).replace("\\", "/").rsplit("/", 1)[-1]
        name = data.rename_dict.get("original_name", "")
        if name:
            return name
        meta = data.rename_dict.get("__meta__")
        return getattr(meta, "org_string", "") or getattr(meta, "name", "") or ""

    def stop_service(self) -> None:
        """
        停止服务
        """
        pass
