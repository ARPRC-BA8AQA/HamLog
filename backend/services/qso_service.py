"""Validation and UTC normalization for QSO records."""

from datetime import date, datetime, timezone, timedelta
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.services.radio import frequency_to_band, normalize_band, parse_frequency_mhz


CALLSIGN_RE = re.compile(r"^[A-Z0-9]{1,10}(?:/[A-Z0-9]{1,10})*$")
DATE_KEYS = ("Year", "Month", "Day")
QSO_FIELDS = (
    "Callsign", "Freq", "Year", "Month", "Day", "Time", "Mode",
    "Power_self", "Power_side", "Rst_self", "Rst_side", "QTH", "Device",
    "QSL_RX", "QSL_SEND", "Remarks",
)


def parse_iso_date(value, field="date"):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field} 必须是 YYYY-MM-DD")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD") from exc


def row_date(row):
    values = [row.get(key) if hasattr(row, "get") else row[key] for key in DATE_KEYS]
    if any(value is None for value in values):
        return None
    try:
        return date(int(values[0]), int(values[1]), int(values[2]))
    except (TypeError, ValueError):
        return None


def normalize_time(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Time 必须是 HHMM 或 HHMMSS")
    digits = value.strip().replace(":", "")
    if len(digits) not in (4, 6) or not digits.isdigit():
        raise ValueError("Time 必须是 HHMM 或 HHMMSS")
    hour, minute = int(digits[:2]), int(digits[2:4])
    second = int(digits[4:]) if len(digits) == 6 else 0
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("Time 超出有效范围")
    return digits


def _timezone(value):
    if value in (None, "", "UTC", "Z"):
        return timezone.utc
    if isinstance(value, timezone):
        return value
    text = str(value).strip()
    offset = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", text)
    if offset:
        minutes = int(offset.group(2)) * 60 + int(offset.group(3))
        if minutes > 23 * 60 + 59:
            raise ValueError("timezone 偏移非法")
        if offset.group(1) == "-":
            minutes = -minutes
        return timezone(timedelta(minutes=minutes))
    try:
        return ZoneInfo(text)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone 不存在") from exc


def _date_values(data):
    present = [key in data and data.get(key) not in (None, "") for key in DATE_KEYS]
    if any(present) and not all(present):
        raise ValueError("Year、Month、Day 必须同时提供")
    if not any(present):
        return None
    try:
        return date(int(data["Year"]), int(data["Month"]), int(data["Day"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("日期无效") from exc


def normalize_qso(data, input_timezone="UTC", require_datetime_pair=True):
    if not isinstance(data, dict):
        raise ValueError("日志必须是对象")
    call = str(data.get("Callsign", "")).strip().upper()
    if not call:
        raise ValueError("Callsign 不能为空")
    if len(call) > 20 or not CALLSIGN_RE.fullmatch(call) or not any(char.isdigit() for char in call) or not any(char.isalpha() for char in call):
        raise ValueError("Callsign 格式非法")

    result = {key: data.get(key) for key in QSO_FIELDS if key in data}
    result["Callsign"] = call
    if "Freq" in result and result["Freq"] not in (None, ""):
        if parse_frequency_mhz(result["Freq"]) is None:
            raise ValueError("Freq 格式非法")
        result["Freq"] = str(result["Freq"]).strip()
    if "Mode" in result and result["Mode"] not in (None, ""):
        result["Mode"] = str(result["Mode"]).strip().upper()

    contact_date = _date_values(data)
    contact_time = normalize_time(data.get("Time")) if "Time" in data else None
    if require_datetime_pair and (contact_date is None) != (contact_time is None):
        raise ValueError("日期和 Time 必须同时提供")
    if contact_date and contact_time:
        tz_value = data.get("utc_offset") if data.get("utc_offset") is not None else data.get("timezone", input_timezone)
        local = datetime.combine(contact_date, datetime.strptime(contact_time, "%H%M" if len(contact_time) == 4 else "%H%M%S").time(), tzinfo=_timezone(tz_value))
        utc = local.astimezone(timezone.utc)
        result.update({"Year": utc.year, "Month": utc.month, "Day": utc.day})
        result["Time"] = utc.strftime("%H%M" if len(contact_time) == 4 else "%H%M%S")
    else:
        if contact_date:
            result.update({"Year": contact_date.year, "Month": contact_date.month, "Day": contact_date.day})
        if "Time" in data:
            result["Time"] = contact_time
    return result


def filter_rows(rows, date_from=None, date_to=None, band=None, mode=None):
    start = parse_iso_date(date_from, "date_from") if date_from else None
    end = parse_iso_date(date_to, "date_to") if date_to else None
    if start and end and start > end:
        raise ValueError("date_from 不能晚于 date_to")
    wanted_band = normalize_band(band) if band not in (None, "") else None
    if band not in (None, "") and wanted_band is None:
        raise ValueError("band 非法")
    wanted_mode = str(mode).strip().upper() if mode not in (None, "") else None
    result = []
    for row in rows:
        value = row_date(row)
        if start and (value is None or value < start):
            continue
        if end and (value is None or value > end):
            continue
        if wanted_band and frequency_to_band(row.get("Freq")) != wanted_band:
            continue
        row_mode = str(row.get("Mode") or "").strip().upper()
        if wanted_mode and row_mode != wanted_mode:
            continue
        result.append(row)
    return result
