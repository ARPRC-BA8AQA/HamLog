# HamLog

> ⚠️ **本分支(Dev)为重构 Beta 分支,正在向 R2.0.0 前后端分离 Web 版重构,后续将合并进主分支。**
>
> **本分支不保证任何稳定性与安全性!** 接口、数据结构、目录布局、配置项均可能随重构频繁变更,请勿用于生产环境。如需稳定版本,请使用 [main 分支](https://github.com/ARPRC-BA8AQA/HamLog/tree/main) 或 [Release_1.0.0](https://github.com/ARPRC-BA8AQA/HamLog/releases/tag/Release_1.0.0)。

---

## 项目简介

HamLog 是面向业余无线电爱好者的通联日志管理系统。R2.0.0 版本将原桌面单机程序重构为 **前后端分离的 Web 应用**:

- **后端**:Flask,提供 RESTful API(统一 POST + 标准 JSON + 状态码)
- **前端**:`front/` 目录,支持 HTML / CSS / JS / PY / PHP 等网页文件
- **可选 JWT 认证**:关闭认证时默认不鉴权
- **插件系统**:插件中心 + 源管理 + 评级系统 + 沙箱隔离
- **QSL 卡片设计器**:类 PPT 可视化设计 + 智能填充 + 私有/公共格式导出
- **安全加固**:CORS / CSRF / SQL 参数化查询 / 可选 AES-256 加密
- **统一日志**:单文件记录,可配置等级,崩溃日志必保
- **授时同步**:自动提权连接标准授时服务器

## 重要文档

本分支的完整重构文档位于 [`docs/`](./docs) 目录:

| 文档 | 说明 |
|------|------|
| 📘 [项目文档](./docs/PROJECT.md) | 功能、架构、认证模型、安全策略、插件、QSL 设计器、快速开始 |
| 📗 [技术文档](./docs/TECHNICAL.md) | 分层架构、接口规范、数据结构、日志、授时、插件引擎、QSL 引擎、迁移约束 |
| 📙 [项目结构](./docs/STRUCTURE.md) | 顶层/后端/前端/插件/data/logs/config 完整目录布局 |
| 📕 [API 接口文档](./docs/API.md) | 统一 POST + 标准 JSON 响应,60+ 接口,状态码规范,速查表 |
| 📓 [插件开发规范](./docs/PLUGIN_DEV.md) | 权限模型、沙箱、语法审核、API、评级系统、发布流程 |
| 📒 [QSL 格式规范](./docs/QSL_FORMAT.md) | `.hamqsl` 私有格式、版本兼容、数据绑定、导出规范 |

## 分支说明

| 分支 | 状态 | 用途 |
|------|------|------|
| `main` | ✅ 稳定 | 生产发布分支 |
| `Dev` | ⚠️ 不稳定 | R2.0.0 Web 重构开发分支(当前分支) |
| `Public` | — | 公共镜像分支 |
| `docs/refactor-r2` | 📄 文档 | 重构文档工作分支 |

## 当前重构进度

- [x] 重构文档体系(项目 / 技术 / 结构 / API / 插件 / QSL 格式)
- [x] QRZ.com 爬虫参考实现([qrz_scraper.py](./qrz_scraper.py))
- [ ] 后端骨架代码(`backend/core/` + `backend/api/`)
- [ ] 前端基础框架(`front/`)
- [ ] 插件引擎与插件中心
- [ ] QSL 卡片设计器
- [ ] 数据库迁移与业务模块
- [ ] 测试与部署

## 协议

详见 [LICENSE](./LICENSE)。

## Windows 快速开始

要求 Windows 10/11 和 Python 3.9 或更高版本。双击 `start_windows.bat` 会自动创建 `.venv`、安装依赖并启动服务；也可以在 PowerShell 中运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start_windows.ps1
```

启动后打开 `http://127.0.0.1:5000`。

## 敏感配置

Windows 生产环境请通过环境变量设置 AES-256 密钥，不要把密钥写入仓库或配置文件。PowerShell 当前会话：

```powershell
$env:HAMLOG_AES_KEY = python -c "import secrets; print(secrets.token_hex(32))"
```

持久写入当前 Windows 用户环境变量：

```powershell
$key = python -c "import secrets; print(secrets.token_hex(32))"
[Environment]::SetEnvironmentVariable("HAMLOG_AES_KEY", $key, "User")
```

设置后需要重新启动 HamLog。`HAMLOG_AES_KEY` 支持 64 位十六进制字符串，也支持长度为 32 字节的原始字符串。也可以使用 `HAMLOG_AES_KEY_B64` 配置 32 字节密钥的 URL-safe Base64 值。未配置环境变量时 AES 功能拒绝开启，主密钥不会写入本地文件。

## 反馈

- 提交 Issue:[github.com/ARPRC-BA8AQA/HamLog/issues](https://github.com/ARPRC-BA8AQA/HamLog/issues)
- 贡献代码:请基于 `Dev` 分支提交 Pull Request
