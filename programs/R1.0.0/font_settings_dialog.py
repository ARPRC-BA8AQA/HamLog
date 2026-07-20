# -*- coding: utf-8 -*-
"""
FontSettingsDialog - 字体和界面大小设置对话框
支持搜索框选择字体，后台异步加载系统字体
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QCompleter
)
from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QFont

from font_manager import FontManager, load_font_settings, save_font_settings


class FontSettingsDialog(QDialog):
    """字体设置对话框"""

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self.setWindowTitle("字体与界面设置")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        self._all_fonts = FontManager.FALLBACK_FONTS.copy()
        self.setup_ui()
        self.load_settings()

        # 启动后台加载系统字体
        self._load_system_fonts()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 全局字体 ===
        global_group = QGroupBox("全局字体")
        global_layout = QFormLayout(global_group)
        global_layout.setSpacing(10)

        # 字体搜索框（带自动补全）
        self.txt_global_font = QLineEdit()
        self.txt_global_font.setPlaceholderText("输入字体名称，如 HarmonyOS Sans...")
        global_layout.addRow("字体:", self.txt_global_font)

        self.spin_global_size = QSpinBox()
        self.spin_global_size.setRange(8, 24)
        self.spin_global_size.setSuffix(" pt")
        global_layout.addRow("字号:", self.spin_global_size)

        layout.addWidget(global_group)



        # === 预览 ===
        preview_group = QGroupBox("预览")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(5)
        self.preview_table.setHorizontalHeaderLabels(["呼号", "频率", "日期", "模式", "QTH"])
        self.preview_table.setRowCount(3)

        sample_data = [
            ["BA8AQA", "144.000MHz", "2026-07-14", "FM", "Chengdu"],
            ["BA8AQA", "7.050MHz", "2026-07-13", "CW", "Beijing"],
            ["BA8AQA", "21.300MHz", "2026-07-12", "SSB", "Shanghai"],
        ]
        for row, data in enumerate(sample_data):
            for col, val in enumerate(data):
                self.preview_table.setItem(row, col, QTableWidgetItem(val))

        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(False)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group, stretch=1)

        # 连接信号更新预览
        self.txt_global_font.textChanged.connect(self.update_preview)
        self.spin_global_size.valueChanged.connect(self.update_preview)


        # === 按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("success")
        self.btn_save.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _load_system_fonts(self):
        """后台加载系统字体，完成后更新补全列表"""
        # 先用默认列表初始化补全
        self._setup_completer(self._all_fonts)

        # 如果系统字体已缓存，直接使用
        if FontManager.is_system_fonts_loaded():
            self._all_fonts = FontManager.get_font_presets()
            self._setup_completer(self._all_fonts)
            return

        # 启动后台线程加载
        from font_manager import FontLoaderThread
        self._loader = FontLoaderThread()
        self._loader.fonts_loaded.connect(self._on_fonts_loaded)
        self._loader.start()

    def _on_fonts_loaded(self, fonts: list):
        """系统字体加载完成，更新补全列表"""
        self._all_fonts = fonts
        self._setup_completer(fonts)
        self._loader = None

    def _setup_completer(self, fonts: list):
        """设置搜索框的自动补全"""
        # 全局字体补全
        comp1 = QCompleter(fonts, self)
        comp1.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp1.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_global_font.setCompleter(comp1)



    def load_settings(self):
        config = load_font_settings(self.settings)

        self.txt_global_font.setText(config['global_font'])
        self.spin_global_size.setValue(config['global_size'])


        self.update_preview()

    def update_preview(self):
        font_name = self.txt_global_font.text().strip() or FontManager.DEFAULT_FONT
        font_size = self.spin_global_size.value()

        self.setFont(QFont(font_name, font_size))
        self.preview_table.setFont(QFont(font_name, font_size))

    def save_settings(self):
        config = {
            'global_font': self.txt_global_font.text().strip() or FontManager.DEFAULT_FONT,
            'global_size': self.spin_global_size.value(),
        }
        save_font_settings(self.settings, config)

        QMessageBox.information(self, "保存成功", 
                                "字体设置已保存，重启软件后完全生效。\n"
                                "部分设置可能立即生效。")
        self.accept()

    def closeEvent(self, event):
        if hasattr(self, '_loader') and self._loader is not None:
            self._loader.quit()
            self._loader.wait(1000)
        event.accept()
