# HamLog QSL 卡片私有格式规范

> HamLog Web · QSL 卡片设计文件 `.hamqsl` 格式规范
> 版本:Schema 1.0 ｜ 主程序 Release 2.0.0
> 仓库:https://github.com/ARPRC-BA8AQA/HamLog
> 配套:[TECHNICAL.md §9](TECHNICAL.md) / [API.md §7](API.md)

---

## 1. 概述

### 1.1 用途
`.hamqsl` 是 HamLog QSL 卡片设计器的**私有工程格式**,用于:
- 保存卡片设计(画布、图层、元素、背景、绑定)
- 跨设备导入/导出,继续编辑
- 与公共格式(PDF/PNG)互转(公共格式可内嵌 `.hamqsl` 元数据以支持回导)

### 1.2 设计原则
- **可读**:JSON 文本格式,便于调试与人工修正
- **自包含**:背景图等资源以 dataurl 内嵌或 asset 引用,导入即还原
- **版本兼容**:带 `schema_version`,新旧版本"能读多少读多少",未知字段忽略,不因新字段缺失而失败
- **绑定优先**:元素文本用占位符绑定数据类别,实现一键填充

### 1.3 文件特征
- 扩展名:`.hamqsl`
- MIME(建议):`application/x-hamlog-qsl+json`
- 编码:UTF-8
- 顶层为 JSON 对象

---

## 2. 顶层结构

```json
{
  "schema_version": "1.0",
  "format": "hamlog-qsl",
  "meta": { ... },
  "canvas": { ... },
  "background": { ... },
  "elements": [ ... ],
  "assets": { ... },
  "guides": [ ... ],
  "history": { ... }
}
```

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `schema_version` | 是 | string | 格式版本,语义化 `MAJOR.MINOR`,当前 `1.0` |
| `format` | 是 | string | 固定 `"hamlog-qsl"`,用于快速识别 |
| `meta` | 否 | object | 元信息(名称、作者、描述、时间戳) |
| `canvas` | 是 | object | 画布尺寸与单位 |
| `background` | 否 | object | 背景配置 |
| `elements` | 是 | array | 图层元素列表(从底层到顶层) |
| `assets` | 否 | object | 资源字典(图片等) |
| `guides` | 否 | array | 辅助参考线 |
| `history` | 否 | object | 编辑历史快照(可选,导入时忽略) |

---

## 3. meta 元信息

```json
"meta": {
  "name": "我的卡片A",
  "author": "BA8AQA",
  "description": "标准 QSL 卡片",
  "created_at": "2026-08-08T02:00:00",
  "updated_at": "2026-08-08T03:00:00",
  "app_version": "Release 2.0.0",
  "tags": ["default", "fm"]
}
```
所有字段可选。`updated_at` 由自动保存(10s)与显式保存更新。

---

## 4. canvas 画布

```json
"canvas": {
  "width": 148,
  "height": 105,
  "unit": "mm",
  "dpi": 300,
  "bleed": 3,
  "orientation": "landscape"
}
```

| 字段 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `width` | 是 | - | 画布宽 |
| `height` | 是 | - | 画布高 |
| `unit` | 否 | `mm` | 单位:`mm` / `px` / `in` / `cm` |
| `dpi` | 否 | 300 | 打印 DPI,影响导出像素 |
| `bleed` | 否 | 0 | 出血量(同 unit) |
| `orientation` | 否 | `landscape` | `landscape` / `portrait`(仅记录,实际由 width/height 决定) |

标准尺寸参考:QSL 常用 148×105mm(A6 横向)。

---

## 5. background 背景

支持纯色、渐变、图片三种类型。

### 5.1 纯色
```json
"background": {"type": "color", "color": "#FFFFFF"}
```

### 5.2 渐变
```json
"background": {
  "type": "gradient",
  "gradient": {
    "direction": "vertical",
    "stops": [
      {"offset": 0.0, "color": "#FFFFFF"},
      {"offset": 1.0, "color": "#E0E0E0"}
    ]
  }
}
```
`direction`: `vertical` / `horizontal` / `diagonal` / `radial`

### 5.3 图片
```json
"background": {
  "type": "image",
  "ref": "asset_bg_001",
  "fit": "cover",
  "opacity": 1.0,
  "position": "center"
}
```
- `ref`:指向 `assets` 中的资源 ID;也可直接用 `"dataurl": "data:image/png;base64,..."` 内嵌
- `fit`: `cover` / `contain` / `stretch` / `tile`
- `opacity`: 0.0 ~ 1.0
- `position`: `center` / `top-left` / ...

---

## 6. elements 元素

`elements` 是数组,**顺序 = 层级(索引 0 在最底层)**。每个元素是对象,公共字段 + 类型专属字段。

### 6.1 公共字段
| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `id` | 是 | string | 元素唯一 ID(同文件内唯一) |
| `type` | 是 | string | 元素类型(见 6.2) |
| `name` | 否 | string | 图层名(显示用) |
| `x` | 是 | number | 左上角 X(画布单位) |
| `y` | 是 | number | 左上角 Y |
| `w` | 是 | number | 宽 |
| `h` | 是 | number | 高 |
| `rotation` | 否 | number | 旋转角度(度,默认 0) |
| `opacity` | 否 | number | 0.0~1.0,默认 1 |
| `visible` | 否 | bool | 默认 true |
| `locked` | 否 | bool | 锁定不可编辑,默认 false |
| `z_index` | 否 | int | 显式层级(覆盖数组顺序,默认按数组) |
| `binding` | 否 | string | 数据绑定 key(见 §7) |
| `style` | 否 | object | 通用样式(边框、阴影等) |

### 6.2 元素类型

#### text 文本
```json
{
  "id": "e1", "type": "text", "name": "对方呼号",
  "x": 10, "y": 20, "w": 80, "h": 12,
  "rotation": 0, "opacity": 1, "visible": true, "locked": false,
  "binding": "log.callsign",
  "content": "{callsign}",
  "style": {
    "font_family": "Microsoft YaHei",
    "font_size": 14,
    "font_weight": "bold",
    "color": "#000000",
    "align": "left",
    "valign": "top",
    "line_height": 1.2,
    "letter_spacing": 0
  }
}
```
- `content`:文本内容,可含占位符(见 §7)
- 填充时:占位符替换为实际值;无绑定时按字面量输出

#### rect 矩形
```json
{
  "id": "e2", "type": "rect",
  "x": 5, "y": 5, "w": 138, "h": 95,
  "style": {
    "fill": "#FFFFFF",
    "fill_opacity": 0.5,
    "border_color": "#333333",
    "border_width": 1,
    "border_style": "solid",
    "radius": 4,
    "shadow": {"x":2,"y":2,"blur":4,"color":"#00000033"}
  }
}
```

#### circle / ellipse 圆/椭圆
```json
{
  "id": "e3", "type": "circle",
  "x": 100, "y": 10, "w": 30, "h": 30,
  "style": {"fill": "#FF0000", "border_color":"#000", "border_width":1}
}
```
> 用 `w==h` 表示正圆;`w!=h` 表示椭圆。

#### line 线条
```json
{
  "id": "e4", "type": "line",
  "x": 10, "y": 50, "w": 128, "h": 0,
  "style": {"border_color": "#000000", "border_width": 1, "border_style": "solid"}
}
```
> 线条用 x/y/w/h 表示起止;`h=0` 水平线,`w=0` 竖线。带 `rotation` 可画斜线。

#### image 图片
```json
{
  "id": "e5", "type": "image",
  "x": 110, "y": 70, "w": 30, "h": 30,
  "ref": "asset_logo_001",
  "fit": "contain",
  "opacity": 1.0
}
```
- `ref` 指向 `assets`,或 `dataurl` 内嵌
- `fit`: `cover` / `contain` / `stretch`

#### qrcode 二维码
```json
{
  "id": "e6", "type": "qrcode",
  "x": 120, "y": 5, "w": 20, "h": 20,
  "binding": "log.callsign",
  "content": "{callsign}",
  "style": {"fg_color": "#000000", "bg_color": "#FFFFFF", "ecc_level": "M"}
}
```
- `content`:二维码内容,可含占位符
- `ecc_level`:纠错等级 `L`/`M`/`Q`/`H`,默认 `M`
- 导出时渲染为图片

#### group 组(可选)
```json
{
  "id": "g1", "type": "group",
  "x": 10, "y": 10, "w": 60, "h": 40,
  "children": ["e1","e2"]
}
```
> 组引用子元素 id,变换作用于整组。v1.0 可选支持。

### 6.3 style 通用字段
| 字段 | 适用 | 说明 |
|------|------|------|
| `fill` | rect/circle | 填充色 |
| `fill_opacity` | rect/circle | 填充透明度 |
| `border_color` | 多数 | 边框色 |
| `border_width` | 多数 | 边框宽 |
| `border_style` | 多数 | `solid`/`dashed`/`dotted` |
| `radius` | rect | 圆角 |
| `shadow` | 多数 | 阴影 `{x,y,blur,color}` |
| `font_*` | text/qrcode | 字体族 |
| `color` | text | 文字色 |
| `align`/`valign` | text | 对齐 |

---

## 7. 数据绑定与占位符

### 7.1 占位符语法
文本类元素的 `content` 中用 `{字段key}` 表示占位符,填充时替换:
- `content`: `"QSO: {log.callsign} {log.date}"`
- 填充后:`"QSO: BA8AQA 2026-08-08"`

### 7.2 绑定 key
元素 `binding` 字段指定该元素的主绑定(用于"一键填充"高亮与默认填充来源)。key 命名空间:

| 命名空间 | 示例 | 说明 |
|----------|------|------|
| `log.*` | `log.callsign` `log.date` `log.freq` `log.mode` `log.rst` `log.qth` `log.remarks` | 通联记录字段 |
| `station.*` | `station.my_callsign` `station.my_name` `station.my_qth` `station.my_grid` | 本台信息 |
| `qsl.*` | `qsl.rx_date` `qsl.send_date` | QSL 收发日期 |
| `meta.*` | `meta.export_date` `meta.export_time` | 导出时的时间 |
| `const.*` | `const.app_name` | 常量 |

> 完整可用字段由 `POST /api/qsl/data_fields` 返回,插件也可扩展(见 §10)。

### 7.3 填充规则
- 一键填充时,主程序遍历所有元素,按 `binding` 与 `content` 占位符替换
- 未提供数据的占位符保留原样或替换为空(由导出选项 `keep_placeholder` 控制)
- 二维码元素:填充后内容生成二维码
- 无 `binding` 的纯文本元素不参与填充

### 7.4 格式化器(可选,v1.0 可选支持)
占位符可带格式化器:`{log.date|date:YYYY/MM/DD}`、`{log.freq|upper}`。读取器遇到不识别的格式化器时按原值输出。

---

## 8. assets 资源字典

集中存放图片等二进制资源,元素通过 `ref` 引用,避免重复内嵌。

```json
"assets": {
  "asset_bg_001": {
    "type": "image",
    "mime": "image/png",
    "dataurl": "data:image/png;base64,iVBORw0KG..."
  },
  "asset_logo_001": {
    "type": "image",
    "mime": "image/jpeg",
    "dataurl": "data:image/jpeg;base64,..."
  }
}
```
- `dataurl` 必填(保证自包含);未来可扩展 `file_ref` 指向外部文件
- 同一资源多元素引用只存一份
- 导入时自动还原

---

## 9. guides 参考线(可选)

```json
"guides": [
  {"orientation": "vertical", "position": 74},
  {"orientation": "horizontal", "position": 52.5}
]
```
仅设计辅助,不影响导出。

---

## 10. 版本兼容与迁移

### 10.1 schema_version 机制
- 顶层 `schema_version` 标识格式版本(语义化,当前 `1.0`)
- 读取器按主版本号选择迁移器
- 同一主版本内向后兼容:新字段对旧读取器无害(忽略),旧文件对新读取器无害(缺省)

### 10.2 读取策略("能读多少读多少")
加载 `.hamqsl` 时遵循宽松读取原则:
1. 解析 JSON 失败 → 报错并提示文件损坏
2. `schema_version` 缺失 → 按 `1.0` 处理并提示
3. 未知字段 → **忽略**,不报错
4. 必填字段缺失 → 用默认值,继续加载
5. 元素类型未知 → 保留原始数据,标记为"未知元素",设计器中以占位框显示,导出时跳过
6. 资源引用缺失 → 显示占位图,不阻断

### 10.3 迁移器
主程序内置迁移链:
```
旧 schema_version → migrate_v0_x_to_1_0(data) → 1.0 内存结构
```
- 迁移只增不删:保留原始字段副本 `_legacy`,便于回写兼容
- 迁移失败时回退到"宽松读取",保证可用

### 10.4 写入策略
- 保存/自动保存始终写当前主程序支持的最新 `schema_version`
- 可选写入 `_legacy` 字段以兼容旧版本(默认关闭,避免文件膨胀)

---

## 11. 跨设备导入导出

### 11.1 导出私有格式
- `POST /api/qsl/export_private` → 返回 `.hamqsl` 文件
- 文件自包含(资源 dataurl 内嵌),单文件即可迁移
- 文件名建议:`<项目名>_<schema_version>.hamqsl`

### 11.2 导入私有格式
- `POST /api/qsl/import_private`(multipart `file`)→ 自动迁移 + 还原资源
- 返回新项目 ID + 迁移标记:
```json
{"code":200,"msg":"导入成功","data":{
  "id":"proj_002","name":"我的卡片A","migrated":true,"from_schema":"0.9","to_schema":"1.0","warnings":["2 个未知元素已保留为占位"]}}
```

### 11.3 公共格式回导
- 导出 PDF/PNG 时,可在文件元数据中内嵌 `.hamqsl` JSON(如 PDF 的 XMP 元数据或 PNG 的 tEXt chunk `hamqsl=`)
- 回导时若检测到内嵌 `.hamqsl`,可还原为可编辑工程
- 未内嵌的公共格式无法回导(只读)

---

## 12. 自动保存

- 前端每 **10s** 检测 dirty 标志,有更新则 `POST /api/qsl/autosave`
- 后端落盘到 `data/qsl/projects/<id>.hamqsl`,并更新数据库 `qsl_projects.updated_at`
- 自动保存写当前 schema_version
- 崩溃恢复:重新打开项目时检测 `updated_at` 与内存态,提示恢复

---

## 13. 安全与体积

- `dataurl` 资源建议压缩(JPEG/PNG 优化),单文件建议 < 10MB
- 导入时校验 JSON 大小与资源数量上限(可配,默认 50 个资源)
- 禁止 `dataurl` 之外的 `javascript:` / 外部 URL 引用(防 XSS)
- 文件来自外部导入,解析在沙箱内进行,异常不致主程序崩溃

---

## 14. 完整示例(.hamqsl)

```json
{
  "schema_version": "1.0",
  "format": "hamlog-qsl",
  "meta": {
    "name": "标准 QSL 卡片",
    "author": "BA8AQA",
    "updated_at": "2026-08-08T03:00:00",
    "app_version": "Release 2.0.0"
  },
  "canvas": {"width": 148, "height": 105, "unit": "mm", "dpi": 300, "bleed": 3},
  "background": {"type": "color", "color": "#FFFFFF"},
  "elements": [
    {
      "id": "border", "type": "rect", "name": "边框",
      "x": 4, "y": 4, "w": 140, "h": 97,
      "style": {"fill": "transparent", "border_color": "#333333", "border_width": 1, "radius": 4}
    },
    {
      "id": "title", "type": "text", "name": "标题",
      "x": 10, "y": 8, "w": 128, "h": 8,
      "content": "QSL CARD",
      "style": {"font_family": "Arial", "font_size": 16, "font_weight": "bold", "color": "#333333", "align": "center"}
    },
    {
      "id": "call", "type": "text", "name": "对方呼号",
      "x": 10, "y": 22, "w": 90, "h": 14,
      "binding": "log.callsign",
      "content": "{log.callsign}",
      "style": {"font_family": "Microsoft YaHei", "font_size": 24, "font_weight": "bold", "color": "#000000", "align": "left"}
    },
    {
      "id": "date", "type": "text", "name": "日期",
      "x": 10, "y": 40, "w": 60, "h": 8,
      "binding": "log.date",
      "content": "Date: {log.date}",
      "style": {"font_size": 11, "color": "#333333"}
    },
    {
      "id": "freq", "type": "text", "name": "频率",
      "x": 75, "y": 40, "w": 60, "h": 8,
      "binding": "log.freq",
      "content": "Freq: {log.freq}",
      "style": {"font_size": 11, "color": "#333333"}
    },
    {
      "id": "rst", "type": "text", "name": "信号",
      "x": 10, "y": 50, "w": 60, "h": 8,
      "binding": "log.rst",
      "content": "RST: {log.rst}",
      "style": {"font_size": 11, "color": "#333333"}
    },
    {
      "id": "mycall", "type": "text", "name": "本台呼号",
      "x": 10, "y": 88, "w": 90, "h": 8,
      "binding": "station.my_callsign",
      "content": "73 de {station.my_callsign}",
      "style": {"font_size": 12, "font_weight": "bold", "color": "#000000"}
    },
    {
      "id": "qr", "type": "qrcode", "name": "呼号二维码",
      "x": 120, "y": 75, "w": 18, "h": 18,
      "binding": "log.callsign",
      "content": "{log.callsign}",
      "style": {"fg_color": "#000000", "bg_color": "#FFFFFF", "ecc_level": "M"}
    }
  ],
  "assets": {},
  "guides": [
    {"orientation": "vertical", "position": 74},
    {"orientation": "horizontal", "position": 52.5}
  ]
}
```

---

## 15. 字段速查表

| 顶层字段 | 必填 | 说明 |
|----------|------|------|
| `schema_version` | 是 | `1.0` |
| `format` | 是 | `hamlog-qsl` |
| `meta` | 否 | 元信息 |
| `canvas` | 是 | 画布 |
| `background` | 否 | 背景 |
| `elements` | 是 | 图层元素数组 |
| `assets` | 否 | 资源字典 |
| `guides` | 否 | 参考线 |
| `history` | 否 | 编辑历史(导入忽略) |

| 元素 type | 必填专属字段 |
|-----------|-------------|
| `text` | `content`(可含占位符) |
| `rect` | - |
| `circle` | - |
| `line` | - |
| `image` | `ref` 或 `dataurl`,`fit` |
| `qrcode` | `content`,`ecc_level` |
| `group` | `children`(元素 id 数组) |

---

## 16. 与 API 的对应

| 操作 | API |
|------|-----|
| 保存 | `POST /api/qsl/save`(content 即本文档结构) |
| 自动保存 | `POST /api/qsl/autosave` |
| 加载 | `POST /api/qsl/load`(返回 content) |
| 导出私有 | `POST /api/qsl/export_private` |
| 导入私有 | `POST /api/qsl/import_private` |
| 导出 PDF/PNG | `POST /api/qsl/export_public` + 一键填充 data |
| 可绑定字段 | `POST /api/qsl/data_fields` |

---

*本规范随 HamLog 演进持续更新。schema_version 升级时会在本文档顶部注明变更摘要。*
