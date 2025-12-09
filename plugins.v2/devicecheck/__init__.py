"""
设备状态检测插件
检测设备在线状态并发送事件通知给其他插件
"""
import threading
import subprocess
import socket
from time import sleep, time
from typing import Any, Dict, List, Tuple, Optional

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType


class DeviceCheck(_PluginBase):
    # 插件名称
    plugin_name = "设备状态检测"
    # 插件描述
    plugin_desc = "检测设备在线状态，当设备上线或下线时发送事件通知给其他插件"
    # 插件图标
    plugin_icon = "Syncthing.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "narapeka"
    # 作者主页
    author_url = "https://github.com/narapeka/MoviePilot-Plugins"
    # 插件配置项ID前缀
    plugin_config_prefix = "DeviceCheck_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _devices = []  # 设备列表: [{"name": "设备名", "ip": "IP地址", "port": 端口（可选）}]
    _check_interval = 60  # 检测间隔（秒）
    _timeout = 3  # 超时时间（秒）
    
    # 监控线程
    _monitor_thread: Optional[threading.Thread] = None
    # 停止事件
    _stop_event = threading.Event()
    # 设备状态缓存
    _device_status = {}  # {device_key: {"status": "online/offline", "last_check": timestamp}}

    def init_plugin(self, config: dict = None):
        """
        初始化插件
        """
        self._stop_event.clear()
        
        if config:
            self._enabled = config.get("enabled", False)
            self._devices = config.get("devices", [])
            self._check_interval = config.get("check_interval", 60)
            self._timeout = config.get("timeout", 3)
            
            # 验证设备配置
            self._devices = [d for d in self._devices if d.get("name") and d.get("ip")]
            
            if self._enabled and self._devices:
                # 启动监控线程
                if self._monitor_thread and self._monitor_thread.is_alive():
                    logger.warning("设备监控线程已在运行")
                else:
                    self._monitor_thread = threading.Thread(
                        target=self._monitor_devices,
                        daemon=True
                    )
                    self._monitor_thread.start()
                    logger.info(f"设备状态检测插件已启动，监控 {len(self._devices)} 个设备")
            else:
                logger.info("设备状态检测插件未启用或未配置设备")

    def get_state(self) -> bool:
        """
        获取插件运行状态
        """
        return self._enabled and len(self._devices) > 0

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        注册插件远程命令
        """
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """
        注册插件API
        """
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面
        """
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
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'check_interval',
                                            'label': '检测间隔（秒）',
                                            'type': 'number',
                                            'placeholder': '30'
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'timeout',
                                            'label': '超时时间（秒）',
                                            'type': 'number',
                                            'placeholder': '3'
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
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'text',
                                            'density': 'compact',
                                            'text': '💡 常用端口提示：SMB (445) | NFS (2049) | CD2 (19798) | 留空则使用Ping检测'
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
                                        'component': 'VDataTable',
                                        'props': {
                                            'model': 'devices',
                                            'headers': [
                                                {'title': '设备名称', 'key': 'name', 'editable': True},
                                                {'title': 'IP地址', 'key': 'ip', 'editable': True},
                                                {'title': '端口', 'key': 'port', 'editable': True}
                                            ],
                                            'items': 'devices',
                                            'hide-default-footer': True,
                                            'editable': True
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
                                        'component': 'VBtn',
                                        'props': {
                                            'color': 'primary',
                                            'text': '添加设备'
                                        },
                                        'events': {
                                            'click': 'addDevice'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'props': {
                            'style': {
                                'margin-top': '12px'
                            },
                        },
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'title': '如何接收设备状态事件'
                                        },
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {
                                                    'style': {
                                                        'margin-top': '8px',
                                                        'line-height': '1.8',
                                                        'font-size': '13px'
                                                    }
                                                },
                                                'content': [
                                                    {
                                                        'component': 'p',
                                                        'props': {
                                                            'style': {
                                                                'margin': '0 0 8px 0',
                                                                'font-weight': '500'
                                                            }
                                                        },
                                                        'text': '其他插件可以通过监听 PluginTriggered 事件来接收设备状态变化通知：'
                                                    },
                                                    {
                                                        'component': 'pre',
                                                        'props': {
                                                            'style': {
                                                                'background': 'rgba(0,0,0,0.05)',
                                                                'padding': '12px',
                                                                'border-radius': '4px',
                                                                'font-size': '11px',
                                                                'margin': '8px 0',
                                                                'overflow-x': 'auto',
                                                                'white-space': 'pre-wrap',
                                                                'word-wrap': 'break-word'
                                                            }
                                                        },
                                                        'text': '@eventmanager.register(EventType.PluginTriggered)\ndef handle_device_event(self, event: Event):\n    event_data = event.event_data\n    if event_data.get("plugin_id") == "DeviceCheck":\n        event_name = event_data.get("event_name")\n        device_ip = event_data.get("device_ip")\n        device_name = event_data.get("device_name")\n        \n        if event_name == "device_online":\n            # 设备上线处理\n            logger.info(f"设备 {device_name} ({device_ip}) 已上线")\n        elif event_name == "device_offline":\n            # 设备下线处理\n            logger.info(f"设备 {device_name} ({device_ip}) 已下线")'
                                                    },
                                                    {
                                                        'component': 'p',
                                                        'props': {
                                                            'style': {
                                                                'margin': '8px 0 0 0',
                                                                'font-size': '12px',
                                                                'color': 'rgba(0,0,0,0.7)'
                                                            }
                                                        },
                                                        'text': '事件数据字段：device_name（设备名称）、device_ip（IP地址）、device_port（端口，可选）、status（online/offline）、timestamp（时间戳）。检测方式：有端口时使用端口检测，无端口时使用ping检测。'
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "devices": [],
            "check_interval": 60,
            "timeout": 3
        }

    def get_page(self) -> List[dict]:
        """
        获取插件数据页面
        """
        # 显示设备状态
        status_data = []
        for device in self._devices:
            device_key = f"{device.get('ip')}:{device.get('port', '')}"
            status_info = self._device_status.get(device_key, {})
            device_port = device.get("port")
            check_method = "端口检测" if device_port else "Ping检测"
            status_data.append({
                "name": device.get("name"),
                "ip": device.get("ip"),
                "port": device_port if device_port else "-",
                "check_method": check_method,
                "status": status_info.get("status", "unknown"),
                "last_check": status_info.get("last_check", 0)
            })
        
        return status_data

    def _monitor_devices(self):
        """
        监控设备状态的线程函数
        """
        logger.info("设备状态监控线程已启动")
        
        while not self._stop_event.is_set():
            try:
                for device in self._devices:
                    if self._stop_event.is_set():
                        break
                    
                    device_name = device.get("name", "Unknown")
                    device_ip = device.get("ip")
                    device_port = device.get("port")
                    
                    if not device_ip:
                        continue
                    
                    device_key = f"{device_ip}:{device_port or ''}"
                    
                    # 检测设备状态：有端口时使用端口检测，无端口时使用ping检测
                    is_online = False
                    if device_port:
                        try:
                            is_online = self._check_port(device_ip, int(device_port))
                        except (ValueError, TypeError):
                            # 端口格式错误，回退到ping检测
                            is_online = self._check_ping(device_ip)
                    else:
                        is_online = self._check_ping(device_ip)
                    
                    # 获取上次状态
                    last_status = self._device_status.get(device_key, {}).get("status")
                    current_status = "online" if is_online else "offline"
                    
                    # 更新状态缓存
                    self._device_status[device_key] = {
                        "status": current_status,
                        "last_check": time()
                    }
                    
                    # 如果状态发生变化，发送事件
                    if last_status and last_status != current_status:
                        logger.info(f"设备 {device_name} ({device_ip}) 状态变化: {last_status} -> {current_status}")
                        self._send_device_event(
                            device_name=device_name,
                            device_ip=device_ip,
                            device_port=device_port,
                            status=current_status
                        )
                    elif not last_status:
                        # 首次检测，也发送事件
                        logger.info(f"设备 {device_name} ({device_ip}) 初始状态: {current_status}")
                        self._send_device_event(
                            device_name=device_name,
                            device_ip=device_ip,
                            device_port=device_port,
                            status=current_status
                        )
                    
                    # 短暂延迟，避免同时检测所有设备
                    sleep(1)
                
                # 等待检测间隔
                self._stop_event.wait(self._check_interval)
                
            except Exception as e:
                logger.error(f"设备状态检测出错: {str(e)}")
                sleep(5)  # 出错后等待5秒再继续
        
        logger.info("设备状态监控线程已停止")

    def _check_ping(self, ip: str) -> bool:
        """
        使用ping检测设备是否在线
        """
        try:
            # Windows使用 -n，Linux/Mac使用 -c
            param = '-n' if self._is_windows() else '-c'
            command = ['ping', param, '1', '-w', str(int(self._timeout * 1000)), ip]
            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self._timeout + 1
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Ping检测 {ip} 失败: {str(e)}")
            return False

    def _check_port(self, ip: str, port: int) -> bool:
        """
        使用端口检测设备是否在线
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"端口检测 {ip}:{port} 失败: {str(e)}")
            return False

    def _is_windows(self) -> bool:
        """
        判断是否为Windows系统
        """
        import platform
        return platform.system().lower() == 'windows'

    def _send_device_event(self, device_name: str, device_ip: str, 
                          device_port: Optional[int], status: str):
        """
        发送设备状态事件
        """
        try:
            event_data = {
                "plugin_id": self.__class__.__name__,
                "event_name": f"device_{status}",  # device_online 或 device_offline
                "device_name": device_name,
                "device_ip": device_ip,
                "device_port": device_port,
                "status": status,
                "timestamp": time()
            }
            
            # 发送PluginTriggered事件，其他插件可以监听此事件
            self.eventmanager.send_event(
                EventType.PluginTriggered,
                event_data
            )
            
            logger.debug(f"已发送设备状态事件: {device_name} ({device_ip}) -> {status}")
            
        except Exception as e:
            logger.error(f"发送设备状态事件失败: {str(e)}")

    def stop_service(self):
        """
        停止插件服务
        """
        logger.info("正在停止设备状态检测插件...")
        self._stop_event.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        
        logger.info("设备状态检测插件已停止")

