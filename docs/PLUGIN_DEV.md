# HamLog 插件开发规范

> HamLog Web · 插件(Plugin)开发与接入规范
> 版本:Release 2.0.0 ｜ 插件 API 版本:1
> 仓库:https://github.com/ARPRC-BA8AQA/HamLog
> 配套:[TECHNICAL.md §8](TECHNICAL.md) / [API.md §8](API.md)

> 插件英文名统一为 **plugin**。下文"插件"即指 plugin。

---

## 1. 总则

### 1.1 设计目标
- 让用户与第三方能够扩展 HamLog 功能,而不修改主程序
- **插件与业务系统隔离**:插件崩溃、报错、卡死均不可影响主程序与数据库
- **安全可控**:权限声明 + 语法审核 + 沙箱执行 + 敏感权限用户确认
- **规范统一**:统一的 manifest、入口、API、生命周期

### 1.2 适用范围
- 本规范适用于 HamLog Web(Release 2.0.0 及以上)
- 插件 API 版本由 manifest 中 `api_version` 声明,当前为 `"1"`
- 主程序按 `api_version` 选择对应的兼容层加载

---

## 2. 插件目录结构

### 2.1 命名规则
- 插件以**英文文件夹名**作为唯一 ID(`id`)
- 文件夹名只能包含:小写字母 `a-z`、数字 `0-9`、下划线 `_`、连字符 `-`
- 必须以字母开头,长度 3~40
- 示例:`dxcc_helper`、`qsl_print_helper`、`lotw-stats`

> **禁止**:中文文件夹名、空格、大写字母、特殊字符。不合规的目录会被跳过加载并在日志中提示。

### 2.2 目录结构
```
plugins/                           # 用户插件目录(运行时创建)
└── dxcc_helper/                   # 插件 ID = 文件夹名
    ├── manifest.json              # 元数据(必须)
    ├── main.py                    # 入口文件(必须,文件名由 manifest.entry 指定)
    ├── helpers.py                 # 其余 py 文件(可选,可多个)
    └── assets/                    # 插件自带资源(可选)
        └── flag.png
```

### 2.3 入口文件
- 由 `manifest.json` 的 `entry` 字段指定,通常为 `main.py`
- 入口文件必须定义一个 `Plugin` 类(见 §4)
- 其余 `.py` 文件由入口文件自行 import

---

## 3. manifest.json 规范

### 3.1 完整字段
```json
{
  "id": "dxcc_helper",
  "name": "DXCC 助手",
  "version": "1.0.0",
  "author": "BA8AQA",
  "description": "根据呼号前缀查询 DXCC 实体、ITU/CQ 分区",
  "entry": "main.py",
  "min_app_version": "2.0.0",
  "api_version": "1",
  "permissions": ["log.read", "settings.read"],
  "sensitive_permissions": ["network"],
  "homepage": "https://github.com/ARPRC-BA8AQA/dxcc_helper",
  "license": "MIT"
}
```

### 3.2 字段说明
| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `id` | 是 | string | 插件 ID,必须与文件夹名一致 |
| `name` | 是 | string | 显示名称(可中文) |
| `version` | 是 | string | 语义化版本 `MAJOR.MINOR.PATCH` |
| `author` | 是 | string | 作者 |
| `description` | 否 | string | 功能描述 |
| `entry` | 是 | string | 入口 py 文件名(相对插件目录) |
| `min_app_version` | 是 | string | 最低兼容的主程序版本 |
| `api_version` | 是 | string | 使用的插件 API 版本,当前 `"1"` |
| `permissions` | 是 | array | 普通权限列表(见 §5) |
| `sensitive_permissions` | 否 | array | 敏感权限列表(见 §5),需用户确认 |
| `homepage` | 否 | string | 主页 |
| `license` | 否 | string | 许可证 |

### 3.3 校验规则
- `id` 必须与文件夹名一致,否则不加载
- `entry` 指向的文件必须存在
- `version` 必须符合语义化版本格式
- `api_version` 主程序不识别时降级提示"API 版本不兼容"
- `min_app_version` 高于当前主程序版本时提示"需要更高版本 HamLog"

---

## 4. 入口文件规范

### 4.1 Plugin 类
入口文件必须定义 `Plugin` 类,实现以下生命周期方法:

```python
# main.py
class Plugin:
    """插件入口类,由主程序实例化"""

    def __init__(self, ctx):
        """
        插件初始化
        :param ctx: PluginContext,插件可用的 API 上下文(见 §6)
        """
        self.ctx = ctx

    def on_load(self):
        """插件加载时调用(可选)"""
        self.ctx.log_info("DXCC 助手已加载")

    def on_unload(self):
        """插件卸载/停用时调用(可选),用于释放资源"""
        pass

    def get_actions(self):
        """
        声明插件对外暴露的功能(可选)
        :return: list[dict],每项描述一个可被 invoke 的 action
        """
        return [
            {"action": "get_dxcc", "label": "查询 DXCC", "params": {"callsign": "str"}},
        ]

    def invoke(self, action, args):
        """
        被 POST /api/plugin/invoke 调用时执行(可选)
        :param action: str,功能名
        :param args: dict,参数
        :return: 任意可 JSON 序列化的结果
        """
        if action == "get_dxcc":
            return self._get_dxcc(args.get("callsign", ""))
        raise ValueError(f"未知 action: {action}")

    def _get_dxcc(self, callsign):
        # 业务实现
        return {"dxcc": "China", "itu": "44", "cq": "24"}
```

### 4.2 方法说明
| 方法 | 必需 | 调用时机 |
|------|------|---------|
| `__init__(self, ctx)` | 是 | 实例化,传入 PluginContext |
| `on_load(self)` | 否 | 加载完成后 |
| `on_unload(self)` | 否 | 卸载/停用前 |
| `get_actions(self)` | 否 | 声明可调用功能,供插件中心展示 |
| `invoke(self, action, args)` | 否 | 响应 `/api/plugin/invoke` |

### 4.3 注意事项
- 入口文件**不得**在顶层执行耗时操作或网络请求(加载会变慢)
- **不得**在顶层创建线程、打开端口、写文件
- 所有副作用应放在 `on_load` 或 `invoke` 中
- `__init__` 应只做轻量初始化(读配置、准备数据结构)

---

## 5. 权限模型

### 5.1 权限分类
| 类别 | 字段 | 是否需用户确认 | 说明 |
|------|------|---------------|------|
| 普通权限 | `permissions` | 否 | 只读、低风险 |
| 敏感权限 | `sensitive_permissions` | **是** | 高风险,前端醒目提醒 |

### 5.2 权限清单(v1)

#### 普通权限
| 权限 | 说明 |
|------|------|
| `log.read` | 读取 QSO 日志 |
| `log.write` | 新增/修改/删除日志(变更类,偏中风险,但归普通) |
| `settings.read` | 读取设置 |
| `settings.write` | 修改设置 |
| `qsl.read` | 读取 QSL 设计 |
| `ui.menu` | 在主界面注册菜单项 |
| `ui.style` | 注入自定义 CSS 样式(作用域限定插件根容器,见 §6.8) |
| `ui.theme` | 读取当前主题并响应主题切换 |
| `ui.panel` | 注册自定义面板/页面(嵌入主界面) |
| `ui.widget` | 注册自定义组件(卡片/小工具) |

> 样式类权限虽归普通,但 `inject_style` 会做安全过滤(禁 `@import`、禁 `url()` 指向非白名单域名、禁 `expression`),调用记入审计日志。

#### 敏感权限(需用户授权)
| 权限 | 说明 | 风险 |
|------|------|------|
| `network` | 发起网络请求 | 可外传数据 |
| `file.write` | 写文件系统 | 可破坏数据 |
| `file.read` | 读任意文件 | 可窃取敏感信息 |
| `system` | 执行系统命令 | 高危 |
| `db.raw` | 直接执行 SQL | 可绕过参数化 |
| `aes.decrypt` | 解密敏感字段 | 可获取明文敏感信息 |
| `subprocess` | 启动子进程 | 高危 |

### 5.3 权限校验流程
1. 加载时读取 manifest 的 `permissions` + `sensitive_permissions`
2. 调用 PluginContext 任何 API 前,校验对应权限是否已声明且已授权
3. 敏感权限需用户在插件中心显式授权(`POST /api/plugin/authorize`)
4. 默认 `config.plugins.allow_sensitive = false`,未授权时敏感 API 调用被拒绝并记录
5. 越权调用 → 抛 `PermissionError`,主程序捕获并返回 `403`,记入 `logs/plugin_audit.log`

### 5.4 最小权限原则
- **只申请真正需要的权限**
- 能用 `log.read` 就不要申请 `db.raw`
- 不需要网络就别申请 `network`
- 审核时会标记"权限过多"的插件供用户参考

---

## 6. 插件 API(PluginContext)

> 插件通过 `__init__(self, ctx)` 收到的 `ctx` 调用主程序能力。所有调用受权限校验。

### 6.1 日志
```python
ctx.log_debug(msg)
ctx.log_info(msg)
ctx.log_warning(msg)
ctx.log_error(msg)
```
> 走主程序统一日志系统(`core/logger.py`),source 标记为插件 id。

### 6.2 日志数据(`log.read` / `log.write`)
```python
logs = ctx.get_log(log_id)              # 单条 dict | None
logs = ctx.search_logs(keyword)         # 模糊搜索 list[dict]
logs = ctx.list_logs(page=1, size=50)   # 分页
ok = ctx.add_log(log_dict)              # 新增,需 log.write
ok = ctx.update_log(log_id, log_dict)   # 更新,需 log.write
ok = ctx.delete_log(log_id)             # 删除,需 log.write
stats = ctx.log_stats()                 # 统计
```

### 6.3 设置(`settings.read` / `settings.write`)
```python
val = ctx.get_setting(key)
ok = ctx.set_setting(key, value)
all_cfg = ctx.get_all_settings()        # 需 settings.read
```

### 6.4 QSL 设计(`qsl.read`)
```python
proj = ctx.get_qsl(project_id)
items = ctx.list_qsl()
```

### 6.5 网络(`network`,敏感)
```python
text = ctx.http_get(url, timeout=10)
text = ctx.http_post(url, body, timeout=10)
```
> 仅允许 HTTP/HTTPS;URL 会被记录到审计日志。禁止内网地址探测可由主程序配置限制。

### 6.6 文件系统(`file.read` / `file.write`,敏感)
```python
data = ctx.read_file(path)              # 需 file.read,路径受沙箱限制
ok = ctx.write_file(path, data)         # 需 file.write,限定在插件数据目录
path = ctx.plugin_data_dir()            # 返回插件专属数据目录,无需额外权限
```
- 插件应优先使用 `plugin_data_dir()` 存放自己的数据,该目录无需 `file.*` 权限
- `file.read/write` 仅在用户明确授权后才可访问该目录之外

### 6.7 加密(`aes.decrypt`,敏感)
```python
plain = ctx.decrypt(value)              # 解密主程序敏感字段,需 aes.decrypt
cipher = ctx.encrypt(plain)             # 加密,用于插件自己存敏感数据
```

### 6.8 UI 扩展(`ui.menu` / `ui.style` / `ui.theme` / `ui.panel` / `ui.widget`)
```python
# 注册菜单项(ui.menu)
ctx.register_menu({
    "label": "DXCC 查询",
    "action": "get_dxcc",
    "icon": "assets/flag.png"
})

# 注入自定义 CSS(ui.style)
#   - 作用域自动限定到插件根容器 #plugin-<id>,避免污染全局
#   - 安全过滤:剥离 @import / expression / 非白名单 url()
ctx.inject_style("""
  .my-card { padding: 8px; border-radius: 6px; }
  .my-card .title { font-weight: bold; }
""")

# 主题读取与响应(ui.theme)
theme = ctx.get_theme()                  # {"mode":"dark","colors":{...}}
ctx.on_theme_change(lambda t: self._recolor(t))   # 切换时回调(在插件子进程触发)

# 注册自定义面板/页面(ui.panel),嵌入主界面
ctx.register_panel({
    "id": "dxcc_panel",
    "label": "DXCC 面板",
    "html": "<div class='my-card'>...</div>",      # 静态 HTML
    "on_action": "panel_action"                    # 点击/交互时 invoke 的 action
})

# 注册自定义组件/小工具(ui.widget),如卡片、统计块
ctx.register_widget({
    "id": "dxcc_widget",
    "label": "今日 DXCC 数",
    "render": "widget_render",                      # 调用 invoke("widget_render", {}) 返回 HTML/JSON
    "refresh_interval": 60                          # 秒,0 表示不自动刷新
})
```
> 主程序把插件注入的 HTML/CSS 限定在插件专属容器内,菜单/面板点击交互通过 `invoke(action, args)` 回调到插件子进程。`inject_style` 的 CSS 会被加前缀 `#plugin-<id>` 实现作用域隔离。

### 6.9 元信息
```python
ctx.app_version        # 主程序版本 str
ctx.api_version        # 插件 API 版本 str
ctx.plugin_id          # 本插件 id str
ctx.plugin_dir         # 插件目录 Path
ctx.data_dir           # 插件数据目录 Path(可自由读写)
```

### 6.10 API 版本兼容
- `api_version: "1"` 对应上述全部 API
- 主程序保证同一大版本内 API 向后兼容
- 新增大版本时旧插件按声明的 `api_version` 走对应兼容层

---

## 7. 语法审核

### 7.1 审核时机
- 插件**安装时**
- 插件**启用时**
- 主程序**启动扫描时**

### 7.2 审核内容
```python
import ast, py_compile

def audit(plugin_dir) -> (ok: bool, errors: list):
    errors = []
    for py_file in plugin_dir.glob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        # 1. 语法树解析
        try:
            ast.parse(src, filename=str(py_file))
        except SyntaxError as e:
            errors.append(f"{py_file.name}:{e.lineno} {e.msg}")
            continue
        # 2. 编译
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"{py_file.name} 编译失败: {e}")
    return (len(errors) == 0, errors)
```

### 7.3 审核结果处理
- **审核不通过 → 不允许加载**
- 在插件中心显示"语法错误"标签 + 错误详情
- 调用 `/api/plugin/install` 时返回:
```json
{"code":422,"msg":"插件语法审核未通过,不允许加载",
 "data":{"id":"bad_plugin","audit_ok":false,"errors":["main.py:10 SyntaxError: invalid syntax"]}}
```
- 审核结果写入 `logs/plugin_audit.log`

### 7.4 不在审核范围
语法审核**只检查语法正确性**,不检查:
- 安全性(由沙箱 + 权限模型保证)
- 业务逻辑正确性
- 性能

---

## 8. 沙箱与隔离

### 8.1 隔离机制
- 插件 `invoke` 与耗时操作在**子进程**中执行(`multiprocessing`)
- 主进程通过 IPC(管道/队列)与插件子进程通信
- 插件子进程不直接持有主进程的数据库连接、Flask app 等对象
- PluginContext 是 IPC 代理,调用经主进程校验权限后执行

### 8.2 资源限制
| 维度 | 限制 | 说明 |
|------|------|------|
| 执行超时 | 默认 30s(invoke 可配) | 超时终止子进程,返回 `503` |
| 内存 | 256MB(可配) | 超限终止 |
| CPU | 单核 | 防止占用过高 |
| 并发 | 同一插件串行 | 避免并发冲突 |

### 8.3 异常隔离
- 插件抛出的任何异常被子进程捕获,序列化后回传主进程
- 主进程记录日志,返回 `503` 给前端,**不上抛到业务层**
- **插件崩溃不影响主程序、数据库、其他插件**

### 8.4 文件系统隔离
- 插件默认只能读写自己的 `plugin_data_dir()`
- 访问其他路径需 `file.read/write` 权限且用户授权
- 沙箱层面也会限制可访问路径白名单

---

## 9. 生命周期

```
扫描 plugins/ 目录
      ↓
读取 manifest.json,校验 id/entry/version
      ↓
语法审核(ast + py_compile)── 失败 → 标记"语法错误",不加载
      ↓
权限校验:敏感权限是否已授权?
      ↓  否
加载但标记"待授权",敏感 API 不可用
      ↓  是
子进程加载 Plugin(ctx),调用 on_load()
      ↓
就绪,可响应 invoke / 菜单点击
      ↓
停用/卸载 → 调用 on_unload() → 终止子进程
```

---

## 10. 完整示例:DXCC 助手

### 10.1 目录
```
plugins/dxcc_helper/
├── manifest.json
└── main.py
```

### 10.2 manifest.json
```json
{
  "id": "dxcc_helper",
  "name": "DXCC 助手",
  "version": "1.0.0",
  "author": "BA8AQA",
  "description": "根据呼号前缀查询 DXCC 实体、ITU/CQ 分区",
  "entry": "main.py",
  "min_app_version": "2.0.0",
  "api_version": "1",
  "permissions": ["log.read", "ui.menu"],
  "sensitive_permissions": [],
  "license": "MIT"
}
```

### 10.3 main.py
```python
# -*- coding: utf-8 -*-
"""DXCC 助手插件 - 根据呼号前缀查询实体信息"""

# 内置前缀表(简化示例)
PREFIX_TABLE = {
    "BA": {"dxcc": "China", "itu": "44", "cq": "24"},
    "BD": {"dxcc": "China", "itu": "44", "cq": "24"},
    "BG": {"dxcc": "China", "itu": "44", "cq": "24"},
    "BH": {"dxcc": "China", "itu": "44", "cq": "24"},
    "BY": {"dxcc": "China", "itu": "44", "cq": "24"},
    "BZ": {"dxcc": "China", "itu": "44", "cq": "24"},
    "W":  {"dxcc": "United States", "itu": "08", "cq": "05"},
    "K":  {"dxcc": "United States", "itu": "08", "cq": "05"},
    "N":  {"dxcc": "United States", "itu": "08", "cq": "05"},
    "JA": {"dxcc": "Japan", "itu": "45", "cq": "25"},
}


class Plugin:
    def __init__(self, ctx):
        self.ctx = ctx

    def on_load(self):
        self.ctx.log_info("DXCC 助手已加载")
        self.ctx.register_menu({
            "label": "DXCC 查询",
            "action": "get_dxcc",
            "icon": "assets/flag.png"
        })

    def on_unload(self):
        self.ctx.log_info("DXCC 助手已卸载")

    def get_actions(self):
        return [
            {"action": "get_dxcc", "label": "查询 DXCC",
             "params": {"callsign": "str"}},
        ]

    def invoke(self, action, args):
        if action == "get_dxcc":
            return self._get_dxcc(args.get("callsign", ""))
        raise ValueError(f"未知 action: {action}")

    def _get_dxc(self, callsign):
        call = callsign.strip().upper()
        if not call:
            return {"error": "呼号为空"}
        # 前缀匹配:从长到短尝试
        for length in (2, 1):
            prefix = call[:length]
            if prefix in PREFIX_TABLE:
                self.ctx.log_info(f"查询 {call} -> {PREFIX_TABLE[prefix]['dxcc']}")
                return {"callsign": call, **PREFIX_TABLE[prefix]}
        return {"callsign": call, "error": "未识别的前缀"}
```

---

## 11. 发布到插件源

### 11.1 插件源格式
插件源是一个 HTTP URL,返回 JSON 索引。**官方源与第三方源使用同一格式**,但只有官方源(`source_type: "official"`)携带并维护评级数据。

```json
{
  "source_type": "official",
  "name": "HamLog 官方插件源",
  "api_version": "1",
  "updated_at": "2026-08-08T00:00:00Z",
  "plugins": [
    {
      "id": "dxcc_helper",
      "name": "DXCC 助手",
      "version": "1.0.0",
      "author": "BA8AQA",
      "author_id": "ba8aqa",
      "description": "根据呼号前缀查询 DXCC 实体、ITU/CQ 分区",
      "permissions": ["log.read", "ui.menu"],
      "sensitive_permissions": [],
      "download_url": "https://example.com/plugins/dxcc_helper-1.0.0.zip",
      "sha256": "abc123...",
      "homepage": "...",
      "license": "MIT",
      "rating": { "score": 4.8, "count": 126, "level": "silver" },
      "author_rating": { "score": 4.9, "level": "gold" },
      "verified": true
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `source_type` | 是 | `official` / `third_party` |
| `name` | 是 | 源显示名 |
| `api_version` | 是 | 源索引格式版本,当前 `1` |
| `updated_at` | 是 | 源索引更新时间(ISO8601,UTC) |
| `plugins[].author_id` | 否 | 作者唯一标识(用于聚合开发者评级) |
| `plugins[].rating` | 否 | 插件评级(官方源必填,第三方源可选,见 §12) |
| `plugins[].author_rating` | 否 | 开发者评级(官方源必填) |
| `plugins[].verified` | 否 | 是否官方认证 |

> 第三方源**可不填** `rating`/`author_rating`,此时前端显示"无评级(第三方源)"。

### 11.2 打包
- 插件以 **zip** 分发,解压后应直接得到插件文件夹(含 manifest + py)
- zip 内结构:
  ```
  dxcc_helper-1.0.0.zip
  └── dxcc_helper/
      ├── manifest.json
      └── main.py
  ```
- 提供 `sha256` 供安装时校验完整性

### 11.3 安装流程
1. 用户在插件中心添加源(官方源默认存在,可加第三方源)
2. 浏览 `/api/plugin/market`
3. `POST /api/plugin/install` 下载 zip → 校验 sha256 → 解压到 `plugins/` → 语法审核 → 加载

---

## 12. 评级系统

### 12.1 概述
为引导插件生态质量,建立**插件评级**与**开发者评级**双重体系:
- **插件评级**:针对单个插件版本的评分、评级等级、官方认证状态
- **开发者评级**:针对作者(account)的累积评分与等级,跨其名下所有插件聚合
- 评级数据由**官方源维护**,客户端每次访问官方源时拉取并更新本地缓存索引
- **第三方源可携带评级**(按本规范格式),但前端会标注"第三方源评级",与官方评级区分显示

### 12.2 评级数据来源
| 数据 | 维护方 | 说明 |
|------|--------|------|
| 插件评分 `rating.score` | 官方源 | 由仓库维护者综合评定(质量、稳定性、安全、反馈等) |
| 插件评分人数 `rating.count` | 官方源 | 累计评分数(维护者口径) |
| 插件等级 `rating.level` | 官方源 | `bronze`/`silver`/`gold`/`platinum`(见 12.4) |
| 开发者评分 `author_rating.score` | 官方源 | 名下所有插件综合评定 |
| 开发者等级 `author_rating.level` | 官方源 | 同插件等级体系 |
| 认证标记 `verified` | 官方源 | 官方认证的开发者/插件 |

> **评级由仓库维护者决定,客户端只读不写**。客户端不提供评分上报接口,不参与评级计算。评级数据随官方源索引一并下发,访问官方源时自动更新本地缓存。

### 12.3 索引与评分更新机制
- **触发时机**:
  - 进入插件中心市场页时
  - 手动刷新源(`/api/plugin/source/refresh`)
  - 后台定时(默认每 24h,可配)
- **流程**:
  1. 客户端请求官方源索引 URL
  2. 解析 `updated_at`,若新于本地缓存则全量更新本地索引表 `plugin_market_cache`
  3. 同步各插件的 `rating` / `author_rating` / `verified`
  4. 前端展示最新评分与等级
- **第三方源**:同样拉取,但 `source_type=third_party` 的评级在 UI 标注来源,不与官方评级混算
- **离线**:使用本地缓存索引,标注"缓存时间 xxx,可能非最新"

### 12.4 等级体系
| 等级 | 标识 | 门槛(参考) |
|------|------|-------------|
| 青铜 Bronze | 🥉 | 已上架,通过语法审核 |
| 白银 Silver | 🥈 | 评分 ≥ 4.0 且评分人数 ≥ 20 |
| 黄金 Gold | 🥇 | 评分 ≥ 4.5 且评分人数 ≥ 100,无重大安全投诉 |
| 铂金 Platinum | 💎 | 评分 ≥ 4.8 且评分人数 ≥ 500,官方认证 |

开发者等级按其名下**最高等级插件 + 综合评分**评定。

### 12.5 评级数据字段规范(源索引内)
```json
"rating": {
  "score": 4.8,            // 0.0 ~ 5.0,保留一位小数
  "count": 126,            // 评分人数,整数
  "level": "silver",       // bronze/silver/gold/platinum
  "trend": 0.2,            // 近 30 天评分变化(可选)
  "updated_at": "2026-08-08T00:00:00Z"
},
"author_rating": {
  "score": 4.9,
  "level": "gold",
  "plugin_count": 3,       // 名下插件数
  "updated_at": "2026-08-08T00:00:00Z"
},
"verified": true,
"badges": ["staff_pick", "no_sensitive"]   // 可选,官方徽章
```
`badges` 可选值:`staff_pick`(官方推荐)、`no_sensitive`(无敏感权限)、`open_source`(开源)、`maintained`(持续维护)。

### 12.6 评级展示(UI 约定)
- 列表/详情页显示:星级(score)、人数(count)、等级徽章(level)、认证勾(verified)、徽章标签(badges)
- 第三方源评级独立标注"第三方源",官方源标注"官方评级"
- 评分人数 < 某阈值(如 5)时显示"评分样本不足"

---

## 13. 开发检查清单

发布前请自检:

- [ ] 文件夹名为英文小写 + 数字 + `_`/`-`,以字母开头
- [ ] `manifest.json` 字段完整,`id` 与文件夹名一致
- [ ] `entry` 指向的文件存在且定义 `Plugin` 类
- [ ] `__init__` 只做轻量初始化,无耗时/网络/文件副作用
- [ ] 权限按最小原则申请,敏感权限单独列出
- [ ] 所有 API 调用通过 `ctx`,不直接访问主程序对象
- [ ] 数据存放在 `ctx.plugin_data_dir()`,不乱写文件系统
- [ ] 异常自行捕获处理,不依赖主程序兜底
- [ ] `on_unload` 释放资源(关闭连接、保存数据)
- [ ] 通过 `ast.parse` + `py_compile` 语法审核
- [ ] zip 结构正确,提供 sha256

---

## 14. 调试

### 14.1 本地开发
1. 将插件文件夹放入 `plugins/`
2. 重启后端或调用 `POST /api/plugin/toggle` 重新加载
3. 查看 `logs/plugin_audit.log` 与 `logs/app.log`(source 为插件 id)

### 14.2 手动调用
```bash
curl -X POST http://127.0.0.1:5000/api/plugin/invoke \
  -H "Content-Type: application/json" \
  -d '{"id":"dxcc_helper","action":"get_dxcc","args":{"callsign":"BA8AQA"}}'
```

### 14.3 常见问题
| 现象 | 原因 |
|------|------|
| 插件不加载 | 文件夹名不合规 / `id` 不一致 / 语法审核失败 |
| invoke 返回 403 | 权限未声明或敏感权限未授权 |
| invoke 返回 503 | 插件抛异常或超时,查看日志 |
| 菜单不显示 | 未调用 `register_menu` 或缺 `ui.menu` 权限 |
| 文件写入失败 | 未申请 `file.write` 或路径超出沙箱白名单 |
| 评级不显示 | 第三方源未提供 rating,或源索引未刷新 |

---

## 15. 安全提醒(给开发者)

- **不要**在插件中硬编码任何用户凭据
- **不要**收集用户数据外传(`network` 权限会被用户审查)
- **不要**尝试绕过沙箱(访问主进程对象、执行系统命令)
- 涉及敏感权限的功能,在 description 中明确说明用途
- 发布前自查:你的插件是否真的需要所申请的每一项权限?
- **不要**自行伪造评级数据:评级以官方源下发为准,客户端展示以本地缓存的官方索引为准

> 主程序会对插件行为做审计记录,恶意插件会被用户通过日志发现并卸载。

---

## 16. 版本演进

- 插件 API 版本与主程序大版本对应
- v1 API 保证向后兼容,新增能力以可选方法/字段形式扩展
- 不兼容变更将提升 `api_version`(v2),旧插件按声明的版本走兼容层
- 弃用的 API 在日志中提示 `DeprecationWarning`,保留至少一个大版本周期

---

*本规范随 HamLog 演进持续更新。开发中如遇不明确处,以主程序 `backend/plugins/api.py` 实现为准。*
