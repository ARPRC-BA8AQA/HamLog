# -*- coding: utf-8 -*-
"""
FontManager - 字体和界面大小管理
支持全局字体、字号、表格行高、列宽自定义
"""
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from typing import Optional, Dict


class FontLoaderThread(QThread):
    """后台线程加载系统字体，避免阻塞GUI"""
    fonts_loaded = pyqtSignal(list)

    def run(self):
        try:
            from PyQt6.QtGui import QFontDatabase
            db = QFontDatabase()
            families = sorted(db.families())
            self.fonts_loaded.emit(families)
        except Exception as e:
            # 出错时返回默认列表
            self.fonts_loaded.emit(FontManager.FALLBACK_FONTS.copy())


class FontManager(QObject):
    """字体管理器"""

    DEFAULT_FONT = "Microsoft YaHei"
    DEFAULT_SIZE = 13
    DEFAULT_TABLE_SIZE = 10
    DEFAULT_ROW_HEIGHT = 28

    # 预设字号列表
    SIZE_PRESETS = [9, 10, 11, 12, 13, 14, 15, 16, 18, 20]

    # 默认字体列表（线程加载完成前使用）
    FALLBACK_FONTS = [
        "Microsoft YaHei", "SimHei", "SimSun", "PingFang SC",
        "Consolas", "Courier New", "Arial", "Segoe UI",
        "Times New Roman", "Helvetica", "Verdana", "Tahoma",
        "Georgia", "Calibri", "Cambria", "Comic Sans MS",
        "NSimSun", "FangSong", "KaiTi", "STHeiti", "STKaiti",
        "STSong", "Hiragino Sans GB", "Meiryo", "Malgun Gothic",
        "Ubuntu", "DejaVu Sans", "Liberation Sans", "Roboto",
        "Open Sans", "Lato", "Montserrat", "Noto Sans",
        "JetBrains Mono", "Cascadia Code",
    ]

    # 系统字体缓存（加载完成后填充）
    _system_fonts = None
    _loader = None

    def __init__(self):
        super().__init__()

    @classmethod
    def start_loading_fonts(cls):
        """启动后台线程加载系统字体"""
        if cls._system_fonts is None and cls._loader is None:
            cls._loader = FontLoaderThread()
            cls._loader.fonts_loaded.connect(cls._on_fonts_loaded)
            cls._loader.start()

    @classmethod
    def _on_fonts_loaded(cls, fonts: list):
        """字体加载完成的回调"""
        cls._system_fonts = fonts
        cls._loader = None

    @classmethod
    def get_font_presets(cls) -> list:
        """获取字体列表（优先使用系统字体，未加载完返回默认列表）"""
        if cls._system_fonts is not None:
            return cls._system_fonts
        return cls.FALLBACK_FONTS

    @classmethod
    def is_system_fonts_loaded(cls) -> bool:
        """检查系统字体是否已加载完成"""
        return cls._system_fonts is not None

    @classmethod
    def get_system_fonts(cls) -> list:
        """获取已加载的系统字体（阻塞等待）"""
        if cls._system_fonts is not None:
            return cls._system_fonts
        # 如果还没加载完，启动并等待
        if cls._loader is None:
            cls.start_loading_fonts()
        # 等待线程完成（最多3秒）
        if cls._loader is not None:
            cls._loader.wait(3000)
        return cls._system_fonts or cls.FALLBACK_FONTS

    @classmethod
    def apply_global_font(cls, app: QApplication, font_name: str, font_size: int):
        """应用全局字体"""
        font = QFont(font_name, font_size)
        app.setFont(font)

    @classmethod
    def get_table_font(cls, font_name: str, font_size: int) -> QFont:
        """获取表格字体"""
        return QFont(font_name, font_size)

    @classmethod
    def validate_row_height(cls, height: int) -> int:
        """验证并规范行高"""
        return max(20, min(60, height))

    @classmethod
    def validate_font_size(cls, size: int) -> int:
        """验证并规范字号"""
        return max(8, min(24, size))


def load_font_settings(settings_manager) -> Dict:
    """从设置加载字体配置"""
    return {
        'global_font': settings_manager.get('global_font', FontManager.DEFAULT_FONT),
        'global_size': int(settings_manager.get('global_font_size', str(FontManager.DEFAULT_SIZE))),
        'table_font': settings_manager.get('table_font', FontManager.DEFAULT_FONT),
        'table_size': int(settings_manager.get('table_font_size', str(FontManager.DEFAULT_TABLE_SIZE))),
        'row_height': int(settings_manager.get('table_row_height', str(FontManager.DEFAULT_ROW_HEIGHT))),
    }


def save_font_settings(settings_manager, config: Dict):
    """保存字体配置到设置"""
    settings_manager.set('global_font', config.get('global_font', FontManager.DEFAULT_FONT))
    settings_manager.set('global_font_size', str(config.get('global_size', FontManager.DEFAULT_SIZE)))
    settings_manager.set('table_font', config.get('table_font', FontManager.DEFAULT_FONT))
    settings_manager.set('table_font_size', str(config.get('table_size', FontManager.DEFAULT_TABLE_SIZE)))
    settings_manager.set('table_row_height', str(config.get('row_height', FontManager.DEFAULT_ROW_HEIGHT)))
