import base64
import io
import re
from pathlib import Path

import qrcode
from PIL import Image, ImageColor, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.-]+)(?:\|[^{}]+)?\}")
UNIT_TO_INCH = {"mm": 1 / 25.4, "cm": 1 / 2.54, "in": 1, "px": 1 / 96}


def _number(value, default=0):
    return float(value) if isinstance(value, (int, float)) else float(default)


def _color(value, default="#000000"):
    try:
        return ImageColor.getrgb(value or default)
    except (ValueError, TypeError):
        return ImageColor.getrgb(default)


def _fill(value, default="#000000", opacity=1):
    rgb = _color(value, default)
    return (*rgb, max(0, min(255, round(_number(opacity, 1) * 255))))


def _dataurl(value):
    if not isinstance(value, str) or not value.startswith("data:image/") or "," not in value:
        return None
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        return None


def _font(size):
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), max(6, round(size)))
            except OSError:
                pass
    return ImageFont.load_default()


def bind_text(value, data, keep_placeholder=False):
    text = str(value or "")
    def replace(match):
        key = match.group(1)
        return str(data[key]) if key in data and data[key] is not None else (match.group(0) if keep_placeholder else "")
    return PLACEHOLDER.sub(replace, text)


def _asset(content, element):
    direct = element.get("dataurl")
    if direct:
        return _dataurl(direct)
    asset = content.get("assets", {}).get(element.get("ref"), {})
    return _dataurl(asset.get("dataurl")) if isinstance(asset, dict) else None


def render_png(content, data=None, dpi=None, keep_placeholder=False):
    data = data or {}
    canvas = content.get("canvas", {})
    unit = canvas.get("unit", "mm")
    scale = (int(dpi or canvas.get("dpi") or 300) * UNIT_TO_INCH.get(unit, UNIT_TO_INCH["mm"]))
    width = max(1, min(10000, round(_number(canvas.get("width"), 148) * scale)))
    height = max(1, min(10000, round(_number(canvas.get("height"), 105) * scale)))
    image = Image.new("RGBA", (width, height), "white")
    draw = ImageDraw.Draw(image, "RGBA")

    background = content.get("background") or {}
    if background.get("type") == "color":
        draw.rectangle((0, 0, width, height), fill=_fill(background.get("color"), "#ffffff"))
    elif background.get("type") == "image":
        bg = _asset(content, background)
        if bg:
            image.alpha_composite(bg.resize((width, height), Image.Resampling.LANCZOS))

    for element in content.get("elements", []):
        if not isinstance(element, dict) or element.get("visible", True) is False or element.get("type") in {"group", "unknown"}:
            continue
        x, y = round(_number(element.get("x")) * scale), round(_number(element.get("y")) * scale)
        w, h = round(_number(element.get("w")) * scale), round(_number(element.get("h")) * scale)
        style = element.get("style") if isinstance(element.get("style"), dict) else {}
        opacity = _number(element.get("opacity"), 1)
        kind = element.get("type")
        border_width = max(1, round(_number(style.get("border_width"), 1) * max(scale / 4, 1)))
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        element_draw = ImageDraw.Draw(layer, "RGBA")
        if kind == "rect":
            element_draw.rounded_rectangle((x, y, x + w, y + h), radius=max(0, round(_number(style.get("radius")) * scale)), fill=_fill(style.get("fill"), "#ffffff", _number(style.get("fill_opacity"), opacity)), outline=_fill(style.get("border_color"), "#000000", opacity), width=border_width)
        elif kind in {"circle", "ellipse"}:
            element_draw.ellipse((x, y, x + w, y + h), fill=_fill(style.get("fill"), "#ffffff", _number(style.get("fill_opacity"), opacity)), outline=_fill(style.get("border_color"), "#000000", opacity), width=border_width)
        elif kind == "line":
            element_draw.line((x, y, x + w, y + h), fill=_fill(style.get("border_color"), "#000000", opacity), width=border_width)
        elif kind == "text":
            text = bind_text(element.get("content", element.get("text", "")), data, keep_placeholder)
            font = _font(_number(style.get("font_size"), 12) * scale / 2.83465)
            spacing = max(1, round(_number(style.get("line_height"), 1.2) * 2))
            box = element_draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
            text_width, text_height = box[2] - box[0], box[3] - box[1]
            text_x = x + (w - text_width if style.get("align") == "right" else (w - text_width) / 2 if style.get("align") == "center" else 0)
            text_y = y + (h - text_height if style.get("valign") == "bottom" else (h - text_height) / 2 if style.get("valign") in {"middle", "center"} else 0)
            element_draw.multiline_text((text_x, text_y), text, font=font, fill=_fill(style.get("color"), "#000000", opacity), spacing=spacing, align=style.get("align", "left"))
        elif kind == "image":
            source = _asset(content, element)
            if source and w > 0 and h > 0:
                if element.get("fit") == "stretch":
                    source = source.resize((w, h), Image.Resampling.LANCZOS)
                else:
                    source.thumbnail((w, h), Image.Resampling.LANCZOS)
                target = Image.new("RGBA", (max(w, 1), max(h, 1)))
                target.alpha_composite(source, ((w - source.width) // 2, (h - source.height) // 2))
                layer.alpha_composite(target, (x, y))
        elif kind == "qrcode" and w > 0 and h > 0:
            value = bind_text(element.get("content", ""), data, keep_placeholder)
            code = qrcode.make(value or " ").convert("RGBA").resize((w, h), Image.Resampling.NEAREST)
            layer.alpha_composite(code, (x, y))
        rotation = _number(element.get("rotation"), 0) % 360
        if rotation:
            layer = layer.rotate(-rotation, resample=Image.Resampling.BICUBIC, center=(x + w / 2, y + h / 2), expand=False)
        image.alpha_composite(layer)

    output = io.BytesIO()
    image.convert("RGB").save(output, format="PNG", dpi=(int(dpi or canvas.get("dpi") or 300),) * 2, optimize=True)
    return output.getvalue(), (width, height)


def render_pdf(content, data=None, dpi=None, keep_placeholder=False):
    png, _ = render_png(content, data, dpi, keep_placeholder)
    canvas_data = content.get("canvas", {})
    unit = canvas_data.get("unit", "mm")
    width_pt = _number(canvas_data.get("width"), 148) * UNIT_TO_INCH.get(unit, UNIT_TO_INCH["mm"]) * 72
    height_pt = _number(canvas_data.get("height"), 105) * UNIT_TO_INCH.get(unit, UNIT_TO_INCH["mm"]) * 72
    output = io.BytesIO()
    pdf = Canvas(output, pagesize=(width_pt, height_pt), pageCompression=1)
    pdf.drawImage(ImageReader(io.BytesIO(png)), 0, 0, width=width_pt, height=height_pt, preserveAspectRatio=False, mask="auto")
    pdf.setTitle(str((content.get("meta") or {}).get("name") or "HamLog QSL Card"))
    pdf.showPage(); pdf.save()
    return output.getvalue()
