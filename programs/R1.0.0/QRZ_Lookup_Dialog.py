# -*- coding: utf-8 -*-
"""
QRZ.com 呼号查询模块
通过爬虫 https://www.qrz.com/db/呼号 获取电台信息
"""
import re
import urllib.request
from urllib.error import URLError, HTTPError

# === 新增：代理支持 ===
from proxy_manager import get_proxy_manager

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QGroupBox, QGridLayout,
    QTextEdit, QProgressBar, QFrame, QScrollArea, QWidget
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QFont


class QRZLookupThread(QThread):
    """QRZ查询工作线程"""
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, callsign: str):
        super().__init__()
        self.callsign = callsign.strip().upper()
        self._running = True

    def run(self):
        try:
            result = self._fetch_qrz_info(self.callsign)
            if self._running:
                self.result_ready.emit(result)
        except Exception as e:
            if self._running:
                self.error_occurred.emit(str(e))

    def _fetch_qrz_info(self, callsign: str) -> dict:
        """从QRZ.com获取呼号信息"""
        url = f"https://www.qrz.com/db/{callsign}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
        }

        req = urllib.request.Request(url, headers=headers)

        # === 新增：应用代理 ===
        proxy_mgr = get_proxy_manager()
        if proxy_mgr.is_enabled():
            # 代理已通过 urllib.request.install_opener 全局应用
            pass

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='replace')
        except HTTPError as e:
            if e.code == 404:
                return {
                    'callsign': callsign,
                    'found': False,
                    'error': f"呼号 {callsign} 在QRZ.com数据库中未找到",
                    'url': url
                }
            raise
        except URLError as e:
            raise Exception(f"网络连接失败: {e.reason}")

        info = {
            'callsign': callsign,
            'url': url,
            'found': True,
            'country': None,
            'has_detail': False,
            'has_biography': False,
            'image_url': None,
            'qsl_info': None,
            'name': None,
            'qth': None,
            'grid': None,
            'email': None,
            'license_class': None,
            'previous_call': None,
        }

        # 提取国家 (从 flag 图片)
        flag_match = re.search(r'flags-iso/flat/\d+/([A-Z]{2})\.png', html)
        if flag_match:
            country_code = flag_match.group(1)
            country_map = {
                'CN': 'China (中国)', 'US': 'United States (美国)', 'JP': 'Japan (日本)',
                'DE': 'Germany (德国)', 'GB': 'United Kingdom (英国)', 'FR': 'France (法国)',
                'RU': 'Russia (俄罗斯)', 'AU': 'Australia (澳大利亚)', 'CA': 'Canada (加拿大)',
                'IT': 'Italy (意大利)', 'ES': 'Spain (西班牙)', 'BR': 'Brazil (巴西)',
                'IN': 'India (印度)', 'KR': 'South Korea (韩国)', 'NL': 'Netherlands (荷兰)',
                'UA': 'Ukraine (乌克兰)', 'PL': 'Poland (波兰)', 'SE': 'Sweden (瑞典)',
                'NO': 'Norway (挪威)', 'FI': 'Finland (芬兰)', 'DK': 'Denmark (丹麦)',
                'CH': 'Switzerland (瑞士)', 'AT': 'Austria (奥地利)', 'BE': 'Belgium (比利时)',
                'PT': 'Portugal (葡萄牙)', 'GR': 'Greece (希腊)', 'CZ': 'Czech Republic (捷克)',
                'HU': 'Hungary (匈牙利)', 'RO': 'Romania (罗马尼亚)', 'BG': 'Bulgaria (保加利亚)',
                'HR': 'Croatia (克罗地亚)', 'SI': 'Slovenia (斯洛文尼亚)', 'SK': 'Slovakia (斯洛伐克)',
                'LT': 'Lithuania (立陶宛)', 'LV': 'Latvia (拉脱维亚)', 'EE': 'Estonia (爱沙尼亚)',
                'IE': 'Ireland (爱尔兰)', 'IS': 'Iceland (冰岛)', 'MT': 'Malta (马耳他)',
                'CY': 'Cyprus (塞浦路斯)', 'LU': 'Luxembourg (卢森堡)', 'MC': 'Monaco (摩纳哥)',
                'AD': 'Andorra (安道尔)', 'LI': 'Liechtenstein (列支敦士登)', 'SM': 'San Marino (圣马力诺)',
                'VA': 'Vatican (梵蒂冈)', 'BY': 'Belarus (白俄罗斯)', 'MD': 'Moldova (摩尔多瓦)',
                'GE': 'Georgia (格鲁吉亚)', 'AM': 'Armenia (亚美尼亚)', 'AZ': 'Azerbaijan (阿塞拜疆)',
                'KZ': 'Kazakhstan (哈萨克斯坦)', 'UZ': 'Uzbekistan (乌兹别克斯坦)', 'KG': 'Kyrgyzstan (吉尔吉斯斯坦)',
                'TJ': 'Tajikistan (塔吉克斯坦)', 'TM': 'Turkmenistan (土库曼斯坦)', 'MN': 'Mongolia (蒙古)',
                'KP': 'North Korea (朝鲜)', 'VN': 'Vietnam (越南)', 'LA': 'Laos (老挝)',
                'KH': 'Cambodia (柬埔寨)', 'TH': 'Thailand (泰国)', 'MM': 'Myanmar (缅甸)',
                'MY': 'Malaysia (马来西亚)', 'SG': 'Singapore (新加坡)', 'ID': 'Indonesia (印度尼西亚)',
                'PH': 'Philippines (菲律宾)', 'TW': 'Taiwan (台湾)', 'HK': 'Hong Kong (香港)',
                'MO': 'Macau (澳门)', 'BD': 'Bangladesh (孟加拉)', 'NP': 'Nepal (尼泊尔)',
                'BT': 'Bhutan (不丹)', 'LK': 'Sri Lanka (斯里兰卡)', 'MV': 'Maldives (马尔代夫)',
                'PK': 'Pakistan (巴基斯坦)', 'AF': 'Afghanistan (阿富汗)', 'IR': 'Iran (伊朗)',
                'IQ': 'Iraq (伊拉克)', 'SY': 'Syria (叙利亚)', 'LB': 'Lebanon (黎巴嫩)',
                'JO': 'Jordan (约旦)', 'IL': 'Israel (以色列)', 'SA': 'Saudi Arabia (沙特阿拉伯)',
                'YE': 'Yemen (也门)', 'OM': 'Oman (阿曼)', 'AE': 'UAE (阿联酋)',
                'QA': 'Qatar (卡塔尔)', 'BH': 'Bahrain (巴林)', 'KW': 'Kuwait (科威特)',
                'TR': 'Turkey (土耳其)', 'EG': 'Egypt (埃及)', 'LY': 'Libya (利比亚)',
                'TN': 'Tunisia (突尼斯)', 'DZ': 'Algeria (阿尔及利亚)', 'MA': 'Morocco (摩洛哥)',
                'MR': 'Mauritania (毛里塔尼亚)', 'ML': 'Mali (马里)', 'NE': 'Niger (尼日尔)',
                'TD': 'Chad (乍得)', 'SD': 'Sudan (苏丹)', 'ER': 'Eritrea (厄立特里亚)',
                'DJ': 'Djibouti (吉布提)', 'ET': 'Ethiopia (埃塞俄比亚)', 'SO': 'Somalia (索马里)',
                'KE': 'Kenya (肯尼亚)', 'UG': 'Uganda (乌干达)', 'TZ': 'Tanzania (坦桑尼亚)',
                'RW': 'Rwanda (卢旺达)', 'BI': 'Burundi (布隆迪)', 'MW': 'Malawi (马拉维)',
                'ZM': 'Zambia (赞比亚)', 'ZW': 'Zimbabwe (津巴布韦)', 'MZ': 'Mozambique (莫桑比克)',
                'MG': 'Madagascar (马达加斯加)', 'MU': 'Mauritius (毛里求斯)', 'SC': 'Seychelles (塞舌尔)',
                'KM': 'Comoros (科摩罗)', 'ZA': 'South Africa (南非)', 'NA': 'Namibia (纳米比亚)',
                'BW': 'Botswana (博茨瓦纳)', 'SZ': 'Eswatini (斯威士兰)', 'LS': 'Lesotho (莱索托)',
                'AO': 'Angola (安哥拉)', 'CD': 'DR Congo (刚果民主共和国)', 'CG': 'Congo (刚果共和国)',
                'GA': 'Gabon (加蓬)', 'GQ': 'Equatorial Guinea (赤道几内亚)', 'CM': 'Cameroon (喀麦隆)',
                'CF': 'CAR (中非共和国)', 'ST': 'Sao Tome (圣多美)', 'GN': 'Guinea (几内亚)',
                'GW': 'Guinea-Bissau (几内亚比绍)', 'SN': 'Senegal (塞内加尔)', 'GM': 'Gambia (冈比亚)',
                'SL': 'Sierra Leone (塞拉利昂)', 'LR': 'Liberia (利比里亚)',
                'CI': 'Ivory Coast (科特迪瓦)', 'GH': 'Ghana (加纳)', 'TG': 'Togo (多哥)',
                'BJ': 'Benin (贝宁)', 'NG': 'Nigeria (尼日利亚)', 'MX': 'Mexico (墨西哥)',
                'GT': 'Guatemala (危地马拉)', 'BZ': 'Belize (伯利兹)', 'SV': 'El Salvador (萨尔瓦多)',
                'HN': 'Honduras (洪都拉斯)', 'NI': 'Nicaragua (尼加拉瓜)', 'CR': 'Costa Rica (哥斯达黎加)',
                'PA': 'Panama (巴拿马)', 'CU': 'Cuba (古巴)', 'JM': 'Jamaica (牙买加)',
                'HT': 'Haiti (海地)', 'DO': 'Dominican Rep. (多米尼加)', 'PR': 'Puerto Rico (波多黎各)',
                'CO': 'Colombia (哥伦比亚)', 'VE': 'Venezuela (委内瑞拉)', 'GY': 'Guyana (圭亚那)',
                'SR': 'Suriname (苏里南)', 'GF': 'French Guiana (法属圭亚那)', 'EC': 'Ecuador (厄瓜多尔)',
                'PE': 'Peru (秘鲁)', 'BO': 'Bolivia (玻利维亚)', 'PY': 'Paraguay (巴拉圭)',
                'UY': 'Uruguay (乌拉圭)', 'CL': 'Chile (智利)', 'AR': 'Argentina (阿根廷)',
                'FK': 'Falkland Is. (福克兰群岛)', 'NZ': 'New Zealand (新西兰)', 'FJ': 'Fiji (斐济)',
                'PG': 'Papua New Guinea (巴布亚新几内亚)', 'SB': 'Solomon Is. (所罗门群岛)', 'VU': 'Vanuatu (瓦努阿图)',
                'NC': 'New Caledonia (新喀里多尼亚)', 'PF': 'French Polynesia (法属波利尼西亚)', 'WS': 'Samoa (萨摩亚)',
                'TO': 'Tonga (汤加)', 'KI': 'Kiribati (基里巴斯)', 'NR': 'Nauru (瑙鲁)',
                'TV': 'Tuvalu (图瓦卢)', 'PW': 'Palau (帕劳)', 'MH': 'Marshall Is. (马绍尔群岛)',
                'FM': 'Micronesia (密克罗尼西亚)', 'TK': 'Tokelau (托克劳)',
                'NU': 'Niue (纽埃)', 'CK': 'Cook Is. (库克群岛)', 'AS': 'American Samoa (美属萨摩亚)',
                'GU': 'Guam (关岛)', 'MP': 'N. Mariana Is. (北马里亚纳)', 'UM': 'US Minor Is. (美属小岛屿)',
                'WF': 'Wallis & Futuna (瓦利斯和富图纳)', 'PN': 'Pitcairn (皮特凯恩)',
                'IO': 'BIOT (英属印度洋领地)', 'CX': 'Christmas Is. (圣诞岛)', 'CC': 'Cocos Is. (科科斯群岛)',
                'NF': 'Norfolk Is. (诺福克岛)', 'HM': 'Heard Is. (赫德岛)', 'AQ': 'Antarctica (南极洲)',
                'GS': 'S. Georgia (南乔治亚)', 'SH': 'St. Helena (圣赫勒拿)', 'AC': 'Ascension (阿森松)',
                'TA': 'Tristan (特里斯坦)', 'BV': 'Bouvet Is. (布韦岛)', 'CP': 'Clipperton (克利珀顿)',
            }
            info['country'] = country_map.get(country_code, country_code)

        # 检查是否有详细资料
        if 'Login is required for additional detail' in html:
            info['has_detail'] = True

        # 检查是否有biography
        if 'id="t_bio"' in html or 'biography' in html.lower():
            info['has_biography'] = True

        # 提取头像图片
        img_match = re.search(r'(https://cdn-bio\.qrz\.com/[^"\'\s]+\.jpg[^"\'\s]*)', html)
        if img_match:
            info['image_url'] = img_match.group(1).replace('\\', '')
        else:
            # 尝试从meta标签提取
            og_img = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
            if og_img:
                info['image_url'] = og_img.group(1)

        # 提取QSL信息
        qsl_match = re.search(r'QSL:\s*([^<\n]+)', html, re.IGNORECASE)
        if qsl_match:
            info['qsl_info'] = qsl_match.group(1).strip()

        # 尝试从页面标题提取
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1)
            if ' - ' in title:
                info['page_title'] = title

        # 尝试提取名字
        name_match = re.search(r'class="[^"]*name[^"]*"[^>]*>([^<]+)', html, re.IGNORECASE)
        if name_match:
            info['name'] = name_match.group(1).strip()

        # 尝试从biography iframe提取
        bio_match = re.search(r'src="(https://cdn-bio\.qrz\.com/[^"]+)"', html)
        if bio_match:
            info['bio_iframe_url'] = bio_match.group(1)

        # 检查 LoTW / eQSL
        if 'LoTW' in html or 'lotw' in html.lower():
            info['lotw'] = True
        if 'eQSL' in html or 'eqsl' in html.lower():
            info['eqsl'] = True

        return info

    def stop(self):
        self._running = False
        self.wait(1000)


class QRZLookupDialog(QDialog):
    """QRZ呼号查询对话框"""

    apply_info = pyqtSignal(dict)

    def __init__(self, callsign: str = "", parent=None):
        super().__init__(parent)
        self.callsign = callsign.strip().upper()
        self.lookup_thread = None
        self.current_result = None
        self.setup_ui()

        if self.callsign:
            self.search_input.setText(self.callsign)
            self.do_lookup()

    def setup_ui(self):
        self.setWindowTitle("QRZ.com 呼号查询")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.resize(700, 600)

        parent_theme = 'dark'
        if self.parent() and hasattr(self.parent(), 'current_theme'):
            parent_theme = self.parent().current_theme

        try:
            from HAMLOG_GUI import StyleSheet
            self.setStyleSheet(StyleSheet.DARK if parent_theme == 'dark' else StyleSheet.LIGHT)
        except ImportError:
            pass

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 搜索栏
        search_group = QGroupBox("呼号查询")
        search_layout = QHBoxLayout(search_group)
        search_layout.setSpacing(10)
        search_layout.setContentsMargins(15, 15, 15, 15)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入呼号，如 BA8AQA")
        self.search_input.setMaxLength(10)
        self.search_input.setMinimumHeight(32)
        self.search_input.returnPressed.connect(self.do_lookup)
        search_layout.addWidget(self.search_input, stretch=1)

        self.search_btn = QPushButton("🔍 查询")
        self.search_btn.setMinimumHeight(32)
        self.search_btn.setMinimumWidth(80)
        self.search_btn.clicked.connect(self.do_lookup)
        search_layout.addWidget(self.search_btn)

        self.open_web_btn = QPushButton("🌐 在浏览器打开")
        self.open_web_btn.setMinimumHeight(32)
        self.open_web_btn.clicked.connect(self.open_in_browser)
        self.open_web_btn.setEnabled(False)
        search_layout.addWidget(self.open_web_btn)

        layout.addWidget(search_group)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # 结果显示区域
        result_group = QGroupBox("查询结果")
        result_layout = QVBoxLayout(result_group)
        result_layout.setSpacing(10)
        result_layout.setContentsMargins(15, 15, 15, 15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.result_widget = QWidget()
        self.result_grid = QGridLayout(self.result_widget)
        self.result_grid.setSpacing(10)
        self.result_grid.setContentsMargins(5, 5, 5, 5)
        self.result_grid.setColumnStretch(1, 1)

        self._create_result_labels()

        scroll.setWidget(self.result_widget)
        result_layout.addWidget(scroll)

        layout.addWidget(result_group, stretch=1)

        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.apply_btn = QPushButton("✓ 应用到日志")
        self.apply_btn.setObjectName("success")
        self.apply_btn.setMinimumHeight(36)
        self.apply_btn.setMinimumWidth(120)
        self.apply_btn.clicked.connect(self.apply_to_log)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setToolTip("将查询到的信息填充到日志表单中")

        self.copy_url_btn = QPushButton("📋 复制链接")
        self.copy_url_btn.setMinimumHeight(36)
        self.copy_url_btn.clicked.connect(self.copy_url)
        self.copy_url_btn.setEnabled(False)

        self.close_btn = QPushButton("关闭")
        self.close_btn.setMinimumHeight(36)
        self.close_btn.setMinimumWidth(80)
        self.close_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.copy_url_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _create_result_labels(self):
        fields = [
            ("呼号:", "lbl_callsign"),
            ("国家/地区:", "lbl_country"),
            ("姓名:", "lbl_name"),
            ("QTH:", "lbl_qth"),
            ("网格:", "lbl_grid"),
            ("QSL方式:", "lbl_qsl"),
            ("详细资料:", "lbl_detail"),
            ("Biography:", "lbl_bio"),
            ("LoTW:", "lbl_lotw"),
            ("eQSL:", "lbl_eqsl"),
            ("头像:", "lbl_image"),
            ("QRZ链接:", "lbl_url"),
        ]

        self.result_labels = {}
        for i, (label_text, attr_name) in enumerate(fields):
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold; color: #4fc3f7;")
            value_label = QLabel("-")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            self.result_grid.addWidget(label, i, 0)
            self.result_grid.addWidget(value_label, i, 1)

            self.result_labels[attr_name] = value_label

        self.image_label = QLabel()
        self.image_label.setFixedSize(120, 120)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("border: 1px solid #3c3c3c; border-radius: 4px;")
        self.result_grid.addWidget(self.image_label, 10, 1)

    def do_lookup(self):
        callsign = self.search_input.text().strip().upper()
        if not callsign:
            QMessageBox.warning(self, "提示", "请输入呼号")
            return

        import re
        if not re.match(r'^[A-Z0-9/]+$', callsign):
            QMessageBox.warning(self, "提示", "呼号格式不正确")
            return

        self.callsign = callsign
        self.progress.setVisible(True)
        self.search_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.copy_url_btn.setEnabled(False)
        self.open_web_btn.setEnabled(False)
        self._clear_results()

        self.lookup_thread = QRZLookupThread(callsign)
        self.lookup_thread.result_ready.connect(self.on_lookup_success)
        self.lookup_thread.error_occurred.connect(self.on_lookup_error)
        self.lookup_thread.finished.connect(self.on_lookup_finished)
        self.lookup_thread.start()

    def _clear_results(self):
        for key, label in self.result_labels.items():
            if key != "lbl_image":
                label.setText("-")
                label.setStyleSheet("")
        self.image_label.clear()
        self.image_label.setStyleSheet("border: 1px solid #3c3c3c; border-radius: 4px;")
        self.current_result = None

    def on_lookup_success(self, result: dict):
        self.current_result = result

        if not result.get('found', False):
            self.result_labels["lbl_callsign"].setText(result.get('callsign', '-'))
            self.result_labels["lbl_country"].setText("未找到")
            self.result_labels["lbl_detail"].setText(result.get('error', '未知错误'))
            self.result_labels["lbl_detail"].setStyleSheet("color: #e57373;")
            QMessageBox.information(self, "查询结果", result.get('error', '未找到该呼号'))
            return

        self.result_labels["lbl_callsign"].setText(result.get('callsign', '-'))
        self.result_labels["lbl_callsign"].setStyleSheet("font-weight: bold; font-size: 16px; color: #81c784;")

        self.result_labels["lbl_country"].setText(result.get('country') or '未知')
        self.result_labels["lbl_name"].setText(result.get('name') or '需要登录查看')
        self.result_labels["lbl_qth"].setText(result.get('qth') or '需要登录查看')
        self.result_labels["lbl_grid"].setText(result.get('grid') or '需要登录查看')
        self.result_labels["lbl_qsl"].setText(result.get('qsl_info') or '需要登录查看')

        detail_text = "有详细资料 ✓" if result.get('has_detail') else "无详细资料"
        self.result_labels["lbl_detail"].setText(detail_text)

        bio_text = "有Biography ✓" if result.get('has_biography') else "无Biography"
        self.result_labels["lbl_bio"].setText(bio_text)

        lotw_text = "支持 ✓" if result.get('lotw') else "未知"
        self.result_labels["lbl_lotw"].setText(lotw_text)

        eqsl_text = "支持 ✓" if result.get('eqsl') else "未知"
        self.result_labels["lbl_eqsl"].setText(eqsl_text)

        self.result_labels["lbl_url"].setText(f'<a href="{result.get("url", "")}">{result.get("url", "")}</a>')
        self.result_labels["lbl_url"].setOpenExternalLinks(True)

        image_url = result.get('image_url')
        if image_url:
            self._load_image(image_url)
        else:
            self.image_label.setText("无头像")
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.image_label.setStyleSheet("border: 1px solid #3c3c3c; border-radius: 4px; color: #666;")

        self.apply_btn.setEnabled(True)
        self.copy_url_btn.setEnabled(True)
        self.open_web_btn.setEnabled(True)

    def _load_image(self, url: str):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            # 代理已通过全局 opener 应用
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
                pixmap = QPixmap()
                if pixmap.loadFromData(data):
                    self.image_label.setPixmap(pixmap)
                    self.image_label.setStyleSheet("border: 1px solid #3c3c3c; border-radius: 4px;")
                else:
                    self.image_label.setText("加载失败")
                    self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except Exception:
            self.image_label.setText("加载失败")
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def on_lookup_error(self, error_msg: str):
        QMessageBox.critical(self, "查询失败", f"查询出错:\n{error_msg}")
        self.result_labels["lbl_callsign"].setText(self.callsign)
        self.result_labels["lbl_country"].setText("查询失败")
        self.result_labels["lbl_detail"].setText(error_msg)
        self.result_labels["lbl_detail"].setStyleSheet("color: #e57373;")

    def on_lookup_finished(self):
        self.progress.setVisible(False)
        self.search_btn.setEnabled(True)

    def open_in_browser(self):
        if self.current_result and self.current_result.get('url'):
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(self.current_result['url']))

    def copy_url(self):
        if self.current_result and self.current_result.get('url'):
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self.current_result['url'])
            QMessageBox.information(self, "已复制", "QRZ链接已复制到剪贴板")

    def apply_to_log(self):
        if not self.current_result:
            return

        info = {
            'callsign': self.current_result.get('callsign', ''),
            'country': self.current_result.get('country', ''),
            'name': self.current_result.get('name', ''),
            'qth': self.current_result.get('qth', ''),
            'grid': self.current_result.get('grid', ''),
            'qsl_info': self.current_result.get('qsl_info', ''),
            'url': self.current_result.get('url', ''),
        }

        self.apply_info.emit(info)
        QMessageBox.information(self, "已应用", "信息已应用到日志表单\n(请手动填入对应字段)")

    def closeEvent(self, event):
        if self.lookup_thread and self.lookup_thread.isRunning():
            self.lookup_thread.stop()
        event.accept()


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = QRZLookupDialog("BD8FPH")
    dialog.show()
    sys.exit(app.exec())
