import re, math

NUM_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")

UNIT_ALIASES = {
    "tco2e": ["tco₂e","tco2e","tco2eq","tco2-e","tco2e/year"],
    "kwh": ["kwh","kw h","kilowatt-hour","kwh/năm"],
    "m3": ["m3","m³","m^3"],
    "percent": ["%","pct","percent"],
    "vnd": ["vnd","₫","vnđ","đ"],
}

def to_number(s: str, decimal_comma=False):
    if s is None:
        return None
    s = str(s).strip()
    try:
        if decimal_comma:
            s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        m = NUM_PATTERN.search(str(s))
        if m:
            return to_number(m.group(0), decimal_comma=decimal_comma)
        return None

def standardize_unit(unit: str) -> str:
    if not unit:
        return ""
    u = unit.strip().lower()
    for k, arr in UNIT_ALIASES.items():
        for alias in arr:
            if alias in u:
                return k
    return u
