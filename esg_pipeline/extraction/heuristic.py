import re
from typing import Dict, Any, List
from ..normalizer import to_number, standardize_unit

# Simple keyword/regex examples — extend per bank/report pattern
PATTERNS = {
    "GHG_Scope1": r"(?:scope\s*1|phạm vi\s*1).{0,50}?(\d[\d\.,]*)\s*(tco2e|tco₂e)?",
    "Energy_Consumption": r"(?:tiêu thụ năng lượng|energy consumption).{0,50}?(\d[\d\.,]*)\s*(kwh|mwh)",
    "Female_Board_Ratio": r"(?:tỷ lệ nữ.*?hđqt|female.*?board).{0,50}?(\d[\d\.,]*)\s*%",
    "Board_Size": r"(?:số lượng thành viên hđqt|board size).{0,50}?(\d+)",
}

def extract(text: str) -> List[Dict[str, Any]]:
    out = []
    for field, rx in PATTERNS.items():
        m = re.search(rx, text, flags=re.I|re.S|re.U)
        if m:
            val = to_number(m.group(1), decimal_comma=True)
            unit = standardize_unit(m.group(2) if len(m.groups())>=2 else "")
            out.append({"field": field, "value_raw": m.group(1), "value": val, "unit": unit, "confidence": 0.7, "source": "heuristic"})
    return out
