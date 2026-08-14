"""Radio-specific normalization shared by logging and ADIF export."""

import re


BAND_RANGES = (
    ("160m", 1.8, 2.0),
    ("80m", 3.5, 4.0),
    ("60m", 5.25, 5.45),
    ("40m", 7.0, 7.3),
    ("30m", 10.1, 10.15),
    ("20m", 14.0, 14.35),
    ("17m", 18.068, 18.168),
    ("15m", 21.0, 21.45),
    ("12m", 24.89, 24.99),
    ("10m", 28.0, 29.7),
    ("6m", 50.0, 54.0),
    ("4m", 70.0, 70.5),
    ("2m", 144.0, 148.0),
    ("1.25m", 222.0, 225.0),
    ("70cm", 420.0, 450.0),
    ("33cm", 902.0, 928.0),
    ("23cm", 1240.0, 1300.0),
    ("13cm", 2300.0, 2450.0),
    ("6cm", 5650.0, 5925.0),
    ("3cm", 10000.0, 10500.0),
)

_FREQUENCY_RE = re.compile(
    r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(ghz|mhz|khz|hz)?\s*$",
    re.IGNORECASE,
)

_BAND_ALIASES = {
    "160": "160m",
    "80": "80m",
    "60": "60m",
    "40": "40m",
    "30": "30m",
    "20": "20m",
    "17": "17m",
    "15": "15m",
    "12": "12m",
    "10": "10m",
    "6": "6m",
    "4": "4m",
    "2": "2m",
    "1.25": "1.25m",
    "70": "70cm",
    "33": "33cm",
    "23": "23cm",
    "13": "13cm",
    "6cm": "6cm",
    "3cm": "3cm",
}

_MODE_ALIASES = {
    "USB": ("SSB", "USB"),
    "LSB": ("SSB", "LSB"),
    "FT8": ("MFSK", "FT8"),
    "FT4": ("MFSK", "FT4"),
    "JS8": ("MFSK", "JS8"),
    "DIGITAL": ("DIGI", None),
    "DATA": ("DIGI", None),
    "PSK31": ("PSK", "PSK31"),
    "PSK63": ("PSK", "PSK63"),
    "JT9": ("JT9", None),
    "JT65": ("JT65", None),
}


def parse_frequency_mhz(value):
    """Return a frequency in MHz, accepting common ADIF/UI formats."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        unit = None
    else:
        match = _FREQUENCY_RE.match(str(value))
        if not match:
            return None
        number = float(match.group(1))
        unit = (match.group(2) or "").lower()
    if number <= 0:
        return None
    if unit == "ghz":
        number *= 1000
    elif unit == "khz":
        number /= 1000
    elif unit == "hz":
        number /= 1_000_000
    return number


def frequency_to_band(value):
    frequency = parse_frequency_mhz(value)
    if frequency is None:
        return None
    for band, lower, upper in BAND_RANGES:
        if lower <= frequency <= upper:
            return band
    return None


def normalize_band(value):
    if value is None:
        return None
    band = str(value).strip().lower().replace(" ", "")
    if band in {name.lower() for name, _, _ in BAND_RANGES}:
        return band
    return _BAND_ALIASES.get(band)


def normalize_mode(value):
    if value is None:
        return None, None
    mode = str(value).strip().upper()
    if not mode:
        return None, None
    return _MODE_ALIASES.get(mode, (mode, None))
