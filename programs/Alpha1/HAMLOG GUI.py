# -*- coding: utf-8 -*-
"""
HAMLOG GUI - 业余无线电台日志管理系统前端界面
使用 PyQt6 构建
"""
import sys
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QDialog, QMessageBox, QComboBox, QSpinBox, QGroupBox, QGridLayout,
    QHeaderView, QFrame, QTextEdit, QMenu, QStatusBar, QFormLayout, QScrollArea)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QAction, QKeySequence, QDesktopServices

from AutoDeal import Database, SettingsManager, Validator

import platform
from pathlib import Path


class StyleSheet:
    """样式表"""
    DARK = """
    QMainWindow {
        background-color: #1e1e1e;
    }
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
        font-family: "Microsoft YaHei", "SimHei", sans-serif;
        font-size: 13px;
    }
    QGroupBox {
        border: 1px solid #3c3c3c;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: #4fc3f7;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit, QTimeEdit {
        background-color: #2d2d2d;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        padding: 6px 10px;
        color: #e0e0e0;
        selection-background-color: #4fc3f7;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
        border: 1px solid #4fc3f7;
    }
    QLineEdit:disabled {
        background-color: #252525;
        color: #666;
    }
    QPushButton {
        background-color: #0d7377;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        color: white;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #14919b;
    }
    QPushButton:pressed {
        background-color: #0a5c5f;
    }
    QPushButton:disabled {
        background-color: #333;
        color: #666;
    }
    QPushButton#danger {
        background-color: #c62828;
    }
    QPushButton#danger:hover {
        background-color: #e53935;
    }
    QPushButton#success {
        background-color: #2e7d32;
    }
    QPushButton#success:hover {
        background-color: #43a047;
    }
    QTableWidget {
        background-color: #252525;
        border: 1px solid #3c3c3c;
        gridline-color: #3c3c3c;
        selection-background-color: #0d7377;
        selection-color: white;
    }
    QTableWidget::item {
        padding: 6px;
        border-bottom: 1px solid #3c3c3c;
    }
    QTableWidget::item:selected {
        background-color: #0d7377;
    }
    QHeaderView::section {
        background-color: #2d2d2d;
        color: #4fc3f7;
        padding: 8px;
        border: none;
        border-right: 1px solid #3c3c3c;
        font-weight: bold;
    }
    QTabWidget::pane {
        border: 1px solid #3c3c3c;
        background-color: #1e1e1e;
    }
    QTabBar::tab {
        background-color: #2d2d2d;
        color: #aaa;
        padding: 10px 20px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background-color: #0d7377;
        color: white;
    }
    QTabBar::tab:hover:!selected {
        background-color: #3c3c3c;
        color: #e0e0e0;
    }
    QMenuBar {
        background-color: #2d2d2d;
        color: #e0e0e0;
    }
    QMenuBar::item:selected {
        background-color: #0d7377;
    }
    QMenu {
        background-color: #2d2d2d;
        border: 1px solid #3c3c3c;
    }
    QMenu::item:selected {
        background-color: #0d7377;
    }
    QStatusBar {
        background-color: #2d2d2d;
        color: #aaa;
    }
    QScrollArea {
        border: none;
    }
    QLabel#title {
        font-size: 24px;
        font-weight: bold;
        color: #4fc3f7;
    }
    QLabel#subtitle {
        font-size: 14px;
        color: #aaa;
    }
    QLabel#clock {
        font-size: 28px;
        font-weight: bold;
        color: #4fc3f7;
        font-family: "Consolas", "Courier New", monospace;
    }
    QLabel#date {
        font-size: 16px;
        color: #aaa;
    }
    QLabel#info_label {
        color: #81c784;
        font-weight: bold;
    }
    QLabel#error_label {
        color: #e57373;
        font-weight: bold;
    }
    QComboBox::drop-down {
        border: none;
        width: 30px;
    }
    QComboBox QAbstractItemView {
        background-color: #2d2d2d;
        color: #e0e0e0;
        selection-background-color: #0d7377;
    }
    """

    LIGHT = """
    QMainWindow {
        background-color: #f5f5f5;
    }
    QWidget {
        background-color: #f5f5f5;
        color: #333333;
        font-family: "Microsoft YaHei", "SimHei", sans-serif;
        font-size: 13px;
    }
    QGroupBox {
        border: 1px solid #cccccc;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: #1565c0;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit, QTimeEdit {
        background-color: #ffffff;
        border: 1px solid #cccccc;
        border-radius: 4px;
        padding: 6px 10px;
        color: #333333;
        selection-background-color: #1976d2;
        selection-color: white;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
        border: 1px solid #1976d2;
    }
    QLineEdit:disabled {
        background-color: #eeeeee;
        color: #999999;
    }
    QPushButton {
        background-color: #1976d2;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        color: white;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #1565c0;
    }
    QPushButton:pressed {
        background-color: #0d47a1;
    }
    QPushButton:disabled {
        background-color: #bdbdbd;
        color: #757575;
    }
    QPushButton#danger {
        background-color: #c62828;
    }
    QPushButton#danger:hover {
        background-color: #b71c1c;
    }
    QPushButton#success {
        background-color: #2e7d32;
    }
    QPushButton#success:hover {
        background-color: #1b5e20;
    }
    QTableWidget {
        background-color: #ffffff;
        border: 1px solid #cccccc;
        gridline-color: #e0e0e0;
        selection-background-color: #1976d2;
        selection-color: white;
    }
    QTableWidget::item {
        padding: 6px;
        border-bottom: 1px solid #e0e0e0;
    }
    QTableWidget::item:selected {
        background-color: #1976d2;
    }
    QHeaderView::section {
        background-color: #e3f2fd;
        color: #1565c0;
        padding: 8px;
        border: none;
        border-right: 1px solid #cccccc;
        font-weight: bold;
    }
    QTabWidget::pane {
        border: 1px solid #cccccc;
        background-color: #f5f5f5;
    }
    QTabBar::tab {
        background-color: #e0e0e0;
        color: #666666;
        padding: 10px 20px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background-color: #1976d2;
        color: white;
    }
    QTabBar::tab:hover:!selected {
        background-color: #bdbdbd;
        color: #333333;
    }
    QMenuBar {
        background-color: #e3f2fd;
        color: #333333;
    }
    QMenuBar::item:selected {
        background-color: #1976d2;
        color: white;
    }
    QMenu {
        background-color: #ffffff;
        border: 1px solid #cccccc;
    }
    QMenu::item:selected {
        background-color: #1976d2;
        color: white;
    }
    QStatusBar {
        background-color: #e3f2fd;
        color: #666666;
    }
    QScrollArea {
        border: none;
    }
    QLabel#title {
        font-size: 24px;
        font-weight: bold;
        color: #1565c0;
    }
    QLabel#subtitle {
        font-size: 14px;
        color: #666666;
    }
    QLabel#clock {
        font-size: 28px;
        font-weight: bold;
        color: #1565c0;
        font-family: "Consolas", "Courier New", monospace;
    }
    QLabel#date {
        font-size: 16px;
        color: #666666;
    }
    QLabel#info_label {
        color: #2e7d32;
        font-weight: bold;
    }
    QLabel#error_label {
        color: #c62828;
        font-weight: bold;
    }
    QComboBox::drop-down {
        border: none;
        width: 30px;
    }
    QComboBox QAbstractItemView {
        background-color: #ffffff;
        color: #333333;
        selection-background-color: #1976d2;
    }
    """


class LogDialog(QDialog):
    """日志编辑对话框"""

    log_saved = pyqtSignal()

    def __init__(self, mode="add", log_data=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.log_data = log_data or {}
        self.settings = SettingsManager()
        self.init_ui()
        self.load_defaults()

    def init_ui(self):
        if self.mode == "add":
            self.setWindowTitle("添加日志")
        elif self.mode == "edit":
            self.setWindowTitle("编辑日志")
        else:
            self.setWindowTitle("查看日志")

        self.setMinimumSize(700, 650)

        # 根据父窗口主题设置样式
        parent_theme = 'dark'
        if self.parent() and hasattr(self.parent(), 'current_theme'):
            parent_theme = self.parent().current_theme
        self.setStyleSheet(StyleSheet.DARK if parent_theme == 'dark' else StyleSheet.LIGHT)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("日志记录")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        form_layout = QFormLayout(content_widget)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # 基本信息
        basic_group = QGroupBox("基本信息")
        basic_layout = QGridLayout(basic_group)

        self.callsign_edit = QLineEdit()
        self.callsign_edit.setPlaceholderText("如：BA8AQA")
        self.callsign_edit.setMaxLength(10)
        basic_layout.addWidget(QLabel("对方呼号*："), 0, 0)
        basic_layout.addWidget(self.callsign_edit, 0, 1)

        self.freq_edit = QLineEdit()
        self.freq_edit.setPlaceholderText("如：144.000MHz")
        basic_layout.addWidget(QLabel("频率："), 0, 2)
        basic_layout.addWidget(self.freq_edit, 0, 3)

        date_layout = QHBoxLayout()
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setValue(datetime.now().month)
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setValue(datetime.now().day)

        date_layout.addWidget(self.year_spin)
        date_layout.addWidget(QLabel("年"))
        date_layout.addWidget(self.month_spin)
        date_layout.addWidget(QLabel("月"))
        date_layout.addWidget(self.day_spin)
        date_layout.addWidget(QLabel("日"))
        date_layout.addStretch()

        basic_layout.addWidget(QLabel("日期*："), 1, 0)
        basic_layout.addLayout(date_layout, 1, 1)

        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("HHMM（如：1316）")
        self.time_edit.setMaxLength(4)
        self.time_edit.setFixedWidth(120)
        now_time = datetime.now().strftime("%H%M")
        self.time_edit.setText(now_time)
        basic_layout.addWidget(QLabel("时间*："), 1, 2)
        basic_layout.addWidget(self.time_edit, 1, 3)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["FM", "SSB", "CW", "AM", "FT8", "FT4", "JT65", "PSK", "RTTY", "SSTV", "其他"])
        self.mode_combo.setEditable(True)
        basic_layout.addWidget(QLabel("模式*："), 2, 0)
        basic_layout.addWidget(self.mode_combo, 2, 1)

        self.qth_edit = QLineEdit()
        self.qth_edit.setPlaceholderText("通联地点")
        basic_layout.addWidget(QLabel("QTH："), 2, 2)
        basic_layout.addWidget(self.qth_edit, 2, 3)

        form_layout.addRow(basic_group)

        # 信号报告
        rst_group = QGroupBox("信号报告")
        rst_layout = QGridLayout(rst_group)

        self.rst_self_edit = QLineEdit()
        self.rst_self_edit.setPlaceholderText("如：59")
        self.rst_self_edit.setMaxLength(3)
        self.rst_self_edit.setFixedWidth(80)
        rst_layout.addWidget(QLabel("对方给我*："), 0, 0)
        rst_layout.addWidget(self.rst_self_edit, 0, 1)
        rst_layout.addWidget(QLabel("（他听我）"), 0, 2)

        self.rst_side_edit = QLineEdit()
        self.rst_side_edit.setPlaceholderText("如：58")
        self.rst_side_edit.setMaxLength(3)
        self.rst_side_edit.setFixedWidth(80)
        rst_layout.addWidget(QLabel("我给对方*："), 0, 3)
        rst_layout.addWidget(self.rst_side_edit, 0, 4)
        rst_layout.addWidget(QLabel("（我听他）"), 0, 5)
        rst_layout.setColumnStretch(6, 1)

        form_layout.addRow(rst_group)

        # 功率与设备
        power_group = QGroupBox("功率与设备")
        power_layout = QGridLayout(power_group)

        self.power_self_edit = QLineEdit()
        self.power_self_edit.setPlaceholderText("如：5W")
        self.power_self_edit.setFixedWidth(100)
        power_layout.addWidget(QLabel("我的功率*："), 0, 0)
        power_layout.addWidget(self.power_self_edit, 0, 1)

        self.power_side_edit = QLineEdit()
        self.power_side_edit.setPlaceholderText("如：8W")
        self.power_side_edit.setFixedWidth(100)
        power_layout.addWidget(QLabel("对方功率："), 0, 2)
        power_layout.addWidget(self.power_side_edit, 0, 3)

        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("使用的设备型号")
        power_layout.addWidget(QLabel("设备："), 1, 0)
        power_layout.addWidget(self.device_edit, 1, 1, 1, 3)

        form_layout.addRow(power_group)

        # QSL 卡片
        qsl_group = QGroupBox("QSL 卡片")
        qsl_layout = QGridLayout(qsl_group)

        self.qsl_rx_edit = QLineEdit()
        self.qsl_rx_edit.setPlaceholderText("YYYYMMDD（如：20260612）")
        self.qsl_rx_edit.setMaxLength(8)
        qsl_layout.addWidget(QLabel("收到QSL："), 0, 0)
        qsl_layout.addWidget(self.qsl_rx_edit, 0, 1)

        self.qsl_send_edit = QLineEdit()
        self.qsl_send_edit.setPlaceholderText("YYYYMMDD（如：20260620）")
        self.qsl_send_edit.setMaxLength(8)
        qsl_layout.addWidget(QLabel("发出QSL："), 0, 2)
        qsl_layout.addWidget(self.qsl_send_edit, 0, 3)

        form_layout.addRow(qsl_group)

        # 备注
        remark_group = QGroupBox("备注")
        remark_layout = QVBoxLayout(remark_group)
        self.remarks_edit = QTextEdit()
        self.remarks_edit.setMaximumHeight(80)
        self.remarks_edit.setPlaceholderText("其他备注信息...")
        remark_layout.addWidget(self.remarks_edit)

        form_layout.addRow(remark_group)

        # 错误提示
        self.error_label = QLabel("")
        self.error_label.setObjectName("error_label")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addRow(self.error_label)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # 按钮
        btn_layout = QHBoxLayout()

        if self.mode in ("add", "edit"):
            self.save_btn = QPushButton("保存")
            self.save_btn.setObjectName("success")
            self.save_btn.clicked.connect(self.save_log)
            btn_layout.addWidget(self.save_btn)

        if self.mode == "edit":
            self.delete_btn = QPushButton("删除")
            self.delete_btn.setObjectName("danger")
            self.delete_btn.clicked.connect(self.delete_log)
            btn_layout.addWidget(self.delete_btn)

        self.cancel_btn = QPushButton("关闭")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        # 查看模式禁用输入
        if self.mode == "view":
            for widget in [
                self.callsign_edit, self.freq_edit, self.year_spin, self.month_spin,
                self.day_spin, self.time_edit, self.mode_combo, self.qth_edit,
                self.rst_self_edit, self.rst_side_edit, self.power_self_edit,
                self.power_side_edit, self.device_edit, self.qsl_rx_edit,
                self.qsl_send_edit, self.remarks_edit
            ]:
                widget.setEnabled(False)

        if self.log_data:
            self.load_data()

    def load_defaults(self):
        default_mode = self.settings.get('default_mode', 'FM')
        default_power = self.settings.get('default_power', '5W')
        default_device = self.settings.get('default_device', 'UVK6')

        self.mode_combo.setCurrentText(default_mode)
        self.power_self_edit.setText(default_power)
        self.device_edit.setText(default_device)

    def load_data(self):
        self.callsign_edit.setText(self.log_data.get('Callsign', ''))
        self.freq_edit.setText(self.log_data.get('Freq', ''))
        self.year_spin.setValue(self.log_data.get('Year', datetime.now().year))
        self.month_spin.setValue(self.log_data.get('Month', datetime.now().month))
        self.day_spin.setValue(self.log_data.get('Day', datetime.now().day))
        self.time_edit.setText(self.log_data.get('Time', ''))
        self.mode_combo.setCurrentText(self.log_data.get('Mode', 'FM'))
        self.qth_edit.setText(self.log_data.get('QTH', ''))
        self.rst_self_edit.setText(self.log_data.get('Rst_self', ''))
        self.rst_side_edit.setText(self.log_data.get('Rst_side', ''))
        self.power_self_edit.setText(self.log_data.get('Power_self', ''))
        self.power_side_edit.setText(self.log_data.get('Power_side', ''))
        self.device_edit.setText(self.log_data.get('Device', ''))
        self.qsl_rx_edit.setText(self.log_data.get('QSL_RX', ''))
        self.qsl_send_edit.setText(self.log_data.get('QSL_SEND', ''))
        self.remarks_edit.setPlainText(self.log_data.get('Remarks', ''))

    def validate_inputs(self):
        errors = []

        ok, result = Validator.validate_callsign(self.callsign_edit.text())
        if not ok:
            errors.append("呼号：" + result)
        else:
            self.callsign_edit.setText(result)

        ok, result = Validator.validate_date(
            self.year_spin.value(),
            self.month_spin.value(),
            self.day_spin.value()
        )
        if not ok:
            errors.append("日期：" + result)

        ok, result = Validator.validate_time(self.time_edit.text())
        if not ok:
            errors.append("时间：" + result)
        else:
            self.time_edit.setText(result)

        if not self.mode_combo.currentText().strip():
            errors.append("模式：不能为空")

        ok, result = Validator.validate_rst(self.rst_self_edit.text())
        if not ok:
            errors.append("对方给我报告：" + result)
        else:
            self.rst_self_edit.setText(result)

        ok, result = Validator.validate_rst(self.rst_side_edit.text())
        if not ok:
            errors.append("我给对方报告：" + result)
        else:
            self.rst_side_edit.setText(result)

        ok, result = Validator.validate_power(self.power_self_edit.text())
        if not ok:
            errors.append("我的功率：" + result)
        else:
            self.power_self_edit.setText(result)

        if self.power_side_edit.text().strip():
            ok, result = Validator.validate_power(self.power_side_edit.text())
            if not ok:
                errors.append("对方功率：" + result)
            else:
                self.power_side_edit.setText(result)

        ok, result = Validator.validate_freq(self.freq_edit.text())
        if not ok:
            errors.append("频率：" + result)
        else:
            self.freq_edit.setText(result)

        ok, result = Validator.validate_qsl_date(self.qsl_rx_edit.text())
        if not ok:
            errors.append("收到QSL：" + result)
        else:
            self.qsl_rx_edit.setText(result)

        ok, result = Validator.validate_qsl_date(self.qsl_send_edit.text())
        if not ok:
            errors.append("发出QSL：" + result)
        else:
            self.qsl_send_edit.setText(result)

        if errors:
            self.error_label.setText("\n".join(errors))
            return False

        self.error_label.setText("")
        return True

    def save_log(self):
        if not self.validate_inputs():
            return

        log_dict = {
            'Callsign': self.callsign_edit.text().strip().upper(),
            'Freq': self.freq_edit.text().strip(),
            'Year': self.year_spin.value(),
            'Month': self.month_spin.value(),
            'Day': self.day_spin.value(),
            'Time': self.time_edit.text().strip(),
            'Mode': self.mode_combo.currentText().strip(),
            'Power_self': self.power_self_edit.text().strip(),
            'Power_side': self.power_side_edit.text().strip(),
            'Rst_self': self.rst_self_edit.text().strip(),
            'Rst_side': self.rst_side_edit.text().strip(),
            'QTH': self.qth_edit.text().strip(),
            'Device': self.device_edit.text().strip(),
            'QSL_RX': self.qsl_rx_edit.text().strip(),
            'QSL_SEND': self.qsl_send_edit.text().strip(),
            'Remarks': self.remarks_edit.toPlainText().strip()
        }

        db = Database()
        try:
            if self.mode == "add":
                ok, msg = db.add(log_dict)
            else:
                log_id = self.log_data.get('id')
                ok, msg = db.update(log_id, log_dict)

            if ok:
                QMessageBox.information(self, "成功", msg)
                self.log_saved.emit()
                self.accept()
            else:
                QMessageBox.warning(self, "失败", msg)
        finally:
            db.close()

    def delete_log(self):
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除与 " + self.log_data.get('Callsign', '') + " 的通联记录吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            db = Database()
            try:
                ok, msg = db.delete(self.log_data.get('id'))
                if ok:
                    QMessageBox.information(self, "成功", msg)
                    self.log_saved.emit()
                    self.accept()
                else:
                    QMessageBox.warning(self, "失败", msg)
            finally:
                db.close()


class SettingsDialog(QDialog):
    """设置对话框"""

    settings_changed = pyqtSignal()
    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("设置")
        self.setMinimumSize(550, 500)

        # 根据父窗口主题设置样式
        parent_theme = 'dark'
        if self.parent() and hasattr(self.parent(), 'current_theme'):
            parent_theme = self.parent().current_theme
        self.setStyleSheet(StyleSheet.DARK if parent_theme == 'dark' else StyleSheet.LIGHT)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("软件设置")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 本台信息
        info_group = QGroupBox("本台信息")
        info_layout = QFormLayout(info_group)
        info_layout.setSpacing(10)

        self.callsign_edit = QLineEdit()
        self.callsign_edit.setPlaceholderText("如：BA8AQA")
        info_layout.addRow("本台呼号：", self.callsign_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("操作员姓名")
        info_layout.addRow("操作员：", self.name_edit)

        self.qth_edit = QLineEdit()
        self.qth_edit.setPlaceholderText("常用QTH")
        info_layout.addRow("常用QTH：", self.qth_edit)

        self.grid_edit = QLineEdit()
        self.grid_edit.setPlaceholderText("网格定位（如：OM66）")
        info_layout.addRow("网格定位：", self.grid_edit)

        layout.addWidget(info_group)

        # 默认参数
        default_group = QGroupBox("默认参数")
        default_layout = QFormLayout(default_group)
        default_layout.setSpacing(10)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["FM", "SSB", "CW", "AM", "FT8", "FT4", "JT65", "PSK", "RTTY", "SSTV"])
        self.mode_combo.setEditable(True)
        default_layout.addRow("默认模式：", self.mode_combo)

        self.power_edit = QLineEdit()
        self.power_edit.setPlaceholderText("如：5W")
        default_layout.addRow("默认功率：", self.power_edit)

        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("默认设备型号")
        default_layout.addRow("默认设备：", self.device_edit)

        layout.addWidget(default_group)

        # 外观设置
        theme_group = QGroupBox("外观")
        theme_layout = QFormLayout(theme_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色", "浅色"])
        theme_layout.addRow("主题：", self.theme_combo)

        layout.addWidget(theme_group)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("success")
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def load_settings(self):
        self.callsign_edit.setText(self.settings.get('my_callsign', ''))
        self.name_edit.setText(self.settings.get('my_name', ''))
        self.qth_edit.setText(self.settings.get('my_qth', ''))
        self.grid_edit.setText(self.settings.get('my_grid', ''))
        self.mode_combo.setCurrentText(self.settings.get('default_mode', 'FM'))
        self.power_edit.setText(self.settings.get('default_power', '5W'))
        self.device_edit.setText(self.settings.get('default_device', 'UVK6'))
        theme = self.settings.get('theme', 'dark')
        self.theme_combo.setCurrentIndex(0 if theme == 'dark' else 1)

    def save_settings(self):
        self.settings.set('my_callsign', self.callsign_edit.text().strip())
        self.settings.set('my_name', self.name_edit.text().strip())
        self.settings.set('my_qth', self.qth_edit.text().strip())
        self.settings.set('my_grid', self.grid_edit.text().strip())
        self.settings.set('default_mode', self.mode_combo.currentText().strip())
        self.settings.set('default_power', self.power_edit.text().strip())
        self.settings.set('default_device', self.device_edit.text().strip())
        new_theme = 'dark' if self.theme_combo.currentIndex() == 0 else 'light'
        self.settings.set('theme', new_theme)

        self.settings_changed.emit()
        self.theme_changed.emit(new_theme)
        QMessageBox.information(self, "成功", "设置已保存！")
        self.accept()


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.settings = SettingsManager()
        self.current_theme = self.settings.get('theme', 'dark')
        self.init_ui()
        self.load_logs()
        self.start_clock()
        self.apply_theme()

    def init_ui(self):
        self.setWindowTitle("HamLog - 业余无线电台日志管理系统")
        self.setMinimumSize(1200, 800)

        # 菜单栏
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")

        exit_action = QAction("退出", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        log_menu = menubar.addMenu("日志")
        add_action = QAction("添加日志", self)
        add_action.setShortcut(QKeySequence("Ctrl+N"))
        add_action.triggered.connect(self.open_add_dialog)
        log_menu.addAction(add_action)

        settings_menu = menubar.addMenu("设置")
        settings_action = QAction("软件设置", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        settings_menu.addAction(settings_action)

        # 添加主题切换菜单
        view_menu = menubar.addMenu("视图")
        toggle_theme_action = QAction("切换主题", self)
        toggle_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(toggle_theme_action)

        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # 独立链接菜单
        website_action = QAction("作者主页", self)
        website_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://space.bilibili.com/1297822096?")))
        help_menu.addAction(website_action)

        github_action = QAction("GitHub", self)
        github_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/ARPRC-BA8AQA/HamLog")))
        help_menu.addAction(github_action)

        help_menu.addSeparator()  # 分隔线

        # 打开软件安装文件夹
        open_folder_action = QAction("打开软件安装文件夹", self)
        open_folder_action.triggered.connect(self.open_install_folder)
        help_menu.addAction(open_folder_action)

        # 清空数据库
        clear_db_action = QAction("清空数据库", self)
        clear_db_action.triggered.connect(self.clear_database)
        help_menu.addAction(clear_db_action)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 顶部信息栏
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setSpacing(20)

        # 左侧：呼号信息
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(5)

        self.callsign_label = QLabel("BA8AQA")
        self.callsign_label.setObjectName("title")
        self.callsign_label.setStyleSheet("font-size: 32px; color: #4fc3f7;")
        info_layout.addWidget(self.callsign_label)

        self.info_detail = QLabel("操作员：-  |  QTH：-  |  网格：-")
        self.info_detail.setObjectName("subtitle")
        info_layout.addWidget(self.info_detail)

        top_layout.addWidget(info_widget, stretch=1)

        # 中间：统计信息
        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)
        stats_layout.setSpacing(30)

        self.total_label = QLabel("总通联：0")
        self.total_label.setStyleSheet("font-size: 16px; color: #81c784;")
        stats_layout.addWidget(self.total_label)

        self.today_label = QLabel("今日：0")
        self.today_label.setStyleSheet("font-size: 16px; color: #ffb74d;")
        stats_layout.addWidget(self.today_label)

        top_layout.addWidget(stats_widget)

        # 右侧：日期时间
        clock_widget = QWidget()
        clock_layout = QVBoxLayout(clock_widget)
        clock_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.clock_label = QLabel("00:00:00")
        self.clock_label.setObjectName("clock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_layout.addWidget(self.clock_label)

        self.date_label = QLabel("2026年06月15日 星期一")
        self.date_label.setObjectName("date")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_layout.addWidget(self.date_label)

        top_layout.addWidget(clock_widget)

        main_layout.addWidget(top_widget)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3c3c3c;")
        main_layout.addWidget(line)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索呼号、QTH、设备、备注...")
        self.search_edit.setFixedWidth(300)
        self.search_edit.returnPressed.connect(self.search_logs)
        toolbar.addWidget(self.search_edit)

        search_btn = QPushButton("搜索")
        search_btn.setFixedWidth(80)
        search_btn.clicked.connect(self.search_logs)
        toolbar.addWidget(search_btn)

        toolbar.addStretch()

        add_btn = QPushButton("+ 添加日志")
        add_btn.setObjectName("success")
        add_btn.setFixedWidth(120)
        add_btn.clicked.connect(self.open_add_dialog)
        toolbar.addWidget(add_btn)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.load_logs)
        toolbar.addWidget(refresh_btn)

        main_layout.addLayout(toolbar)

        # 日志表格
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(16)
        self.log_table.setHorizontalHeaderLabels([
            "ID", "呼号", "频率", "年", "月", "日", "时间", "模式",
            "我的功率", "对方功率", "给我报告", "我给报告", "QTH", "设备",
            "收到QSL", "发出QSL"
        ])
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.log_table.setColumnHidden(0, True)
        self.log_table.doubleClicked.connect(self.on_table_double_click)
        self.log_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_table.customContextMenuRequested.connect(self.show_context_menu)

        main_layout.addWidget(self.log_table)

        # 底部状态栏
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")

        self.load_station_info()

    def apply_theme(self):
        """应用当前主题"""
        if self.current_theme == 'light':
            self.setStyleSheet(StyleSheet.LIGHT)
        else:
            self.setStyleSheet(StyleSheet.DARK)

    def toggle_theme(self):
        """切换主题"""
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.settings.set('theme', self.current_theme)
        self.apply_theme()
        # 刷新所有子窗口样式
        for widget in self.findChildren(QWidget):
            widget.setStyleSheet(self.styleSheet())

    def start_clock(self):
        self.update_clock()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)

    def update_clock(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M:%S"))
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        self.date_label.setText(f"{now.year}年{now.month:02d}月{now.day:02d}日 {weekdays[now.weekday()]}")

    def load_station_info(self):
        callsign = self.settings.get('my_callsign', 'BA8AQA')
        name = self.settings.get('my_name', '')
        qth = self.settings.get('my_qth', '')
        grid = self.settings.get('my_grid', '')

        self.callsign_label.setText(callsign)
        detail = []
        if name:
            detail.append("操作员：" + name)
        if qth:
            detail.append("QTH：" + qth)
        if grid:
            detail.append("网格：" + grid)

        if detail:
            self.info_detail.setText("  |  ".join(detail))
        else:
            self.info_detail.setText("点击设置配置本台信息")

    def load_logs(self):
        logs = self.db.get_all()
        self.populate_table(logs)
        self.update_stats()
        self.statusbar.showMessage("共 " + str(len(logs)) + " 条记录")

    def populate_table(self, logs):
        self.log_table.setRowCount(len(logs))

        for row, log in enumerate(logs):
            self.log_table.setItem(row, 0, QTableWidgetItem(str(log.get('id', ''))))
            self.log_table.setItem(row, 1, QTableWidgetItem(str(log.get('Callsign', ''))))
            self.log_table.setItem(row, 2, QTableWidgetItem(str(log.get('Freq', ''))))
            self.log_table.setItem(row, 3, QTableWidgetItem(str(log.get('Year', ''))))
            self.log_table.setItem(row, 4, QTableWidgetItem(str(log.get('Month', ''))))
            self.log_table.setItem(row, 5, QTableWidgetItem(str(log.get('Day', ''))))
            self.log_table.setItem(row, 6, QTableWidgetItem(str(log.get('Time', ''))))
            self.log_table.setItem(row, 7, QTableWidgetItem(str(log.get('Mode', ''))))
            self.log_table.setItem(row, 8, QTableWidgetItem(str(log.get('Power_self', ''))))
            self.log_table.setItem(row, 9, QTableWidgetItem(str(log.get('Power_side', ''))))
            self.log_table.setItem(row, 10, QTableWidgetItem(str(log.get('Rst_self', ''))))
            self.log_table.setItem(row, 11, QTableWidgetItem(str(log.get('Rst_side', ''))))
            self.log_table.setItem(row, 12, QTableWidgetItem(str(log.get('QTH', ''))))
            self.log_table.setItem(row, 13, QTableWidgetItem(str(log.get('Device', ''))))
            self.log_table.setItem(row, 14, QTableWidgetItem(str(log.get('QSL_RX', ''))))
            self.log_table.setItem(row, 15, QTableWidgetItem(str(log.get('QSL_SEND', ''))))

            self.log_table.setRowHeight(row, 28)

    def update_stats(self):
        logs = self.db.get_all()
        total = len(logs)

        today = datetime.now().strftime("%Y%m%d")
        today_count = 0
        for log in logs:
            y = str(log.get('Year', ''))
            m = str(log.get('Month', '')).zfill(2)
            d = str(log.get('Day', '')).zfill(2)
            if y + m + d == today:
                today_count += 1

        self.total_label.setText("总通联：" + str(total))
        self.today_label.setText("今日：" + str(today_count))

    def search_logs(self):
        keyword = self.search_edit.text().strip()
        if not keyword:
            self.load_logs()
            return

        logs = self.db.search(keyword)
        self.populate_table(logs)
        self.statusbar.showMessage('搜索 "' + keyword + '" 找到 ' + str(len(logs)) + ' 条记录')

    def open_add_dialog(self):
        dialog = LogDialog(mode="add", parent=self)
        dialog.log_saved.connect(self.load_logs)
        dialog.exec()

    def open_edit_dialog(self, log_id):
        log_data = self.db.get_by_id(log_id)
        if log_data:
            dialog = LogDialog(mode="edit", log_data=log_data, parent=self)
            dialog.log_saved.connect(self.load_logs)
            dialog.exec()

    def open_view_dialog(self, log_id):
        log_data = self.db.get_by_id(log_id)
        if log_data:
            dialog = LogDialog(mode="view", log_data=log_data, parent=self)
            dialog.exec()

    def on_table_double_click(self, index):
        row = index.row()
        log_id = int(self.log_table.item(row, 0).text())
        self.open_edit_dialog(log_id)

    def show_context_menu(self, position):
        row = self.log_table.rowAt(position.y())
        if row < 0:
            return

        log_id = int(self.log_table.item(row, 0).text())
        callsign = self.log_table.item(row, 1).text()

        menu = QMenu(self)

        view_action = QAction("查看 " + callsign, self)
        view_action.triggered.connect(lambda: self.open_view_dialog(log_id))
        menu.addAction(view_action)

        edit_action = QAction("编辑 " + callsign, self)
        edit_action.triggered.connect(lambda: self.open_edit_dialog(log_id))
        menu.addAction(edit_action)

        menu.addSeparator()

        delete_action = QAction("删除 " + callsign, self)
        delete_action.triggered.connect(lambda: self.delete_log(log_id, callsign))
        menu.addAction(delete_action)

        menu.exec(self.log_table.viewport().mapToGlobal(position))

    def delete_log(self, log_id, callsign):
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除与 " + callsign + " 的通联记录吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = self.db.delete(log_id)
            if ok:
                QMessageBox.information(self, "成功", msg)
                self.load_logs()
            else:
                QMessageBox.warning(self, "失败", msg)

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self.load_station_info)
        dialog.theme_changed.connect(self.on_theme_changed)
        dialog.exec()

    def on_theme_changed(self, new_theme):
        self.current_theme = new_theme
        self.apply_theme()

    def show_about(self):
        QMessageBox.about(self, "关于 ",
                          "<h2>HamLog 业余无线电台日志管理系统</h2>"
                          "<p>版本：内部--Alpha1</p>"
                          "<p>作者：BA8AQA</p>"
                          "<p>Bilibili:https://space.bilibili.com/1297822096?</p>"
                          "<p>Github:https://github.com/ARPRC-BA8AQA/HamLog</p>"
                          "<p>基于 Python、PyQt6、SQLite 开发</p>"
                          "<p>本软件遵循GPL3协议</p>"
                          "<p>特别鸣谢：BA8AQA    BG5JQN和所有对HamLog开发做出过贡献的人和组织</p>"
                          "<p>73!</p>")

    def open_install_folder(self):
        """用系统文件管理器打开软件所在文件夹"""
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后
            app_dir = Path(sys.executable).parent
        else:
            # 开发环境
            app_dir = Path(__file__).parent

        path = str(app_dir.resolve())

        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{path}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文件夹:\n{e}")

    def clear_database(self):
        """清空数据库"""
        reply = QMessageBox.warning(
            self,
            "警告",
            "这会永久清空所有日志和配置文件，无法恢复！\n\n确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            confirm = QMessageBox.critical(
                self,
                "最终确认",
                "此操作不可撤销！\n所有 QSO 日志、设置将全部丢失。\n\n确定清空吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    # 关闭现有连接
                    self.db.close()
                    self.settings.close()

                    # 删除数据库文件（路径来自 AutoDeal.db_path）
                    db_file = Path(self.db.db_path)
                    if db_file.exists():
                        db_file.unlink()

                    # 重新初始化
                    self.db = Database()
                    self.settings = SettingsManager()

                    # 刷新界面
                    self.load_logs()
                    self.load_station_info()

                    QMessageBox.information(self, "完成", "数据库已清空并重新初始化。")

                except Exception as e:
                    QMessageBox.critical(self, "错误", f"清空失败:\n{e}")
                    # 尝试恢复连接
                    try:
                        self.db = Database()
                        self.settings = SettingsManager()
                    except:
                        pass

    def closeEvent(self, event):
        self.db.close()
        self.settings.close()
        event.accept()


def main():
    app = QApplication(sys.argv)

    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()