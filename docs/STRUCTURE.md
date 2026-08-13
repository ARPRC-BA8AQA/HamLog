# HamLog Web 项目结构

> HamLog Web · 前后端分离重构版 · Release 2.0.0
> 仓库:https://github.com/ARPRC-BA8AQA/HamLog
> 架构:Flask 后端 API + 静态前端(front 目录)

---

## 1. 顶层结构

```
HamLog/
├── README.md                      # 项目说明
├── LICENSE                        # GPL-3.0
├── requirements.txt               # Python 依赖
├── config.yaml                    # 主配置(运行时配置,首次启动自动生成)
├── run.py                         # 启动入口(Flask app + 初始化)
├── docs/                          # 文档目录
│   ├── PROJECT.md                 # 项目文档
│   ├── TECHNICAL.md               # 技术文档
│   ├── STRUCTURE.md               # 本文档(项目结构)
│   ├── API.md                     # API 接口文档(独立)
│   ├── PLUGIN_DEV.md              # 插件开发规范
│   └── QSL_FORMAT.md              # QSL 卡片私有格式规范
├── backend/                       # 后端(Flask)
├── front/                         # 前端(静态网页)
├── plugins/                       # 用户插件目录(运行时创建)
├── official_plugins/              # 官方默认插件源
├── data/                          # 数据与备份
├── logs/                          # 运行日志
└── installer/                     # 打包脚本
```

---

## 2. backend/ 后端目录

```
backend/
├── __init__.py
├── app.py                         # Flask 应用工厂(create_app)
├── config.py                      # 配置加载与校验(读 config.yaml)
├── extensions.py                  # 扩展实例(db/jwt/cors/migrate)
│
├── core/                          # 核心基础层(被所有模块依赖)
│   ├── __init__.py
│   ├── database.py                # 数据库连接 + 参数化查询封装
│   ├── models.py                  # ORM 模型(log/settings/users/...)
│   ├── response.py                # 标准JSON响应(code/msg/data)
│   ├── auth.py                    # JWT 签发/校验/权限装饰器
│   ├── decorators.py              # @require_auth / @require_role / @post_only
│   ├── logger.py                  # 【统一日志】单一文件,分级+崩溃必记
│   ├── crypto.py                  # AES-256-GCM 加解密(敏感信息)
│   ├── time_sync.py               # NTP 授时 + 自动提权
│   ├── errors.py                  # 全局异常处理 → 标准JSON
│   └── security.py                # CORS/CSRF/参数白名单
│
├── api/                           # API 蓝图(全部 POST 请求)
│   ├── __init__.py                # 蓝图注册
│   ├── auth_api.py                # 认证:登录/登出/刷新/CSRF令牌
│   ├── log_api.py                 # QSO 日志 CRUD/搜索/统计
│   ├── settings_api.py            # 本台与系统设置
│   ├── adif_api.py                # ADIF 导出
│   ├── lotw_api.py                # LoTW 上传(TQSL 签名+HTTP)
│   ├── qrz_api.py                 # QRZ.com 呼号查询
│   ├── qsl_api.py                 # QSL 卡片设计(保存/导出/导入/列表)
│   ├── plugin_api.py              # 插件中心(源/安装/启停/调用)
│   ├── intertime_api.py           # 网络延迟检测
│   ├── update_api.py              # 在线更新
│   └── system_api.py              # 系统信息/授时/加密开关
│
├── plugins/                       # 插件子系统(后端引擎,非用户插件)
│   ├── __init__.py
│   ├── manager.py                 # 插件管理器(加载/卸载/生命周期)
│   ├── sandbox.py                 # 插件隔离执行(子进程+超时+资源限制)
│   ├── auditor.py                 # 语法审核(ast/py_compile)
│   ├── api.py                     # 插件可用 API 接口(PluginContext)
│   ├── sources.py                 # 插件源管理(官方+用户自定义)
│   └── permissions.py             # 权限声明与敏感权限校验
│
├── services/                      # 业务服务层(纯逻辑,无 Flask 依赖)
│   ├── __init__.py
│   ├── qrz_client.py              # QRZ 爬虫(由 qrz_scraper.py 重构)
│   ├── adif_exporter.py           # ADIF 导出逻辑
│   ├── tqsl_service.py            # TQSL 查找与签名
│   ├── qsl_design_service.py      # QSL 设计数据/版本兼容
│   ├── lotw_service.py            # LoTW 上传
│   └── update_service.py          # 更新检查与下载
│
└── tests/                         # 测试
    ├── test_database.py
    ├── test_auth.py
    ├── test_plugins.py
    ├── test_qsl_compat.py
    └── test_qrz.py
```

---

## 3. front/ 前端目录

```
front/
├── index.html                     # 单页入口
├── favicon.ico
├── css/
│   ├── base.css                   # 全局样式
│   ├── theme.css                  # 深色/浅色主题变量
│   └── components.css             # 组件样式
├── js/
│   ├── core/
│   │   ├── api.js                 # API 客户端(POST/统一错误处理/JWT携带)
│   │   ├── auth.js                # 登录态/Token 管理/CSRF
│   │   ├── store.js               # 前端状态管理
│   │   └── utils.js               # 工具函数
│   ├── pages/                     # 各功能页模块
│   │   ├── logs.js                # 日志页
│   │   ├── settings.js            # 设置页
│   │   ├── qrz.js                 # QRZ 查询页
│   │   ├── adif.js                # ADIF 导出页
│   │   ├── lotw.js                # LoTW 上传页
│   │   ├── intertime.js           # 延迟监测页
│   │   └── plugins.js             # 插件中心页
│   └── components/                # 可复用组件
│       ├── table.js
│       ├── dialog.js
│       └── toast.js
├── qsl_designer/                  # QSL 卡片设计器(类PPT)
│   ├── designer.html              # 设计器入口
│   ├── designer.js                # 设计器主逻辑(画布/图层/吸附)
│   ├── elements.js                # 图形元素(矩形/圆/文字/图片/QR码)
│   ├── binding.js                 # 数据绑定(智能一键填充)
│   ├── autosave.js                # 10s 自动保存
│   ├── exporter.js                # 导出(私有/公共/PDF)
│   └── designer.css
├── assets/                        # 静态资源
│   ├── fonts/
│   ├── icons/
│   └── backgrounds/              # QSL 背景图库
└── vendor/                        # 第三方库(本地托管)
    ├── pdf-lib.min.js            # PDF 生成
    └── fabric.min.js             # 画布(可选)
```

> 说明:front 目录支持 html/css/js,也允许 php(若部署在支持 PHP 的服务器,作为可选服务端增强)。核心前端为纯静态,由 Flask 直接托管或独立 Nginx 托管。

---

## 4. 用户插件目录

插件(英文名:**plugin**)以英文文件夹名命名,内含一个或多个 `.py` 文件 + `manifest.json`。

```
plugins/                           # 用户插件目录(运行时创建)
├── example_plugin/                # 插件示例(英文名命名)
│   ├── manifest.json              # 元数据:名称/版本/作者/权限声明/入口
│   ├── main.py                    # 插件入口(必须)
│   └── helpers.py                 # 其余 py 文件(可选)
└── another_plugin/
    ├── manifest.json
    └── main.py

official_plugins/                  # 官方默认源(随仓库分发)
├── dxcc_helper/
│   ├── manifest.json
│   └── main.py
└── README.md                      # 官方源索引
```

### manifest.json 结构
```json
{
  "id": "example_plugin",
  "name": "示例插件",
  "version": "1.0.0",
  "author": "BA8AQA",
  "description": "插件说明",
  "entry": "main.py",
  "min_app_version": "2.0.0",
  "permissions": ["log.read", "settings.read"],
  "sensitive_permissions": [],
  "api_version": "1"
}
```

---

## 5. data/ 与 logs/

```
data/
├── Log.db                         # 主数据库
├── logs_cache.db                  # 日志缓存(SQLite)
├── qsl/                           # QSL 设计文件
│   ├── projects/                  # 私有格式(.hamqsl)
│   └── exports/                   # 导出的 PDF/图片
├── backups/                       # 自动备份
└── secret.key                     # AES 密钥(加密功能开启后生成,勿提交)

logs/
├── app.log                        # 运行日志(按天轮转)
├── crash.log                      # 崩溃日志(独立,必保)
└── plugin_audit.log               # 插件审核与运行日志
```

---

## 6. 配置文件 config.yaml

首次启动由 `backend/config.py` 自动生成,关键字段:

```yaml
server:
  host: "127.0.0.1"
  port: 5000
auth:
  enabled: false              # 是否启用认证;关闭则不降权(默认全权)
  jwt_secret: ""              # 启用时自动生成
  access_token_expires: 7200  # 秒
security:
  cors_origins: ["http://127.0.0.1:5000"]
  csrf_enabled: true
  aes_enabled: false          # 敏感信息加密(用户手动开启)
logging:
  level: "INFO"               # DEBUG/INFO/WARNING/ERROR/CRITICAL
  keep_days: 30
time_sync:
  enabled: true
  ntp_servers: ["ntp.ntsc.ac.cn", "pool.ntp.org"]
  auto_elevate: true          # 自动获取管理员权限
plugins:
  enabled: true
  sources:
    - "official"              # 官方默认源
  allow_sensitive: false      # 是否允许插件敏感权限(默认否,需用户确认)
qsl:
  autosave_interval: 10       # 秒
```

---

## 7. 启动与部署

### 开发启动
```bash
pip install -r requirements.txt
python run.py
# 默认 http://127.0.0.1:5000,前端由 Flask 托管
```

### 生产部署
- 方式一(单机):`run.py` 一体化,Flask 托管 front 静态文件
- 方式二(分离):Nginx 托管 front,Flask 仅提供 `/api/*`,通过反代
- 打包:`installer/` 提供 PyInstaller 后端打包 + 前端静态资源内嵌

---

## 8. 模块依赖关系

```
┌─────────────── front (静态前端) ───────────────┐
│   index.html + js/core/api.js (POST + JWT)      │
└───────────────────────┬────────────────────────┘
                        │ HTTP POST /api/* (JSON)
┌───────────────────────▼────────────────────────┐
│  backend/api/*  (Flask 蓝图, 全部 POST)         │
│  auth / log / qrz / qsl / plugin / ...          │
├─────────────────────────────────────────────────┤
│  backend/core (响应/认证/日志/加密/授时/异常)    │
├─────────────────────┬───────────────────────────┤
│  backend/services   │  backend/plugins          │
│  (业务逻辑)          │  (插件引擎,沙箱隔离)      │
├─────────────────────┴───────────────────────────┤
│  数据层:SQLite(参数化查询) + AES-256(可选)    │
└─────────────────────────────────────────────────┘
```

- `core/logger.py` 被所有模块引用(唯一日志入口)
- `plugins/sandbox.py` 隔离插件,插件异常不影响业务系统
- `services` 纯逻辑可被 API 与插件共享调用
