# HamLog 业余无线电台日志管理系统 🎙️

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-41CD52?logo=qt&logoColor=white)](https://www.qt.io/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-0078D6?logo=windows&logoColor=white)]()

> **一款为 HAM 打造的开源业余无线电台日志管理系统**

---

## 📖 简介

HamLog 是一款面向业余无线电爱好者（HAM）开发的电子日志管理软件，使用 **Python + PyQt6 + SQLite3** 构建，遵循 **GPL-3.0** 开源协议。

无论你是刚入门的爱好者还是资深火腿，HamLog 都能帮助你高效管理 QSO 日志、追踪 QSL 卡片收发状态，并支持 ADIF 导出与 LoTW 上传。

---

## ✨ 功能特性

| 功能 | 状态 | 说明 |
|------|------|------|
| 📝 **QSO 日志录入** | ✅ | 支持呼号、频率、模式、功率、RST 报告等完整字段；呼号自动转大写 |
| 🔍 **智能搜索** | ✅ | 支持按呼号、QTH、设备、备注模糊搜索 |
| 📊 **实时统计** | ✅ | 总通联数、今日通联数实时显示 |
| 🎴 **QSL 卡片管理** | ✅ | 记录收发日期，追踪卡片状态 |
| ⚙️ **本台信息配置** | ✅ | 呼号、姓名、QTH、网格定位等个性化设置 |
| 🌓 **深色/浅色主题** | ✅ | 一键切换，适配不同使用环境 |
| 📤 **ADIF 导出** | ✅ | 支持按日期范围、波段、模式筛选导出，适配 LoTW 字段要求 |
| 🌐 **LoTW 上传** | ✅ | 调用 TQSL 签名生成的秘钥文件，通过 HTTP POST 上传至 ARRL LoTW 服务器 |
| 🔎 **QRZ.com 查询** | ✅ | 爬虫获取呼号信息，支持国家识别、头像显示、LoTW/eQSL 状态检测 |
| 🖥️ **界面自定义** | ✅ | 全局字体、字号、表格行高自定义；搜索框选择字体 |
| 🌐 **代理支持** | ✅ | HTTP/HTTPS/SOCKS5 代理，支持读取 Windows 系统代理设置 |
| 📡 **网络延迟监测** | ✅ | 实时 Ping 检测多个节点延迟，状态栏动态显示 |
| 🔄 **自动更新** | ✅ | 从 Gitee 获取版本信息，通过 GitHub Release + ghproxy 下载安装包 |
| 📋 **运行日志** | ✅ | 内置日志查看器，支持分级过滤、搜索、导出；SQLite 缓存 + 文件持久化 |

---

## 🖼️ 界面预览

![HamLog 主界面](screenshots/main_window.png)

*深色主题下的主界面，包含呼号信息栏、实时时钟、网络延迟监测、搜索工具和日志表格*

---

## 🚀 快速开始

### 环境要求

- **操作系统**：Windows 10 / 11 (x64)（主要支持平台）
- **Python**：3.8 或更高版本

### 依赖安装

```bash
# 核心依赖
pip install PyQt6

# 可选依赖（用于高级功能）
pip install PySocks                # SOCKS5 代理支持
```

### 运行程序

```bash
# 克隆仓库
git clone https://github.com/ARPRC-BA8AQA/HamLog.git
cd HamLog

# 运行程序
python "HAMLOG GUI.py"
```

### 打包为可执行文件

```bash
pip install pyinstaller
pyinstaller --onefile --windowed "HAMLOG GUI.py"
```

---

## 📁 项目结构

```
HamLog/
├── HAMLOG GUI.py              # 主程序（PyQt6 GUI）
├── AutoDeal.py                # 后端模块（数据库、校验、设置管理）
├── ADIF.py                    # ADIF 导出和 LoTW 上传支持模块
├── ADIF_Export_Dialog.py      # ADIF 导出对话框
├── LoTW_Upload_Dialog.py      # LoTW 上传对话框（TQSL 签名 + HTTP 上传）
├── QRZ_Lookup_Dialog.py       # QRZ.com 呼号查询模块
├── update_module.py           # 自动更新模块（Gitee 版本检查 + GitHub 下载）
├── proxy_manager.py           # 代理配置管理（HTTP/HTTPS/SOCKS5/系统代理）
├── proxy_settings_dialog.py   # 代理设置对话框
├── font_manager.py            # 字体管理（系统字体异步加载）
├── font_settings_dialog.py    # 字体设置对话框
├── app_logger.py              # 应用日志系统（SQLite 缓存 + 文件轮转）
├── log_viewer_dialog.py       # 日志查看器（过滤、搜索、导出、实时刷新）
├── intertime.py               # 网络延迟检测（Ping）
├── HamLog_UserLicense.txt     # 用户协议与许可声明
├── LICENSE                    # GPL-3.0 许可证
├── README.md                  # 本文件
├── screenshots/               # 界面截图
└── Log.db                     # 本地 SQLite 数据库（运行时生成）
```

---

## 🗄️ 数据库说明

HamLog 使用 **SQLite** 本地数据库，默认存储路径：

| 系统 | 路径 |
|------|------|
| Windows | `%APPDATA%\HamLog\Log.db` |
| macOS | `~/Library/Application Support/HamLog/Log.db` |
| Linux | `~/.local/share/HamLog/Log.db` |

> ⚠️ **建议定期备份 `Log.db` 文件，以防数据丢失！**

### 数据库字段

| 字段 | 说明 | 备注 |
|------|------|------|
| `id` | 自增主键 | — |
| `Callsign` | 对方呼号 | 自动转大写存储 |
| `Freq` | 频率 | 如 `144.000MHz`，支持波段别名和数字解析 |
| `Year/Month/Day` | 通联日期（UTC） | 用户输入本地时间，自动转换为 UTC 存储 |
| `Time` | 通联时间（UTC，HHMM 或 HHMMSS） | 同上 |
| `Mode` | 模式 | FM/SSB/CW/FT8/FT4/JT65/RTTY/PSK31 等 |
| `Power_self` | 我的功率 | 如 `5W` |
| `Power_side` | 对方功率 | 如 `8W` |
| `Rst_self` | 对方给我的报告 | 如 `59` |
| `Rst_side` | 我给对方的报告 | 如 `58` |
| `QTH` | 通联地点 | — |
| `Device` | 使用设备 | — |
| `QSL_RX` | 收到 QSL 日期 | `YYYYMMDD` 格式 |
| `QSL_SEND` | 发出 QSL 日期 | `YYYYMMDD` 格式 |
| `Remarks` | 备注 | — |
| `CreateTime` | 记录创建时间 | 自动填充 |

> 💡 **时区说明**：日志录入界面显示系统本地时区（仅作参考），数据库存储和 ADIF 导出均使用 **UTC 时间**。录入时输入本地时间，程序自动转换。主界面表格上方有 UTC 提示标签。

---

## 🛠️ 高级功能配置

### LoTW 上传

1. 安装 [TrustedQSL (TQSL)](https://www.arrl.org/tqsl-download) 并申请配置证书
2. 在 HamLog 中通过 **文件 → 导出为 ADIF 文件** 导出 `.adi` 文件
3. 通过 **工具 → 上传到 LoTW** 选择 `.adi` 文件，程序将自动调用 TQSL 签名并 HTTP 上传
4. 支持自动查找 TQSL 安装位置、证书识别、台站位置选择、重复 QSO 处理策略

### QRZ.com 查询

- 支持呼号自动查询国家（通过国旗图片识别）、QSL 方式、LoTW/eQSL 支持状态
- 查询结果可一键复制到剪贴板或应用到日志表单
- 支持代理访问

### 代理设置

- 支持 HTTP / HTTPS / SOCKS5 手动代理
- 支持读取 Windows 系统代理设置（注册表）
- 内置代理连通性测试
- 代理配置自动应用到所有网络请求（urllib）

---

## 🤝 参与贡献

我们欢迎所有 HAM 和开发者的贡献！

### 如何贡献

> ⚠️ **注意**：由于著作权归属需要，请不要直接提交 PR，只需要指出问题或想要加入的功能即可。

1. 确定问题或功能需求
2. 添加 [Issue](https://github.com/ARPRC-BA8AQA/HamLog/issues)

---

## 📜 开源协议

本项目遵循 **[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0)** 开源协议。

完整的许可证文本见 `LICENSE` 文件。

用户协议与许可声明见 `HamLog_UserLicense.txt` 文件。

```
HamLog - 业余无线电台日志管理系统
Copyright (C) 2026  HamLog Team

本程序是自由软件：你可以再发布本软件和/或修改本软件，
只要你遵守著作权法规和 GNU 通用公共许可证（GPL）第 3 版。
本程序是希望它能有用而发布的，但没有任何担保或特定用途适用性的隐含担保；
甚至没有适销性。详情请参阅 GNU 通用公共许可证。
```

---

## 📦 根目录文件说明

| 文件 | 说明 |
|------|------|
| `update.txt` | 自动更新配置文件，包含最新版本号、安装包下载链接和更新日志链接 |
| `changelog_Release_xxx.x.docx` | 版本更新日志文档（Word 格式） |

> 这两个文件由更新模块自动获取，用于检测新版本和展示更新内容。

---

## 🙏 致谢

特别感谢以下人员与组织对 HamLog 开发的支持：

- **BA8AQA** — 项目发起人与核心开发
- **BG5JQN** — 旧版本(重构前实验版本)核心开发
- 所有提交 Issue 和反馈的爱好者
- 开源社区提供的优秀工具与库

---

## 📬 联系我们

| 平台 | 链接 |
|------|------|
| GitHub | [ARPRC-BA8AQA/HamLog](https://github.com/ARPRC-BA8AQA/HamLog) |
| Bilibili | [@C盘研究所-中国_BA8AQA](https://space.bilibili.com/1297822096?) |

---

<p align="center">
  <b>73 De BA8AQA 🎙️</b><br>
  <i>愿电波永不消逝，友谊长存空中</i>
</p>
