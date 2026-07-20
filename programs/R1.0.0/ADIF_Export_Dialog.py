# -*- coding: utf-8 -*-
"""
ADIF 导出对话框 - 独立功能
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout, QComboBox, QProgressBar, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from datetime import datetime
from pathlib import Path

from ADIF import LoTWADIExporter


class ADIFExportThread(QThread):
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, int)

    def __init__(self, exporter, output_path, query=None, params=None):
        super().__init__()
        self.exporter = exporter
        self.output_path = output_path
        self.query = query
        self.params = params

    def run(self):
        try:
            result = self.exporter.export(
                self.output_path,
                query=self.query,
                params=self.params
            )
            self.finished_signal.emit(
                True,
                f"成功导出 {result['exported']} 条 QSO",
                result['exported']
            )
        except Exception as e:
            self.finished_signal.emit(False, f"导出失败: {str(e)}", 0)


class ADIFExportDialog(QDialog):
    """独立的 ADIF 导出对话框"""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.export_thread = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("导出 ADIF 文件")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # ========== 导出选项 ==========
        options_group = QGroupBox("导出选项")
        options_layout = QFormLayout()
        options_layout.setSpacing(8)
        options_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        options_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # 导出范围
        self.cmb_range = QComboBox()
        self.cmb_range.addItem("全部日志", "all")
        self.cmb_range.addItem("按日期范围", "date_range")
        self.cmb_range.addItem("按波段", "band")
        self.cmb_range.addItem("按模式", "mode")
        self.cmb_range.currentIndexChanged.connect(self.on_range_changed)
        options_layout.addRow("导出范围:", self.cmb_range)

        # 日期范围
        self.date_widget = QWidget()
        date_layout = QHBoxLayout(self.date_widget)
        date_layout.setSpacing(5)
        date_layout.setContentsMargins(0, 0, 0, 0)

        self.txt_start_date = QLineEdit()
        self.txt_start_date.setPlaceholderText("YYYYMMDD")
        self.txt_start_date.setMaximumWidth(100)
        self.txt_start_date.setMinimumWidth(80)

        self.txt_end_date = QLineEdit()
        self.txt_end_date.setPlaceholderText("YYYYMMDD")
        self.txt_end_date.setMaximumWidth(100)
        self.txt_end_date.setMinimumWidth(80)

        date_layout.addWidget(QLabel("从"))
        date_layout.addWidget(self.txt_start_date)
        date_layout.addWidget(QLabel("到"))
        date_layout.addWidget(self.txt_end_date)
        date_layout.addStretch()

        self.date_widget.setVisible(False)
        options_layout.addRow(self.date_widget)

        # 波段选择（带标签）
        self.band_widget = QWidget()
        band_layout = QHBoxLayout(self.band_widget)
        band_layout.setContentsMargins(0, 0, 0, 0)
        self.cmb_band = QComboBox()
        self.cmb_band.addItems(['160M', '80M', '40M', '30M', '20M', '17M', '15M', '12M', '10M', '6M', '2M', '70CM'])
        band_layout.addWidget(self.cmb_band)
        band_layout.addStretch()
        self.band_widget.setVisible(False)
        options_layout.addRow("波段:", self.band_widget)

        # 模式选择（带标签）
        self.mode_widget = QWidget()
        mode_layout = QHBoxLayout(self.mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(['CW', 'SSB', 'FM', 'AM', 'FT8', 'FT4', 'JT65', 'RTTY', 'PSK31'])
        mode_layout.addWidget(self.cmb_mode)
        mode_layout.addStretch()
        self.mode_widget.setVisible(False)
        options_layout.addRow("模式:", self.mode_widget)



        # 呼号
        self.txt_callsign = QLineEdit()
        self.txt_callsign.setPlaceholderText("你的呼号")
        options_layout.addRow("电台呼号:", self.txt_callsign)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # ========== 输出路径 ==========
        path_group = QGroupBox("输出路径")
        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        self.txt_output_path = QLineEdit()
        default_name = f"HamLog_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.adi"
        self.txt_output_path.setText(str(Path.home() / "Desktop" / default_name))
        self.txt_output_path.setMinimumWidth(300)

        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.setFixedWidth(70)
        self.btn_browse.clicked.connect(self.browse_output)

        path_layout.addWidget(self.txt_output_path, stretch=1)
        path_layout.addWidget(self.btn_browse)

        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # ========== 进度条 ==========
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # ========== 按钮 ==========
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_export = QPushButton("导出")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.btn_export.clicked.connect(self.do_export)

        self.btn_close = QPushButton("关闭")
        self.btn_close.setMinimumWidth(70)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self.setLayout(layout)

    def on_range_changed(self, index):
        """切换导出范围时显示/隐藏对应控件"""
        range_type = self.cmb_range.currentData()

        self.date_widget.setVisible(range_type == "date_range")
        self.band_widget.setVisible(range_type == "band")
        self.mode_widget.setVisible(range_type == "mode")

        self.adjustSize()

    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 ADIF 文件",
            self.txt_output_path.text(),
            "ADI Files (*.adi);;All Files (*)"
        )
        if file_path:
            self.txt_output_path.setText(file_path)

    def do_export(self):
        output_path = self.txt_output_path.text().strip()
        if not output_path:
            QMessageBox.warning(self, "提示", "请选择输出路径")
            return

        callsign = self.txt_callsign.text().strip() or None

        exporter = LoTWADIExporter(self.db_path, station_callsign=callsign)

        # 构建查询条件
        query = None
        params = None

        range_type = self.cmb_range.currentData()
        if range_type == "date_range":
            start = self.txt_start_date.text().strip()
            end = self.txt_end_date.text().strip()
            if start and end:
                query = """
                    SELECT * FROM log 
                    WHERE (Year || printf('%02d', Month) || printf('%02d', Day)) BETWEEN ? AND ?
                    ORDER BY Year, Month, Day, Time
                """
                params = (start, end)
        elif range_type == "band":
            band = self.cmb_band.currentText()
            # 修复：使用频率关键字映射，解决 LIKE '%2M%' 无法匹配 '144.000MHz' 的问题
            band_freq_map = {
                '160M': ['1.8', '1.9', '2.0', '160M'],
                '80M': ['3.5', '3.8', '4.0', '80M'],
                '40M': ['7.0', '7.1', '7.2', '40M'],
                '30M': ['10.1', '10.2', '30M'],
                '20M': ['14.0', '14.1', '14.2', '14.3', '20M'],
                '17M': ['18.0', '18.1', '17M'],
                '15M': ['21.0', '21.1', '21.2', '21.3', '15M'],
                '12M': ['24.9', '24.8', '12M'],
                '10M': ['28.0', '29.0', '29.5', '10M'],
                '6M': ['50.', '51.', '6M'],
                '2M': ['144.', '145.', '146.', '2M'],
                '70CM': ['430.', '440.', '70CM', '70cm'],
            }
            keywords = band_freq_map.get(band, [band])
            conditions = ' OR '.join(['Freq LIKE ?' for _ in keywords])
            query = f"SELECT * FROM log WHERE {conditions} ORDER BY Year, Month, Day, Time"
            params = tuple(f"%{k}%" for k in keywords)
        elif range_type == "mode":
            mode = self.cmb_mode.currentText()
            query = "SELECT * FROM log WHERE Mode = ? ORDER BY Year, Month, Day, Time"
            params = (mode,)

        self.progress.setVisible(True)
        self.btn_export.setEnabled(False)

        self.export_thread = ADIFExportThread(exporter, output_path, query, params)
        self.export_thread.finished_signal.connect(self.on_export_finished)
        self.export_thread.start()

    def on_export_finished(self, success: bool, message: str, count: int):
        self.progress.setVisible(False)
        self.btn_export.setEnabled(True)

        if success:
            QMessageBox.information(self, "导出完成", message)
        else:
            QMessageBox.critical(self, "导出失败", message)