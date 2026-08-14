from copy import deepcopy
import re

MAX_CONTENT_BYTES = 10 * 1024 * 1024
MAX_ASSETS = 50
ALLOWED_UNITS = {"mm", "px", "in", "cm"}
ALLOWED_ELEMENT_TYPES = {"text", "rect", "circle", "ellipse", "line", "image", "qrcode", "group"}

DEFAULT_CONTENT = {
    "schema_version": "1.0", "format": "hamlog-qsl",
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
