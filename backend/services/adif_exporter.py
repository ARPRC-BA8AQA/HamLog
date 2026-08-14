"""ADIF 3.1 export with HamLog's shared filter and radio semantics."""

from dataclasses import dataclass
from datetime import date, datetime
import re

from backend.services.qso_service import filter_rows, normalize_time, row_date
from backend.services.radio import frequency_to_band, normalize_mode, parse_frequency_mhz


ADIF_VERSION = "3.1.0"
PROGRAM_ID = "HamLog"
PROGRAM_VERSION = "2.0.0"


@dataclass
class ExportResult:
    content: bytes
    total: int
    exported: int
    skipped: int
    errors: list


def _field(name, value, data_type=None):
    if value is None or value == "":
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    type_suffix = f":{data_type}" if data_type else ""
    return f"<{name}:{len(text)}{type_suffix}>{text}"


def _frequency(value):
    frequency = parse_frequency_mhz(value)
    if frequency is None:
        return None
    return f"{frequency:.6f}".rstrip("0").rstrip(".")


def _qsl_status(value):
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().upper()
    if text in {"Y", "YES", "TRUE", "1", "已收到", "已发送"}:
        return "Y"
    if text in {"N", "NO", "FALSE", "0", "未收到", "未发送"}:
        return "N"
    return None


def _qsl_date(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y%m%d")
    text = str(value or "").strip().replace("-", "")
    if len(text) == 8 and text.isdigit():
        try:
            datetime.strptime(text, "%Y%m%d")
        except ValueError:
            return None
        return text
    return None


def _power(value):
    if value in (None, ""):
        return None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(?:W|WATTS?)?\s*", str(value), re.IGNORECASE)
    return match.group(1) if match else None


class ADIFExporter:
    def export(self, rows, *, date_from=None, date_to=None, band=None, mode=None, station_callsign=None):
        source = [dict(row) for row in rows]
        selected = filter_rows(source, date_from, date_to, band, mode)
        header = " ".join(filter(None, (
            _field("ADIF_VER", ADIF_VERSION),
            _field("PROGRAMID", PROGRAM_ID),
            _field("PROGRAMVERSION", PROGRAM_VERSION),
            "<EOH>",
        )))
        lines = [header]
        errors = []
        exported = 0
        station = str(station_callsign or "").strip().upper() or None
        if station and (len(station) > 20 or not re.fullmatch(r"[A-Z0-9]+(?:/[A-Z0-9]+)*", station)):
            raise ValueError("station_callsign 格式非法")
        for row in selected:
            record_id = row.get("id", "?")
            contact_date = row_date(row)
            try:
                contact_time = normalize_time(row.get("Time"))
            except ValueError:
                contact_time = None
            record_band = frequency_to_band(row.get("Freq"))
            record_mode, submode = normalize_mode(row.get("Mode"))
            missing = []
            if not row.get("Callsign"):
                missing.append("CALL")
            if not contact_date:
                missing.append("QSO_DATE")
            if not contact_time:
                missing.append("TIME_ON")
            if not record_band:
                missing.append("BAND")
            if not record_mode:
                missing.append("MODE")
            if missing:
                errors.append({"id": record_id, "error": "missing or invalid " + ", ".join(missing)})
                continue
            values = (
                ("CALL", str(row["Callsign"]).strip().upper(), None),
                ("QSO_DATE", contact_date.strftime("%Y%m%d"), "D"),
                ("TIME_ON", contact_time, "T"),
                ("BAND", record_band, None),
                ("FREQ", _frequency(row.get("Freq")), "N"),
                ("MODE", record_mode, None),
                ("SUBMODE", submode, None),
                ("RST_SENT", row.get("Rst_self"), None),
                ("RST_RCVD", row.get("Rst_side"), None),
                ("TX_PWR", _power(row.get("Power_self")), "N"),
                ("QTH", row.get("QTH"), None),
                ("MY_RIG", row.get("Device"), None),
                ("QSL_RCVD", _qsl_status(row.get("QSL_RX")) or ("Y" if _qsl_date(row.get("QSL_RX")) else None), None),
                ("QSLRDATE", _qsl_date(row.get("QSL_RX")), "D"),
                ("QSL_SENT", _qsl_status(row.get("QSL_SEND")) or ("Y" if _qsl_date(row.get("QSL_SEND")) else None), None),
                ("QSLSDATE", _qsl_date(row.get("QSL_SEND")), "D"),
                ("COMMENT", row.get("Remarks"), None),
                ("STATION_CALLSIGN", station, None),
            )
            fields = [_field(name, value, data_type) for name, value, data_type in values]
            lines.append(" ".join(field for field in fields if field) + " <EOR>")
            exported += 1
        content = ("\r\n".join(lines) + "\r\n").encode("utf-8")
        return ExportResult(content, len(selected), exported, len(selected) - exported, errors)
