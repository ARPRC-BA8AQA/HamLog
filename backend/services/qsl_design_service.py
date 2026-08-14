from copy import deepcopy
import base64
import binascii
import re

MAX_CONTENT_BYTES = 10 * 1024 * 1024
MAX_ASSETS = 50
ALLOWED_UNITS = {"mm", "px", "in", "cm"}
ALLOWED_ELEMENT_TYPES = {"text", "rect", "circle", "ellipse", "line", "image", "qrcode", "group"}
DATAURL = re.compile(r"^data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/=\r\n]+)$", re.IGNORECASE)

DEFAULT_CONTENT = {
    "schema_version": "1.0", "format": "hamlog-qsl",
    "meta": {},
    "canvas": {"width": 148, "height": 105, "unit": "mm"},
    "background": {"type": "color", "color": "#FFFFFF"},
    "elements": [], "assets": {}, "guides": [],
}

def normalize(content):
    value = deepcopy(content) if isinstance(content, dict) else {}
    result = deepcopy(DEFAULT_CONTENT)
    result.update({key: value[key] for key in DEFAULT_CONTENT if key in value})
    result["schema_version"] = "1.0"
    result["format"] = "hamlog-qsl"
    if not isinstance(result["canvas"], dict): result["canvas"] = deepcopy(DEFAULT_CONTENT["canvas"])
    if not isinstance(result["elements"], list): result["elements"] = []
    if not isinstance(result["assets"], dict): result["assets"] = {}
    result["assets"] = {key: asset for key, asset in result["assets"].items() if isinstance(key, str) and isinstance(asset, dict)}
    if len(result["assets"]) > MAX_ASSETS:
        raise ValueError("资源数量超过限制")
    canvas = result["canvas"]
    if not isinstance(canvas.get("width"), (int, float)) or not isinstance(canvas.get("height"), (int, float)):
        raise ValueError("canvas width/height 必须是数字")
    if canvas.get("unit", "mm") not in ALLOWED_UNITS:
        raise ValueError("canvas unit 不支持")
    if not 0 < float(canvas["width"]) <= 5000 or not 0 < float(canvas["height"]) <= 5000:
        raise ValueError("canvas width/height 超出范围")
    dpi = canvas.get("dpi", 300)
    if not isinstance(dpi, (int, float)) or not 36 <= float(dpi) <= 1200:
        raise ValueError("canvas dpi 必须在 36 到 1200 之间")
    for asset_id, asset in result["assets"].items():
        dataurl = asset.get("dataurl")
        match = DATAURL.fullmatch(dataurl or "")
        if asset.get("type", "image") != "image" or not match:
            raise ValueError(f"资源 {asset_id} 必须是自包含图片 dataurl")
        try:
            decoded = base64.b64decode(match.group(2), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"资源 {asset_id} Base64 无效") from exc
        if len(decoded) > 8 * 1024 * 1024:
            raise ValueError(f"资源 {asset_id} 超过 8MB 限制")
    elements = []
    seen = set()
    for element in result["elements"]:
        if not isinstance(element, dict):
            continue
        item = deepcopy(element)
        item.setdefault("id", "element-" + str(len(elements) + 1))
        if item["id"] in seen:
            item["id"] += "-" + str(len(elements) + 1)
        seen.add(item["id"])
        if item.get("type") not in ALLOWED_ELEMENT_TYPES:
            item["unknown_type"] = item.get("type")
            item["type"] = "unknown"
        if item.get("type") == "image" and item.get("dataurl"):
            direct = DATAURL.fullmatch(item["dataurl"])
            if not direct:
                raise ValueError(f"元素 {item['id']} 包含非法图片 dataurl")
        if item.get("type") == "image" and not item.get("dataurl") and item.get("ref") not in result["assets"]:
            item["missing_asset"] = True
        elements.append(item)
    result["elements"] = elements
    serialized_size = len(content_json(result).encode("utf-8"))
    if serialized_size > MAX_CONTENT_BYTES:
        raise ValueError("QSL 工程文件超过 10MB 限制")
    return result


def content_json(content):
    import json
    return json.dumps(content, ensure_ascii=False, separators=(",", ":"))


def import_content(raw):
    import json
    if len(raw) > MAX_CONTENT_BYTES:
        raise ValueError("QSL 文件超过 10MB 限制")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("QSL 文件不是有效 JSON") from exc
    return normalize(value)
