# -*- coding: utf-8 -*-
"""
LogViewerDialog - 软件运行日志查看器
支持过滤、搜索、导出、实时刷新
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog, QGroupBox, QSpinBox,
    QTextEdit, QSplitter, QWidget, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from datetime import datetime

from app_logger import get_logger


class LogViewerDialog(QDialog):
    """日志查看器对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        self.setWindowTitle("软件运行日志")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self.resize(1100, 700)
        self.setup_ui()
        self.refresh_logs()

        # 绑定信号
        self.logger.log_recorded.connect(self.on_new_log)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # === 过滤工具栏 ===
        filter_group = QGroupBox("过滤条件")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setSpacing(10)

        filter_layout.addWidget(QLabel("级别:"))
        self.cmb_level = QComboBox()
        self.cmb_level.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.cmb_level.setCurrentText("ALL")
        self.cmb_level.currentIndexChanged.connect(self.refresh_logs)
        filter_layout.addWidget(self.cmb_level)

        filter_layout.addWidget(QLabel("搜索:"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("搜索日志内容或来源...")
        self.txt_search.setMinimumWidth(200)
        self.txt_search.returnPressed.connect(self.refresh_logs)
        filter_layout.addWidget(self.txt_search, stretch=1)

        self.btn_search = QPushButton("🔍 搜索")
        self.btn_search.clicked.connect(self.refresh_logs)
        filter_layout.addWidget(self.btn_search)

        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self.refresh_logs)
        filter_layout.addWidget(self.btn_refresh)

        layout.addWidget(filter_group)

        # === 日志表格 ===
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(4)
        self.log_table.setHorizontalHeaderLabels(["时间", "级别", "来源", "消息"])
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.log_table.setColumnWidth(0, 150)
        self.log_table.setColumnWidth(1, 80)
        self.log_table.setColumnWidth(2, 120)

        # 级别颜色映射
        self.level_colors = {
            "DEBUG": "#9e9e9e",
            "INFO": "#4fc3f7",
            "WARNING": "#ffb74d",
            "ERROR": "#e57373",
            "CRITICAL": "#f44336",
        }

        layout.addWidget(self.log_table)

        # === 统计信息 ===
        stats_layout = QHBoxLayout()
        self.lbl_stats = QLabel("统计: 加载中...")
        stats_layout.addWidget(self.lbl_stats)
        stats_layout.addStretch()

        self.btn_export = QPushButton("导出日志")
        self.btn_export.clicked.connect(self.export_logs)
        stats_layout.addWidget(self.btn_export)

        self.btn_clear = QPushButton("清理旧日志")
        self.btn_clear.clicked.connect(self.clear_old_logs)
        stats_layout.addWidget(self.btn_clear)

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        stats_layout.addWidget(self.btn_close)

        layout.addLayout(stats_layout)

    def refresh_logs(self):
        """刷新日志列表"""
        level = self.cmb_level.currentText()
        keyword = self.txt_search.text().strip() or None

        logs = self.logger.query_logs(level=level if level != "ALL" else None,
                                       keyword=keyword, limit=500)

        self.log_table.setRowCount(len(logs))

        for row, log in enumerate(logs):
            # 时间
            item_time = QTableWidgetItem(log.get('timestamp', ''))
            item_time.setFont(QFont("Consolas", 10))
            self.log_table.setItem(row, 0, item_time)

            # 级别（带颜色）
            level_text = log.get('level', 'INFO')
            item_level = QTableWidgetItem(level_text)
            color = self.level_colors.get(level_text, "#e0e0e0")
            item_level.setForeground(Qt.GlobalColor.white)
            item_level.setBackground(Qt.GlobalColor.transparent)
            item_level.setData(Qt.ItemDataRole.UserRole + 1, color)
            self.log_table.setItem(row, 1, item_level)

            # 来源
            item_source = QTableWidgetItem(log.get('source', ''))
            self.log_table.setItem(row, 2, item_source)

            # 消息
            item_msg = QTableWidgetItem(log.get('message', ''))
            item_msg.setToolTip(log.get('message', ''))
            self.log_table.setItem(row, 3, item_msg)

            # 行高
            self.log_table.setRowHeight(row, 24)

        self.update_stats()

    def on_new_log(self, level, source, message, timestamp):
        """新日志到达时的处理（自动追加到顶部）"""
        # 检查是否符合当前过滤条件
        current_level = self.cmb_level.currentText()
        if current_level != "ALL" and level != current_level:
            return
        keyword = self.txt_search.text().strip()
        if keyword and keyword not in message and keyword not in source:
            return

        # 插入到第一行
        self.log_table.insertRow(0)

        item_time = QTableWidgetItem(timestamp)
        item_time.setFont(QFont("Consolas", 10))
        self.log_table.setItem(0, 0, item_time)

        item_level = QTableWidgetItem(level)
        color = self.level_colors.get(level, "#e0e0e0")
        item_level.setData(Qt.ItemDataRole.UserRole + 1, color)
        self.log_table.setItem(0, 1, item_level)

        item_source = QTableWidgetItem(source)
        self.log_table.setItem(0, 2, item_source)

        item_msg = QTableWidgetItem(message)
        item_msg.setToolTip(message)
        self.log_table.setItem(0, 3, item_msg)

        self.log_table.setRowHeight(0, 24)

        # 限制行数
        if self.log_table.rowCount() > 500:
            self.log_table.removeRow(500)

        self.update_stats()

    def update_stats(self):
        stats = self.logger.get_stats()
        parts = [f"总计: {stats.get('TOTAL', 0)}"]
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            count = stats.get(level, 0)
            if count > 0:
                parts.append(f"{level}: {count}")
        self.lbl_stats.setText(" | ".join(parts))

    def export_logs(self):
        """导出日志到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志",
            f"HamLog_Logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return

        try:
            level = self.cmb_level.currentText()
            keyword = self.txt_search.text().strip() or None
            logs = self.logger.query_logs(
                level=level if level != "ALL" else None,
                keyword=keyword, limit=10000
            )

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"HamLog 运行日志导出\n")
                f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"过滤级别: {level}\n")
                f.write(f"搜索关键词: {keyword or '无'}\n")
                f.write("=" * 80 + "\n\n")

                for log in logs:
                    f.write(f"[{log['timestamp']}] [{log['level']}] [{log['source']}] {log['message']}\n")

            QMessageBox.information(self, "导出成功", f"已导出 {len(logs)} 条日志到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def clear_old_logs(self):
        """清理旧日志"""
        from PyQt6.QtWidgets import QInputDialog
        days, ok = QInputDialog.getInt(self, "清理旧日志", "保留最近多少天的日志？", 30, 1, 365, 1)
        if ok:
            self.logger.clear_old_logs(days)
            self.refresh_logs()
            QMessageBox.information(self, "完成", f"已清理 {days} 天前的日志")

    def closeEvent(self, event):
        # 断开信号避免内存泄漏
        try:
            self.logger.log_recorded.disconnect(self.on_new_log)
        except Exception:
            pass
        event.accept()
