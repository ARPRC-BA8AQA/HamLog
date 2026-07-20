# -*- coding: utf-8 -*-
"""
ProxyManager - 系统代理配置管理
支持 HTTP/HTTPS/SOCKS5 代理，自动应用到 urllib 请求
"""
import os
import re
import socket
import urllib.request
from typing import Optional, Dict
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal


class ProxyManager(QObject):
    """代理管理器单例"""

    proxy_changed = pyqtSignal(dict)  # 代理配置变更信号

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if ProxyManager._initialized:
            return
        super().__init__()
        ProxyManager._initialized = True

        self._config = {
            'enabled': False,
            'http': '',
            'https': '',
            'socks5': '',
            'no_proxy': 'localhost,127.0.0.1,::1,gitee.com,ghproxy.com,ghproxy.net,mirror.ghproxy.com',
            'use_system': False,
        }
        self._original_opener = None
        self._apply_to_env()

    def load_from_settings(self, settings_manager):
        """从 SettingsManager 加载配置"""
        self._config['enabled'] = settings_manager.get('proxy_enabled', '0') == '1'
        self._config['http'] = settings_manager.get('proxy_http', '')
        self._config['https'] = settings_manager.get('proxy_https', '')
        self._config['socks5'] = settings_manager.get('proxy_socks5', '')
        self._config['no_proxy'] = settings_manager.get('proxy_no_proxy', 'localhost,127.0.0.1,::1,gitee.com,ghproxy.com,ghproxy.net,mirror.ghproxy.com')
        self._config['use_system'] = settings_manager.get('proxy_use_system', '0') == '1'
        self._apply_to_env()

    def save_to_settings(self, settings_manager):
        """保存配置到 SettingsManager"""
        settings_manager.set('proxy_enabled', '1' if self._config['enabled'] else '0')
        settings_manager.set('proxy_http', self._config['http'])
        settings_manager.set('proxy_https', self._config['https'])
        settings_manager.set('proxy_socks5', self._config['socks5'])
        settings_manager.set('proxy_no_proxy', self._config['no_proxy'])
        settings_manager.set('proxy_use_system', '1' if self._config['use_system'] else '0')

    def _apply_to_env(self):
        """应用代理到环境变量和 urllib"""
        if not self._config['enabled']:
            # 清除代理环境变量
            for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
                        'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy']:
                if key in os.environ:
                    del os.environ[key]
            # 恢复默认 opener
            if self._original_opener:
                urllib.request.install_opener(self._original_opener)
            return

        # 使用系统代理
        if self._config['use_system']:
            self._apply_system_proxy()
            return

        # 手动代理
        proxies = {}
        no_proxy = self._config['no_proxy']

        if self._config['http']:
            proxies['http'] = self._config['http']
            os.environ['HTTP_PROXY'] = self._config['http']
            os.environ['http_proxy'] = self._config['http']

        if self._config['https']:
            proxies['https'] = self._config['https']
            os.environ['HTTPS_PROXY'] = self._config['https']
            os.environ['https_proxy'] = self._config['https']

        if self._config['socks5']:
            # SOCKS5 需要 PySocks
            try:
                import socks
                import socket as sock_module
                sock_module.setdefaultproxy = socks.setdefaultproxy
                sock_module.socksocket = socks.socksocket
            except ImportError:
                pass
            proxies['all'] = self._config['socks5']
            os.environ['ALL_PROXY'] = self._config['socks5']
            os.environ['all_proxy'] = self._config['socks5']

        if no_proxy:
            os.environ['NO_PROXY'] = no_proxy
            os.environ['no_proxy'] = no_proxy

        # 应用到 urllib
        proxy_handler = urllib.request.ProxyHandler(proxies)
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)

    def _apply_system_proxy(self):
        """读取系统代理设置"""
        # Windows 注册表读取
        if os.name == 'nt':
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
                proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
                if proxy_enable:
                    proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
                    bypass, _ = winreg.QueryValueEx(key, "ProxyOverride")

                    # 解析代理服务器格式 host:port 或 http=host:port;https=host:port
                    if ';' in proxy_server:
                        for part in proxy_server.split(';'):
                            if '=' in part:
                                proto, addr = part.split('=', 1)
                                if proto == 'http':
                                    os.environ['HTTP_PROXY'] = f"http://{addr}"
                                elif proto == 'https':
                                    os.environ['HTTPS_PROXY'] = f"http://{addr}"
                    else:
                        os.environ['HTTP_PROXY'] = f"http://{proxy_server}"
                        os.environ['HTTPS_PROXY'] = f"http://{proxy_server}"

                    if bypass:
                        os.environ['NO_PROXY'] = bypass.replace(';', ',')

                    proxy_handler = urllib.request.ProxyHandler()
                    opener = urllib.request.build_opener(proxy_handler)
                    urllib.request.install_opener(opener)
            except Exception:
                pass

        # macOS / Linux 读取环境变量
        else:
            for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
                if var in os.environ:
                    proxy_handler = urllib.request.ProxyHandler()
                    opener = urllib.request.build_opener(proxy_handler)
                    urllib.request.install_opener(opener)
                    break

    def set_config(self, config: Dict):
        """设置代理配置"""
        self._config.update(config)
        self._apply_to_env()
        self.proxy_changed.emit(self._config.copy())

    def get_config(self) -> Dict:
        """获取当前配置"""
        return self._config.copy()

    def is_enabled(self) -> bool:
        return self._config['enabled']

    def test_proxy(self, url: str = "https://www.google.com", timeout: int = 10) -> tuple:
        """测试代理连通性，返回 (success, message)"""
        try:
            req = urllib.request.Request(url, method='HEAD',
                                         headers={'User-Agent': 'HamLog/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return True, f"HTTP {resp.status}"
        except Exception as e:
            return False, str(e)


def get_proxy_manager() -> ProxyManager:
    """获取代理管理器单例"""
    return ProxyManager()
