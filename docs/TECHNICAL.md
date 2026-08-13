# HamLog Web 技术文档

> 业余无线电台日志管理系统 · 前后端分离重构版 · 技术实现文档
> 版本:Release 2.0.0 ｜ 协议:GPL-3.0
> 仓库:https://github.com/ARPRC-BA8AQA/HamLog
> 配套:[PROJECT.md](PROJECT.md) / [STRUCTURE.md](STRUCTURE.md) / [API.md](API.md)

---

## 1. 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | Flask 2.x | 应用工厂 + 蓝图,轻量灵活 |
| ORM | SQLAlchemy | 参数化查询、模型管理(防 SQL 注入) |
| 认证 | Flask-JWT-Extended(PyJWT) | 可选启用,access/refresh 双 Token |
| CORS | flask-cors | 可配置来源 |
| 数据库 | SQLite3 | 单文件 `data/Log.db`,标准库 |
| 加密 | cryptography(AES-256-GCM) | 敏感信息可选加密 |
| 授时 | ntplib + 系统命令 | NTP 校时 + 自动提权 |
| 日志 | logging + faulthandler + sys.excepthook | 单文件统一,崩溃必保 |
| 前端 | 原生 HTML/CSS/JS | 静态资源放 `front/`,无强制框架;可选 php |
| PDF 生成 | 前端 pdf-lib / 后端 reportlab | QSL 打印 PDF |
| 画布 | 原生 Canvas API(可选 fabric.js) | QSL 设计器 |
| 打包 | PyInstaller + Inno Setup | 后端 exe + 前端内嵌 |

---

## 2. 架构总览

### 2.1 分层
```
┌──────────────────── front (静态前端 SPA) ────────────────────┐
│ index.html / pages/*.js / qsl_designer/                      │
│  └─ js/core/api.js : 统一 POST + JWT/CSRF 携带 + 错误处理     │
├──────────────────────────────────────────────────────────────┤
│  backend/api/*  (Flask 蓝图, 全部 POST)                       │
│  入参校验 → 装饰器(认证/CSRF/日志) → 业务 → 标准JSON响应       │
├──────────────────────────────────────────────────────────────┤
│  backend/core  响应/认证/日志/加密/授时/异常/安全(基础设施)    │
├──────────────────────────┬───────────────────────────────────┤
│  backend/services(纯逻辑) │  backend/plugins(插件引擎,沙箱)   │
├──────────────────────────┴───────────────────────────────────┤
│  数据层:SQLite(参数化) + AES-256(可选)                       │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 设计原则
- **统一日志入口**:全应用只通过 `core/logger.py` 记录
- **参数化查询**:禁止拼接 SQL,统一走 SQLAlchemy 或 `?` 占位
- **可选认证**:认证开关在配置;关闭即全权,业务无感
- **插件隔离**:插件异常不可上抛到业务层
- **标准响应**:所有出口统一 `ok(data)` / `fail(code, msg)`

---

## 3. 标准响应与状态码

### 3.1 响应结构(`core/response.py`)
```python
def ok(data=None, msg="ok"):
    return {"code": 200, "msg": msg, "data": data}

def fail(code, msg, data=None):
    return {"code": code, "msg": msg, "data": data}
```

### 3.2 状态码约定
| code | 含义 |
|------|------|
| 200 | 成功 |
| 400 | 参数错误/校验失败 |
| 401 | 未认证/Token 失效 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 冲突(如重复) |
| 500 | 服务器内部错误 |
| 503 | 依赖不可用(如 TQSL 未安装) |

### 3.3 请求约定
- 全部 **POST**,`Content-Type: application/json`,body 为 JSON
- 认证开启时头携带 `Authorization: Bearer <access_token>`
- CSRF 开启时变更类请求头携带 `X-CSRF-Token: <token>`
- 统一前缀 `/api/`

---

## 4. 认证与权限(`core/auth.py`)

### 4.1 配置开关
```yaml
auth:
  enabled: false      # 关闭 → 不降权(全权);开启 → 需登录
  jwt_secret: "..."   # 首次开启自动生成
  access_token_expires: 7200
  refresh_token_expires: 604800
```

### 4.2 流程
1. 前端 `POST /api/auth/login` {username, password}
2. 校验通过 → 签发 access_token(短)+ refresh_token(长)
3. 受保护接口经 `@require_auth` 装饰器校验
4. access 过期 → `POST /api/auth/refresh` 用 refresh 换新

### 4.3 装饰器(`core/decorators.py`)
```python
@require_auth         # 认证关闭时自动放行;开启时校验 Token
@require_role("admin")# 角色校验;认证关闭时默认 admin
@post_only            # 仅允许 POST
def log_list():
    ...
```

### 4.4 用户表
```sql
CREATE TABLE users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,   -- werkzeug generate_password_hash
  role TEXT DEFAULT 'admin',     -- admin / user
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```
首次启动若表空且认证开启,引导创建管理员账户。密码使用 PBKDF2 哈希存储,不存明文。

---

## 5. 安全设计(`core/security.py`)

### 5.1 CORS
```python
CORS(app, resources={r"/api/*": {"origins": config.cors_origins}})
```
默认仅允许本机来源,可在配置扩展。

### 5.2 CSRF
- 每个会话签发 CSRF Token,前端通过 `POST /api/auth/csrf` 获取
- 变更类接口校验 `X-CSRF-Token` 头
- JWT 走 Authorization 头本身免疫 CSRF,CSRF 作为纵深防御(尤其兼容 cookie 模式)

### 5.3 SQL 注入防护
- 全部使用 SQLAlchemy ORM / Core,或原生 `cursor.execute(sql, params)` 参数化
- **禁止**任何 `f"...{var}..."` / `%` 拼接 SQL;代码审查强约束
- 动态列名走白名单校验

### 5.4 AES-256 加密(`core/crypto.py`)
- 用户手动开启(`config.security.aes_enabled`)
- 算法:**AES-256-GCM**(带认证标签,防篡改)
- 密钥:首次开启生成并保存到 `data/secret.key`(文件权限 600),可由用户口令派生(PBKDF2)再加密保护
- 用途:QRZ 登录凭据、用户邮箱/地址等敏感字段
```python
class Crypto:
    def encrypt(self, plaintext: str) -> str   # 返回 base64(nonce+ct+tag)
    def decrypt(self, token: str) -> str
```
- 数据库敏感字段以密文存储,读取时按开关解密;关闭加密时明文读写,迁移时提供一键加密/解密

### 5.5 输入校验
- 每个接口入参用 schema 校验(类型、长度、白名单),非法直接 400

---

## 6. 统一日志系统(`core/logger.py`)

> **单一文件**统一记录全应用日志,是唯一日志入口。

### 6.1 能力
- 分级:`DEBUG / INFO / WARNING / ERROR / CRITICAL`,用户在配置中选择
- 双写:文件(`logs/app.log`,按天轮转,保留 30 天)+ 控制台
- 崩溃日志**必保**:写入独立 `logs/crash.log`

### 6.2 崩溃保障机制
```python
import faulthandler, sys, atexit, threading

# 1. 段错误/死锁堆栈
faulthandler.enable(file=open("logs/crash.log","a"), all_threads=True)

# 2. 未捕获异常
def _excepthook(exc_type, exc, tb):
    logger.critical("UNCAUGHT", exc_info=(exc_type, exc, tb))
    _flush_crash()
sys.excepthook = _excepthook

# 3. 线程未捕获异常
threading.excepthook = lambda args: logger.critical("THREAD_CRASH", exc_info=args.exc_info)

# 4. 退出前强制 flush
atexit.register(_flush_all)
```
- 日志 handler 用 `BufferingHandler` + 退出/异常 flush,保证崩溃前已缓冲日志落盘
- 插件审核与运行日志单独写 `logs/plugin_audit.log`

### 6.3 接口
```python
log = get_logger()
log.info("source", "message")
log.error("qrz", "查询失败", exc_info=True)
```

---

## 7. 授时同步(`core/time_sync.py`)

### 7.1 流程
1. 用 `ntplib` 查询 NTP 服务器(默认 `ntp.ntsc.ac.cn`、`pool.ntp.org`),取偏移量
2. 偏移超阈值 → 校正系统时间
3. **自动获取管理员权限**:
   - Windows:检测非管理员 → 通过 `ShellExecuteW(runas)` 触发 UAC 提权,再以 `w32tm /resync` 或 `Set-Date` 校时
   - Linux:`sudo timedatectl set-ntp true` / `date -s`
4. 校时结果记入日志

### 7.2 触发时机
- 后端启动时(可配置)
- 用户在系统页手动触发 `POST /api/system/sync_time`
- 定期(可选)

### 7.3 用途
- 保证日志时间戳、UTC 转换、LoTW 上传时间准确(LoTW 对时间敏感)

---

## 8. 插件系统(`backend/plugins/`)

### 8.1 插件规范
- 插件(英文 **plugin**)以**英文文件夹名**为 ID,内含 `manifest.json` + 一个或多个 `.py` 文件
- `manifest.json`:
```json
{
  "id": "dxcc_helper",
  "name": "DXCC 助手",
  "version": "1.0.0",
  "author": "BA8AQA",
  "description": "...",
  "entry": "main.py",
  "min_app_version": "2.0.0",
  "api_version": "1",
  "permissions": ["log.read"],
  "sensitive_permissions": []
}
```

### 8.2 权限模型(`permissions.py`)
- 普通权限:`log.read`、`settings.read`
- 敏感权限(需用户确认,醒目提醒):`file.write`、`network`、`system`、`db.raw`、`aes.decrypt`
- 默认 `allow_sensitive: false`,敏感权限插件需用户在插件中心显式授权

### 8.3 加载与语法审核(`auditor.py`)
```python
def audit(plugin_dir) -> (ok: bool, errors: list):
    for py in plugin_dir.glob("*.py"):
        src = py.read_text()
        ast.parse(src)            # 语法树解析
        py_compile.compile(str(py), doraise=True)  # 编译
    # 失败 → 不加载,返回 errors 给前端提示"语法错误,不允许加载"
```
- 审核不通过的插件**不允许加载**,在插件中心显示语法错误详情
- 审核结果写入 `logs/plugin_audit.log`

### 8.4 隔离执行(`sandbox.py`)
- 插件在**子进程**中运行(`multiprocessing`),主进程不受影响
- 超时限制 + 内存守护;插件抛异常被捕获并记录,不上抛
- 插件通过 IPC(管道/队列)调用 `PluginContext` API,不直接持有主进程对象
- 业务系统与插件完全隔离:**插件崩溃不影响全局**

### 8.5 插件 API(`api.py`)
```python
class PluginContext:
    def get_log(self, log_id) -> dict          # 受权限控制
    def search_logs(self, keyword) -> list
    def get_setting(self, key) -> str
    def log_info(self, msg)                     # 走统一日志
    def http_get(self, url) -> str              # 需 network 权限
    # ... 详见 PLUGIN_DEV.md
```
- 所有 API 调用受 manifest 声明权限校验,越权调用拒绝并记录

### 8.6 插件中心(`sources.py` + `plugin_api.py`)
- 插件源:URL,返回插件清单 JSON;内置官方默认源
- 用户可添加/删除源
- 支持:列表、安装、更新、启用/停用、卸载、查看权限
- 敏感权限操作前端醒目提醒用户确认

---

## 9. QSL 卡片设计器

### 9.1 前端设计器(`front/qsl_designer/`)
- **类 PPT 网页画布**:Canvas,图层化(增删/排序/锁定/显隐)
- **基础图形**:矩形、圆、线条、文字、图片、二维码
- **背景图**:上传或内置图库(`assets/backgrounds/`)
- **拖拽/对齐/吸附/缩放/旋转**
- **智能一键填充**:元素绑定数据类别(占位符),如 `{callsign}`、`{date}`、`{freq}`、`{rst}`、`{my_qth}`;填充时按当前通联记录一键替换

### 9.2 数据绑定(`binding.js`)
```js
// 占位符 → 数据类别映射
{ "{callsign}": "log.callsign", "{date}": "log.date", "{my_call}": "station.my_callsign", ... }
// 一键填充:遍历元素,按绑定替换占位符为实际值
```

### 9.3 私有格式 `.hamqsl`(`services/qsl_design_service.py`)
- JSON 封装,带 `schema_version`
```json
{
  "schema_version": "1.0",
  "canvas": {"width": 148, "height": 105, "unit": "mm"},
  "background": {"type": "image", "ref": "asset_id or dataurl"},
  "elements": [
    {"id": "...", "type": "text", "x": 10, "y": 20, "w": 80, "h": 12,
     "text": "{callsign}", "binding": "log.callsign", "style": {...}}
  ],
  "assets": {...}
}
```
- **版本兼容**:读取时按 `schema_version` 走迁移器;未知字段忽略;**能读多少读多少**,不因新字段缺失而失败
- **跨设备导入**:导出 `.hamqsl` 文件 → 其他设备导入继续编辑
- 资源(背景图)以 dataurl 内嵌或 asset_id 引用,导入时自动还原

### 9.4 公共格式导出
- **PDF**:`front/vendor/pdf-lib.min.js` 按画布尺寸生成,支持自定义纸张大小
- **PNG**:Canvas `toDataURL`
- 若公共格式能还原原始数据(PDF 内嵌 `.hamqsl` 元数据),亦可回导

### 9.5 自动保存(`autosave.js`)
- 前端 dirty 标志 + 每 **10s** 检测,有更新则 `POST /api/qsl/autosave`
- 后端落盘到 `data/qsl/projects/<id>.hamqsl`

### 9.6 打印
- 一键生成打印 PDF,自定义尺寸(DPI/纸张/出血)

---

## 10. 数据库设计

### 10.1 主表(沿用并优化)
```sql
-- log 表(参数化访问)
CREATE TABLE log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  Callsign TEXT NOT NULL,
  Freq TEXT, Year INTEGER, Month INTEGER, Day INTEGER, Time TEXT,
  Mode TEXT, Power_self TEXT, Power_side TEXT,
  Rst_self TEXT, Rst_side TEXT, QTH TEXT, Device TEXT,
  QSL_RX TEXT, QSL_SEND TEXT, Remarks TEXT,
  CreateTime TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 10.2 settings(KV,沿用)
```sql
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
```

### 10.3 qsl_projects
```sql
CREATE TABLE qsl_projects(
  id TEXT PRIMARY KEY, name TEXT, schema_version TEXT,
  updated_at TEXT, content TEXT  -- .hamqsl JSON
);
```

### 10.4 app_logs(日志缓存)
```sql
CREATE TABLE app_logs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT, level TEXT, source TEXT, message TEXT
);
CREATE INDEX idx_logs_time ON app_logs(timestamp);
CREATE INDEX idx_logs_level ON app_logs(level);
```

### 10.5 users(见 §4.4)

### 10.6 数据兼容策略
- 每张表带 `schema_version` 或通过迁移脚本管理
- 读取旧数据时:能读多少读多少,缺失字段用默认值,不报错
- 数据库启动迁移:`flask db migrate/upgrade`(Alembic)

---

## 11. 核心业务实现

### 11.1 QRZ 查询(`services/qrz_client.py`)
- 由 [qrz_scraper.py](file:///workspace/qrz_scraper.py) 重构为纯逻辑类 `QRZClient`
- 处理反爬:UA 伪装、nojs token 登录、Bio Base64 解码、302 检测、3~6s 随机延迟
- 游客/登录双模式;登录凭据可选 AES 加密存储
- 通过 `proxy_manager` 等价机制走代理(走 `requests` proxies,显式传入)

### 11.2 ADIF 导出(`services/adif_exporter.py`)
- 频率→波段、模式归一化、ADIF 头/记录生成
- 参数化查询日志,导出 `.adi`

### 11.3 LoTW 上传(`services/tqsl_service.py` + `lotw_service.py`)
- TQSL 跨平台查找(默认路径/PATH/多驱动器搜索)
- `tqsl` 签名 ADIF → `.tq8` → HTTP POST 上传 → 解析结果

### 11.4 时区
- 用户录入本地时间,存储/导出用 UTC;前端预览 UTC

---

## 12. 前端实现要点

### 12.1 API 客户端(`front/js/core/api.js`)
```js
async function post(path, body) {
  const headers = {"Content-Type": "application/json"};
  if (token) headers["Authorization"] = "Bearer " + token;
  if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const res = await fetch("/api" + path, {
    method: "POST", headers, body: JSON.stringify(body || {})
  });
  const json = await res.json();
  if (json.code === 401) { /* 跳登录/刷新 */ }
  return json;
}
```
- 统一错误处理、Token 携带、CSRF 携带、loading 态

### 12.2 主题与字体
- CSS 变量切换深/浅;字体/字号可配置(沿用桌面版理念)

### 12.3 QSL 设计器
- 见 §9,Canvas + 图层 + 数据绑定

---

## 13. 异常处理(`core/errors.py`)
- 全局注册 HTTP 错误与未捕获异常处理器,统一返回标准 JSON
- 业务异常自定义 `AppError(code, msg)`
- 崩溃走日志系统(§6)确保记录

---

## 14. 配置管理(`config.py` + `config.yaml`)
- 首次启动自动生成默认 `config.yaml`
- 热加载关键项(日志等级、CORS 等)
- 敏感项(jwt_secret、aes key)单独保管,不进版本库

---

## 15. 测试

| 模块 | 测试点 |
|------|--------|
| database | CRUD/搜索/参数化/迁移兼容 |
| auth | 开关切换、Token 签发/校验/过期/刷新、权限 |
| security | CSRF、CORS、SQL 注入用例、AES 加解密 |
| logger | 分级、崩溃钩子、轮转 |
| plugins | 语法审核(合法/非法)、权限校验、沙箱隔离、崩溃不上抛 |
| qsl | 私有格式读写、版本兼容(旧 schema 能读)、导出 PDF |
| qrz | mock HTML 解析、反爬重定向、Bio 解码 |

---

## 16. 重构迁移要点(从桌面版到 Web 版)
1. `AutoDeal.Database/SettingsManager` → `core/database.py` + ORM 模型(SQLAlchemy,参数化)
2. `QRZ_Lookup_Dialog` → `services/qrz_client.py`(纯逻辑)+ `api/qrz_api.py`
3. `ADIF/LoTW` → `services/adif_exporter.py` / `tqsl_service.py` / `lotw_service.py`
4. `app_logger` → `core/logger.py`(增强崩溃保障)
5. `proxy_manager` → `core` 内代理配置,显式传入 requests/urllib
6. `update_module` → `services/update_service.py` + `api/update_api.py`
7. 桌面 GUI → `front/` 静态网页
8. QSL 卡片设计器、插件系统、AES、授时为全新模块

---

## 17. 已知约束与后续
- LoTW 上传仍依赖 TQSL(用户自装)
- 授时提权在无 GUI 的纯服务端场景需配合系统策略
- 插件沙箱采用子进程,跨平台资源限制在 Windows 上能力有限(以超时为主)
- 前端默认原生 JS,后续可平滑引入框架(不强制)

---

*本文档随重构进度持续更新。*
