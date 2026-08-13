# HamLog Web API 接口文档

> 业余无线电台日志管理系统 · 前后端分离重构版 · API 规范
> 版本:Release 2.0.0 ｜ 协议:GPL-3.0
> 仓库:https://github.com/ARPRC-BA8AQA/HamLog
> 配套:[PROJECT.md](PROJECT.md) / [TECHNICAL.md](TECHNICAL.md) / [STRUCTURE.md](STRUCTURE.md)

---

## 0. 全局约定

### 0.1 请求方式
- **统一 POST**(查询与变更均用 POST)
- `Content-Type: application/json`
- 请求体为 JSON 对象
- 统一前缀 `/api/`

### 0.2 标准响应结构
所有接口返回统一 JSON:
```json
{
  "code": 200,
  "msg": "ok",
  "data": { }
}
```
- `code`:业务状态码(整数)
- `msg`:提示信息
- `data`:业务数据(可为对象/数组/字符串/null)

### 0.3 状态码
| code | 含义 |
|------|------|
| 200 | 成功 |
| 400 | 参数错误/校验失败 |
| 401 | 未认证/Token 失效 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 冲突(如重复) |
| 422 | 业务校验不通过(如呼号格式错误) |
| 500 | 服务器内部错误 |
| 503 | 依赖不可用(如 TQSL 未安装、NTP 不可达) |

### 0.4 认证(JWT,可选)
- 配置 `auth.enabled = true` 时启用
- 受保护接口需请求头携带:
  ```
  Authorization: Bearer <access_token>
  ```
- 关闭认证时,所有接口默认全权放行,无需 Token

### 0.5 CSRF 防护(可选)
- 配置 `security.csrf_enabled = true` 时启用
- 变更类接口需请求头携带:
  ```
  X-CSRF-Token: <token>
  ```
- Token 通过 `POST /api/auth/csrf` 获取

### 0.6 时间与编码
- 日期:`YYYY-MM-DD`
- 时间:`HHMM` 或 `HHMMSS`(UTC)
- QSL 日期:`YYYYMMDD`
- 字符编码:UTF-8

### 0.7 通用错误响应示例
```json
{"code": 400, "msg": "callsign 不能为空", "data": null}
{"code": 401, "msg": "未认证或 Token 已过期", "data": null}
{"code": 403, "msg": "需要管理员权限", "data": null}
{"code": 500, "msg": "内部错误: ...", "data": null}
```

---

## 1. 认证模块 `/api/auth`

> 仅当 `auth.enabled = true` 时需要登录;关闭时登录接口仍可调用但非必需。

### 1.1 登录
`POST /api/auth/login`

请求:
```json
{"username": "admin", "password": "******"}
```
响应:
```json
{
  "code": 200, "msg": "ok",
  "data": {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "expires_in": 7200,
    "role": "admin",
    "username": "admin"
  }
}
```
错误:`401` 用户名或密码错误;`403` 账户被禁用。

### 1.2 刷新 Token
`POST /api/auth/refresh`

请求:
```json
{"refresh_token": "eyJhbGciOi..."}
```
响应:
```json
{"code": 200, "msg": "ok", "data": {"access_token": "...", "expires_in": 7200}}
```
错误:`401` refresh_token 无效或过期。

### 1.3 登出
`POST /api/auth/logout`

请求头:`Authorization`
响应:
```json
{"code": 200, "msg": "ok", "data": null}
```

### 1.4 获取 CSRF Token
`POST /api/auth/csrf`

请求:无
响应:
```json
{"code": 200, "msg": "ok", "data": {"csrf_token": "a1b2c3..."}}
```

### 1.5 获取当前认证状态
`POST /api/auth/status`

响应:
```json
{"code": 200, "msg": "ok", "data": {"auth_enabled": true, "logged_in": true, "role": "admin", "username": "admin"}}
```

### 1.6 用户管理(管理员)
| 接口 | 说明 |
|------|------|
| `POST /api/auth/user/list` | 用户列表(管理员) |
| `POST /api/auth/user/create` | 创建用户(管理员) |
| `POST /api/auth/user/update` | 修改用户/重置密码(管理员) |
| `POST /api/auth/user/delete` | 删除用户(管理员) |

`user/create` 请求:
```json
{"username": "op1", "password": "******", "role": "user"}
```

---

## 2. QSO 日志模块 `/api/log`

### 2.1 日志列表
`POST /api/log/list`

请求:
```json
{
  "page": 1,
  "page_size": 50,
  "keyword": "BA8",
  "callsign": null,
  "band": null,
  "mode": null,
  "date_from": "2026-01-01",
  "date_to": null,
  "order": "desc"
}
```
所有过滤项可选,传 `null` 或省略即不过滤。
响应:
```json
{
  "code": 200, "msg": "ok",
  "data": {
    "total": 328,
    "page": 1, "page_size": 50,
    "items": [
      {"id": 1024, "Callsign": "BA8AQA", "Freq": "144.000MHz",
       "Year": 2026, "Month": 8, "Day": 8, "Time": "0230",
       "Mode": "FM", "Power_self": "5W", "Power_side": "10W",
       "Rst_self": "59", "Rst_side": "59", "QTH": "Mianyang",
       "Device": "FT-817", "QSL_RX": "", "QSL_SEND": "",
       "Remarks": "", "CreateTime": "2026-08-08 02:30:11"}
    ]
  }
}
```

### 2.2 获取单条
`POST /api/log/get`
```json
{"id": 1024}
```
错误:`404` 不存在。

### 2.3 新增
`POST /api/log/add`
```json
{
  "Callsign": "BA8AQA",
  "Freq": "144.000MHz",
  "Year": 2026, "Month": 8, "Day": 8, "Time": "0230",
  "Mode": "FM",
  "Power_self": "5W", "Power_side": "10W",
  "Rst_self": "59", "Rst_side": "59",
  "QTH": "Mianyang", "Device": "FT-817",
  "QSL_RX": "", "QSL_SEND": "", "Remarks": ""
}
```
响应:
```json
{"code": 200, "msg": "日志添加成功", "data": {"id": 1025}}
```
错误:`422` 呼号/日期/时间/频率校验失败;`400` 字段非法。

### 2.4 更新
`POST /api/log/update`
```json
{"id": 1024, "log": { "QTH": "Chengdu" }}
```
响应:`{"code":200,"msg":"更新成功","data":{"id":1024}}`

### 2.5 删除
`POST /api/log/delete`
```json
{"id": 1024}
```

### 2.6 模糊搜索
`POST /api/log/search`
```json
{"keyword": "BA8", "limit": 100}
```
响应同 list 的 `items`(无分页)。

### 2.7 统计
`POST /api/log/stats`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"total":328,"today":12,"this_month":56,"by_band":{"2m":120,"70cm":80},"by_mode":{"FM":200,"FT8":128}}}
```

### 2.8 清空(管理员)
`POST /api/log/clear`
```json
{"confirm": "CLEAR"}
```
需 `confirm` 文本二次确认;管理员权限。

---

## 3. 设置模块 `/api/settings`

### 3.1 获取全部
`POST /api/settings/get_all`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"my_callsign":"BA8AQA","my_qth":"Mianyang","theme":"dark", ...}}
```

### 3.2 获取单项
`POST /api/settings/get`
```json
{"key": "my_callsign"}
```

### 3.3 设置单项
`POST /api/settings/set`
```json
{"key": "my_callsign", "value": "BA8AQA"}
```

### 3.4 批量设置
`POST /api/settings/set_many`
```json
{"items": {"my_callsign":"BA8AQA","theme":"light"}}
```

---

## 4. ADIF 导出模块 `/api/adif`

### 4.1 导出 ADIF 文件
`POST /api/adif/export`
```json
{
  "date_from": "2026-01-01",
  "date_to": "2026-12-31",
  "band": null,
  "mode": null,
  "station_callsign": "BA8AQA"
}
```
响应(返回导出统计 + 下载标识):
```json
{"code":200,"msg":"ok","data":{"token":"exp_abc123","total":120,"exported":120,"skipped":0,"errors":[]}}
```

### 4.2 下载导出文件
`POST /api/adif/download`
```json
{"token": "exp_abc123"}
```
响应:`application/octet-stream` 文件流(`.adi`),或:
```json
{"code":404,"msg":"导出文件不存在或已过期","data":null}
```

---

## 5. LoTW 上传模块 `/api/lotw`

### 5.1 查找 TQSL
`POST /api/lotw/find_tqsl`
```json
{"search_drives": null}
```
响应:
```json
{"code":200,"msg":"ok","data":{"tqsl_path":"C:\\Program Files\\TrustedQSL\\tqsl.exe","version":"2.7.1"}}
```
错误:`503` 未找到 TQSL。

### 5.2 查找证书
`POST /api/lotw/list_certs`
```json
{"tqsl_path": null}
```
响应:
```json
{"code":200,"msg":"ok","data":{"certs":[{"callsign":"BA8AQA","station":"Mianyang","expire":"2028-01-01"}]}}
```

### 5.3 上传
`POST /api/lotw/upload`
```json
{
  "tqsl_path": null,
  "station_location": "Mianyang",
  "adif_token": "exp_abc123",
  "duplicate_strategy": "skip"
}
```
`duplicate_strategy`: `skip` / `replace` / `ask`
响应(异步任务):
```json
{"code":200,"msg":"ok","data":{"task_id":"lotw_xxx"}}
```

### 5.4 查询上传进度
`POST /api/lotw/progress`
```json
{"task_id": "lotw_xxx"}
```
响应:
```json
{"code":200,"msg":"ok","data":{"status":"done","uploaded":120,"duplicates":0,"errors":[],"message":"上传完成"}}
```
`status`: `pending` / `signing` / `uploading` / `done` / `error`

---

## 6. QRZ 查询模块 `/api/qrz`

### 6.1 查询呼号
`POST /api/qrz/lookup`
```json
{"callsign": "BA8AQA", "login": false}
```
`login`:是否使用登录态(需配置 QRZ 账号;关闭时走游客模式)
响应:
```json
{
  "code":200,"msg":"ok",
  "data":{
    "callsign":"BA8AQA","url":"https://www.qrz.com/db/BA8AQA","found":true,
    "country":"China (中国)","has_detail":false,"has_biography":true,
    "image_url":"https://cdn-bio.qrz.com/...","qsl_info":"...",
    "name":null,"qth":null,"grid":null,"email":null,
    "license_class":null,"previous_call":null,"lotw":true,"eqsl":false,
    "bio":"Hello! This is BA8AQA..."
  }
}
```
错误:`404` 呼号不存在;`503` 网络错误/被反爬拦截。

### 6.2 QRZ 账号配置
`POST /api/qrz/set_credential`
```json
{"username":"xxx","password":"xxx","encrypt":true}
```
> 密码可选 AES-256 加密存储(见 §9.3)。敏感字段写入 `plugin_audit.log` 仅记录"已配置/已清除"。

### 6.3 清除凭据
`POST /api/qrz/clear_credential`
```json
{}
```

---

## 7. QSL 卡片设计模块 `/api/qsl`

### 7.1 保存设计
`POST /api/qsl/save`
```json
{
  "id": "proj_001",
  "name": "我的卡片A",
  "content": {
    "schema_version": "1.0",
    "canvas": {"width":148,"height":105,"unit":"mm"},
    "background": {"type":"image","ref":"asset_xxx"},
    "elements": [
      {"id":"e1","type":"text","x":10,"y":20,"w":80,"h":12,"text":"{callsign}","binding":"log.callsign","style":{"font_size":14}}
    ],
    "assets": {"asset_xxx":{"type":"image","dataurl":"data:image/png;base64,..."}}
  }
}
```
响应:
```json
{"code":200,"msg":"保存成功","data":{"id":"proj_001","updated_at":"2026-08-08T03:00:00"}}
```

### 7.2 自动保存(10s 触发)
`POST /api/qsl/autosave`
```json
{"id":"proj_001","name":"我的卡片A","content":{...}}
```
响应:
```json
{"code":200,"msg":"ok","data":{"saved":true,"updated_at":"2026-08-08T03:00:10"}}
```
> 前端每 10s 检测 dirty 标志,有更新才调用。

### 7.3 项目列表
`POST /api/qsl/list`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"items":[{"id":"proj_001","name":"我的卡片A","updated_at":"2026-08-08T03:00:00"}]}}
```

### 7.4 加载设计
`POST /api/qsl/load`
```json
{"id":"proj_001"}
```
响应:
```json
{"code":200,"msg":"ok","data":{"id":"proj_001","name":"我的卡片A","content":{...}}}
```
错误:`404` 不存在。**版本兼容**:旧 schema 由迁移器处理,未知字段忽略,能读多少读多少。

### 7.5 删除
`POST /api/qsl/delete`
```json
{"id":"proj_001"}
```

### 7.6 导出私有格式 `.hamqsl`
`POST /api/qsl/export_private`
```json
{"id":"proj_001"}
```
响应:文件流(`.hamqsl`,JSON),或带 token:
```json
{"code":200,"msg":"ok","data":{"token":"qsl_exp_xxx"}}
```
再调 `POST /api/qsl/download` 下载。

### 7.7 导入私有格式
`POST /api/qsl/import_private`
请求:`multipart/form-data`,字段 `file`(支持 `.hamqsl`)
响应:
```json
{"code":200,"msg":"导入成功","data":{"id":"proj_002","name":"我的卡片A","migrated":true,"schema_version":"1.0"}}
```
> 跨设备导入,资源以 dataurl/asset_id 自动还原;旧版本自动迁移。

### 7.8 导出公共格式(PDF/PNG)
`POST /api/qsl/export_public`
```json
{
  "id":"proj_001",
  "format":"pdf",
  "paper":"A6",
  "width":148,"height":105,"unit":"mm",
  "dpi":300,
  "data": {
    "log.callsign":"BA8AQA","log.date":"2026-08-08","log.freq":"144.000MHz",
    "log.rst":"59","station.my_callsign":"BA8AQA","station.my_qth":"Mianyang"
  }
}
```
`format`: `pdf` / `png`
`data`:一键填充的实际数据(按绑定替换占位符)
响应:文件流,或:
```json
{"code":200,"msg":"ok","data":{"token":"qsl_pdf_xxx"}}
```

### 7.9 下载导出文件
`POST /api/qsl/download`
```json
{"token":"qsl_pdf_xxx"}
```
响应:`application/pdf` 或 `image/png` 文件流。

### 7.10 上传背景图/素材
`POST /api/qsl/upload_asset`
请求:`multipart/form-data`,字段 `file`
响应:
```json
{"code":200,"msg":"ok","data":{"asset_id":"asset_yyy","url":"/api/qsl/asset/asset_yyy"}}
```

### 7.11 数据类别列表(供绑定选择)
`POST /api/qsl/data_fields`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"fields":[
  {"key":"log.callsign","label":"对方呼号","group":"通联"},
  {"key":"log.date","label":"通联日期","group":"通联"},
  {"key":"log.freq","label":"频率","group":"通联"},
  {"key":"log.rst","label":"信号报告","group":"通联"},
  {"key":"station.my_callsign","label":"我的呼号","group":"本台"},
  {"key":"station.my_qth","label":"我的QTH","group":"本台"}
]}}
```

---

## 8. 插件模块 `/api/plugin`

### 8.1 插件源管理
`POST /api/plugin/source/list`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"sources":[
  {"id":"official","name":"HamLog 官方插件源","url":"official",
   "source_type":"official","enabled":true,"updated_at":"2026-08-08T00:00:00Z","cached_at":"2026-08-08T01:00:00Z"}
]}}
```

`POST /api/plugin/source/add`
```json
{"name":"第三方源","url":"https://example.com/plugins/index.json"}
```
> 添加后会自动拉取一次索引校验格式;`source_type` 由源索引自带决定。

`POST /api/plugin/source/delete`
```json
{"id":"src_xxx"}
```
> 官方源不可删除。

`POST /api/plugin/source/toggle`
```json
{"id":"src_xxx","enabled":true}
```

`POST /api/plugin/source/refresh`
```json
{"source_id": null}
```
> `source_id` 为空则刷新全部启用源。拉取最新索引并更新本地缓存与评级数据。
响应:
```json
{"code":200,"msg":"ok","data":{"refreshed":["official","src_xxx"],"updated_at":{"official":"2026-08-08T00:00:00Z"}}}
```

### 8.2 浏览可安装插件
`POST /api/plugin/market`
```json
{"source_id": null, "keyword": null, "sort": "rating"}
```
`sort`: `rating`(默认,按评分)/ `updated`(最新)/ `name`(名称)
响应:
```json
{"code":200,"msg":"ok","data":{"cached_at":"2026-08-08T01:00:00Z","items":[
  {"id":"dxcc_helper","name":"DXCC助手","version":"1.0.0","author":"BA8AQA","author_id":"ba8aqa",
   "description":"...","permissions":["log.read"],"sensitive_permissions":[],
   "installed":false,"update_available":false,"verified":true,
   "source_id":"official","source_type":"official",
   "rating":{"score":4.8,"count":126,"level":"silver","trend":0.2,"updated_at":"2026-08-08T00:00:00Z"},
   "author_rating":{"score":4.9,"level":"gold","plugin_count":3},
   "badges":["staff_pick","no_sensitive"]}
]}}
```
> 第三方源条目 `source_type:"third_party"`,评级字段可能为 `null`,前端标注"第三方源"。

### 8.3 安装
`POST /api/plugin/install`
```json
{"source_id":"official","plugin_id":"dxcc_helper"}
```
> 安装后触发语法审核;若失败返回 `422` 且不加载,`data.errors` 给出语法错误详情。
响应(成功):
```json
{"code":200,"msg":"安装成功","data":{"id":"dxcc_helper","audit_ok":true,"errors":[]}}
```
响应(语法错误):
```json
{"code":422,"msg":"插件语法审核未通过,不允许加载","data":{"id":"dxcc_helper","audit_ok":false,"errors":["main.py:10 SyntaxError: invalid syntax"]}}
```

### 8.4 卸载
`POST /api/plugin/uninstall`
```json
{"id":"dxcc_helper"}
```

### 8.5 启用/停用
`POST /api/plugin/toggle`
```json
{"id":"dxcc_helper","enabled":true}
```

### 8.6 已安装列表
`POST /api/plugin/installed`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"items":[
  {"id":"dxcc_helper","name":"DXCC助手","version":"1.0.0","enabled":true,"audit_ok":true,
   "permissions":["log.read"],"sensitive_permissions":[],"authorized":true,
   "source_id":"official","source_type":"official",
   "rating":{"score":4.8,"count":126,"level":"silver"},
   "author_rating":{"score":4.9,"level":"gold"},"verified":true}
]}}
```

### 8.7 检查更新
`POST /api/plugin/check_update`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"updates":[{"id":"dxcc_helper","current":"1.0.0","latest":"1.1.0"}]}}
```

### 8.8 授权敏感权限(用户确认)
`POST /api/plugin/authorize`
```json
{"id":"dxcc_helper","allow_sensitive":true}
```
> 前端需醒目提醒用户敏感权限风险。

### 8.9 调用插件功能
`POST /api/plugin/invoke`
```json
{"id":"dxcc_helper","action":"get_dxcc","args":{"callsign":"BA8AQA"}}
```
响应:
```json
{"code":200,"msg":"ok","data":{"result":{"dxcc":"China","itu":"44","cq":"24"}}}
```
错误:`422` 插件未启用/未授权;`503` 插件运行异常(已隔离,不影响主系统)。

### 8.10 插件元信息
`POST /api/plugin/info`
```json
{"id":"dxcc_helper"}
```
响应:
```json
{"code":200,"msg":"ok","data":{
  "manifest":{...},
  "enabled":true,"audit_ok":true,"authorized":true,
  "source_id":"official","source_type":"official","verified":true,
  "rating":{"score":4.8,"count":126,"level":"silver","updated_at":"2026-08-08T00:00:00Z"},
  "author_rating":{"score":4.9,"level":"gold","plugin_count":3},
  "badges":["staff_pick"]
}}
```

### 8.11 查询插件评级详情
`POST /api/plugin/rating`
```json
{"id":"dxcc_helper"}
```
响应:
```json
{"code":200,"msg":"ok","data":{
  "id":"dxcc_helper",
  "rating":{"score":4.8,"count":126,"level":"silver","trend":0.2,"updated_at":"2026-08-08T00:00:00Z"},
  "distribution":{"5":90,"4":30,"3":4,"2":1,"1":1},
  "source_type":"official","verified":true,"badges":["staff_pick","no_sensitive"]
}}
```
> 第三方源评级返回 `source_type:"third_party"`,前端区分展示。评级为只读,由仓库维护者决定。

### 8.12 查询开发者评级
`POST /api/plugin/author_rating`
```json
{"author_id":"ba8aqa"}
```
响应:
```json
{"code":200,"msg":"ok","data":{
  "author_id":"ba8aqa","author":"BA8AQA",
  "rating":{"score":4.9,"level":"gold","plugin_count":3,"updated_at":"2026-08-08T00:00:00Z"},
  "plugins":[{"id":"dxcc_helper","name":"DXCC助手","level":"silver","score":4.8}],
  "verified":true
}}
```

---

## 9. 网络延迟模块 `/api/intertime`

### 9.1 获取配置
`POST /api/intertime/get`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"enabled":true,"nodes":["www.baidu.com","8.8.8.8"],"timeout":2,"interval":5,"display_names":{}}}
```

### 9.2 保存配置
`POST /api/intertime/set`
```json
{"enabled":true,"nodes":["www.baidu.com","8.8.8.8"],"timeout":2,"interval":5,"display_names":{}}
```

### 9.3 立即检测一次
`POST /api/intertime/test`
```json
{"nodes":["www.baidu.com","8.8.8.8"],"timeout":2}
```
响应:
```json
{"code":200,"msg":"ok","data":{"results":[{"node":"www.baidu.com","time_ms":23,"ok":true},{"node":"8.8.8.8","time_ms":120,"ok":true}]}}
```

### 9.4 启动/停止轮询
`POST /api/intertime/start` / `POST /api/intertime/stop`

---

## 10. 在线更新模块 `/api/update`

### 10.1 检查更新
`POST /api/update/check`
```json
{"current_version":"Release 2.0.0"}
```
响应:
```json
{"code":200,"msg":"ok","data":{
  "has_update":true,"latest_version":"Release 2.1.0","force_update":false,
  "changelog":"1. 新增 QSL 设计器\n2. 修复 ...","exe_url":"https://..."}}
```

### 10.2 下载更新
`POST /api/update/download`
```json
{"exe_url":"https://..."}
```
响应(异步):
```json
{"code":200,"msg":"ok","data":{"task_id":"upd_xxx"}}
```

### 10.3 下载进度
`POST /api/update/progress`
```json
{"task_id":"upd_xxx"}
```
响应:
```json
{"code":200,"msg":"ok","data":{"status":"downloading","percent":45,"speed_kbps":1024,"error":null}}
```

### 10.4 安装更新
`POST /api/update/install`
```json
{"task_id":"upd_xxx"}
```
> 触发安装包运行并退出当前后端。

---

## 11. 系统模块 `/api/system`

### 11.1 系统信息
`POST /api/system/info`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{
  "app_version":"Release 2.0.0","python_version":"3.11.4","platform":"Windows-10",
  "db_path":".../Log.db","uptime_seconds":3600}}
```

### 11.2 授时同步
`POST /api/system/sync_time`
```json
{"servers":["ntp.ntsc.ac.cn","pool.ntp.org"]}
```
响应:
```json
{"code":200,"msg":"ok","data":{"offset_ms":-120,"synced":true,"server":"ntp.ntsc.ac.cn","elevated":true}}
```
错误:`503` NTP 不可达或提权失败。

### 11.3 授时状态
`POST /api/system/sync_status`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"last_sync":"2026-08-08T02:00:00","offset_ms":-120,"auto_elevate":true}}
```

### 11.4 加密开关(AES-256)
`POST /api/system/aes_status`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"enabled":false,"has_key":false}}
```

`POST /api/system/aes_enable`
```json
{"passphrase":"用户口令(可选,用于派生保护密钥)"}
```
> 开启后敏感字段加密存储;首次生成 `data/secret.key`。
响应:
```json
{"code":200,"msg":"ok","data":{"enabled":true,"migrated_fields":12}}
```

`POST /api/system/aes_disable`
```json
{"passphrase":"..."}
```
> 关闭并解密所有敏感字段。

### 11.5 日志查询
`POST /api/system/log/query`
```json
{"level":null,"keyword":null,"source":null,"limit":500,"offset":0}
```
响应:
```json
{"code":200,"msg":"ok","data":{"total":1200,"items":[
  {"id":1,"timestamp":"2026-08-08T02:00:00","level":"INFO","source":"qrz","message":"查询 BA8AQA"}
]}}
```

### 11.6 日志统计
`POST /api/system/log/stats`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"total":1200,"by_level":{"DEBUG":100,"INFO":1000,"WARNING":50,"ERROR":40,"CRITICAL":10}}}
```

### 11.7 备份
`POST /api/system/backup`
```json
{"keep_count":10}
```
响应:
```json
{"code":200,"msg":"ok","data":{"file":"backup_20260808.zip","size":12345}}
```

### 11.8 数据库迁移状态
`POST /api/system/db_status`
```json
{}
```
响应:
```json
{"code":200,"msg":"ok","data":{"schema_version":"1.0","pending_migrations":0}}
```

---

## 12. 限流与错误处理

- 所有接口统一经全局异常处理器返回标准 JSON
- 业务异常:`AppError(code, msg)` 直接抛出
- 关键写操作(清空、删除、安装插件、授权敏感权限)需二次确认字段
- 长耗时操作(LoTW 上传、更新下载、插件调用)走异步任务 + `task_id` 轮询

---

## 13. 接口速查表

| 模块 | 接口 | 说明 |
|------|------|------|
| auth | /api/auth/login | 登录 |
| auth | /api/auth/refresh | 刷新 Token |
| auth | /api/auth/logout | 登出 |
| auth | /api/auth/csrf | 获取 CSRF |
| auth | /api/auth/status | 认证状态 |
| auth | /api/auth/user/* | 用户管理 |
| log | /api/log/list | 日志列表 |
| log | /api/log/get | 获取单条 |
| log | /api/log/add | 新增 |
| log | /api/log/update | 更新 |
| log | /api/log/delete | 删除 |
| log | /api/log/search | 模糊搜索 |
| log | /api/log/stats | 统计 |
| log | /api/log/clear | 清空(管理员) |
| settings | /api/settings/get_all | 全部设置 |
| settings | /api/settings/get | 获取单项 |
| settings | /api/settings/set | 设置单项 |
| settings | /api/settings/set_many | 批量设置 |
| adif | /api/adif/export | 导出 ADIF |
| adif | /api/adif/download | 下载文件 |
| lotw | /api/lotw/find_tqsl | 查找 TQSL |
| lotw | /api/lotw/list_certs | 证书列表 |
| lotw | /api/lotw/upload | 上传 |
| lotw | /api/lotw/progress | 上传进度 |
| qrz | /api/qrz/lookup | 查询呼号 |
| qrz | /api/qrz/set_credential | 配置账号 |
| qrz | /api/qrz/clear_credential | 清除账号 |
| qsl | /api/qsl/save | 保存设计 |
| qsl | /api/qsl/autosave | 自动保存 |
| qsl | /api/qsl/list | 项目列表 |
| qsl | /api/qsl/load | 加载设计 |
| qsl | /api/qsl/delete | 删除 |
| qsl | /api/qsl/export_private | 导出私有格式 |
| qsl | /api/qsl/import_private | 导入私有格式 |
| qsl | /api/qsl/export_public | 导出 PDF/PNG |
| qsl | /api/qsl/download | 下载导出文件 |
| qsl | /api/qsl/upload_asset | 上传素材 |
| qsl | /api/qsl/data_fields | 数据类别列表 |
| plugin | /api/plugin/source/* | 插件源管理 |
| plugin | /api/plugin/source/refresh | 刷新源索引+评级 |
| plugin | /api/plugin/market | 插件市场(含评级) |
| plugin | /api/plugin/install | 安装 |
| plugin | /api/plugin/uninstall | 卸载 |
| plugin | /api/plugin/toggle | 启停 |
| plugin | /api/plugin/installed | 已安装(含评级) |
| plugin | /api/plugin/check_update | 检查更新 |
| plugin | /api/plugin/authorize | 授权敏感权限 |
| plugin | /api/plugin/invoke | 调用插件 |
| plugin | /api/plugin/info | 插件信息(含评级) |
| plugin | /api/plugin/rating | 插件评级详情(只读) |
| plugin | /api/plugin/author_rating | 开发者评级(只读) |
| intertime | /api/intertime/get | 获取配置 |
| intertime | /api/intertime/set | 保存配置 |
| intertime | /api/intertime/test | 立即检测 |
| intertime | /api/intertime/start/stop | 启停轮询 |
| update | /api/update/check | 检查更新 |
| update | /api/update/download | 下载 |
| update | /api/update/progress | 下载进度 |
| update | /api/update/install | 安装 |
| system | /api/system/info | 系统信息 |
| system | /api/system/sync_time | 授时同步 |
| system | /api/system/sync_status | 授时状态 |
| system | /api/system/aes_status/enable/disable | AES 加密 |
| system | /api/system/log/query | 日志查询 |
| system | /api/system/log/stats | 日志统计 |
| system | /api/system/backup | 备份 |
| system | /api/system/db_status | 数据库状态 |

---

*本文档随版本迭代持续更新。接口字段以代码实现为准,如不一致以代码为准并回更本文档。*
