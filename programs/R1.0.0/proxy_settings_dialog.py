# -*- coding: utf-8 -*-
"""
ProxySettingsDialog - 代理设置对话框
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QGroupBox, QFormLayout, QMessageBox,
    QTextEdit
)
from PyQt6.QtCore import Qt

from proxy_manager import get_proxy_manager


class ProxySettingsDialog(QDialog):
    """代理设置对话框"""

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self.proxy_mgr = get_proxy_manager()
        self.setWindowTitle("代理设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 说明



        # 启用代理
        self.chk_enabled = QCheckBox("启用代理")
        self.chk_enabled.stateChanged.connect(self.on_enabled_changed)
        layout.addWidget(self.chk_enabled)

        # 使用系统代理
        self.chk_system = QCheckBox("使用系统代理设置")
        self.chk_system.stateChanged.connect(self.on_system_changed)
        layout.addWidget(self.chk_system)

        # 手动代理设置
        self.manual_group = QGroupBox("手动代理配置")
        manual_layout = QFormLayout(self.manual_group)
        manual_layout.setSpacing(10)

        self.txt_http = QLineEdit()
        self.txt_http.setPlaceholderText("http://127.0.0.1:7890")
        manual_layout.addRow("HTTP 代理:", self.txt_http)

        self.txt_https = QLineEdit()
        self.txt_https.setPlaceholderText("http://127.0.0.1:7890")
        manual_layout.addRow("HTTPS 代理:", self.txt_https)

        self.txt_socks5 = QLineEdit()
        self.txt_socks5.setPlaceholderText("socks5://127.0.0.1:7890")
        manual_layout.addRow("SOCKS5 代理:", self.txt_socks5)



        layout.addWidget(self.manual_group)

        # 测试区域
        test_layout = QHBoxLayout()
        self.btn_test = QPushButton("测试代理")
        self.btn_test.clicked.connect(self.test_proxy)
        test_layout.addWidget(self.btn_test)

        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setStyleSheet("color: #81c784;")
        test_layout.addWidget(self.lbl_test_result)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        layout.addStretch()

        # 按钮
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

    def load_settings(self):
        self.proxy_mgr.load_from_settings(self.settings)
        config = self.proxy_mgr.get_config()

        self.chk_enabled.setChecked(config['enabled'])
        self.chk_system.setChecked(config['use_system'])
        self.txt_http.setText(config['http'])
        self.txt_https.setText(config['https'])
        self.txt_socks5.setText(config['socks5'])


        self.on_enabled_changed()
        self.on_system_changed()

    def on_enabled_changed(self):
        enabled = self.chk_enabled.isChecked()
        self.chk_system.setEnabled(enabled)
        self.manual_group.setEnabled(enabled and not self.chk_system.isChecked())

    def on_system_changed(self):
        use_system = self.chk_system.isChecked()
        self.manual_group.setEnabled(not use_system)

    def test_proxy(self):
        self.lbl_test_result.setText("测试中...")
        self.lbl_test_result.setStyleSheet("color: #ffb74d;")

        # 先临时应用当前设置
        config = {
            'enabled': self.chk_enabled.isChecked(),
            'use_system': self.chk_system.isChecked(),
            'http': self.txt_http.text().strip(),
            'https': self.txt_https.text().strip(),
            'socks5': self.txt_socks5.text().strip(),
            'no_proxy': 'localhost,127.0.0.1,::1,gitee.com,ghproxy.com,ghproxy.net,mirror.ghproxy.com',
        }
        old_config = self.proxy_mgr.get_config()
        self.proxy_mgr.set_config(config)

        success, msg = self.proxy_mgr.test_proxy()

        # 恢复旧设置
        self.proxy_mgr.set_config(old_config)

        if success:
            self.lbl_test_result.setText(f"✓ 连接成功 ({msg})")
            self.lbl_test_result.setStyleSheet("color: #81c784;")
        else:
            self.lbl_test_result.setText(f"✗ 连接失败: {msg}")
            self.lbl_test_result.setStyleSheet("color: #e57373;")

    def save_settings(self):
        config = {
            'enabled': self.chk_enabled.isChecked(),
            'use_system': self.chk_system.isChecked(),
            'http': self.txt_http.text().strip(),
            'https': self.txt_https.text().strip(),
            'socks5': self.txt_socks5.text().strip(),
            'no_proxy': 'localhost,127.0.0.1,::1,gitee.com,ghproxy.com,ghproxy.net,mirror.ghproxy.com',
        }
        self.proxy_mgr.set_config(config)
        self.proxy_mgr.save_to_settings(self.settings)

        QMessageBox.information(self, "保存成功", "代理设置已保存并生效")
        self.accept()
