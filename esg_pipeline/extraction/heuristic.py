import re, yaml
from typing import Dict, Any, List
from ..normalizer import to_number, standardize_unit

def _window(text: str, start: int, end: int, pad: int=80) -> str:
    s = max(0, start-pad)
    e = min(len(text), end+pad)
    return text[s:e].replace("\n", " ")

def load_rules(path:str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def compile_patterns(rules: Dict[str, Any], bank: str) -> Dict[str, List[re.Pattern]]:
    pats = {}
    defaults = rules.get("bank_defaults", {}).get("patterns", {})
    for field, arr in defaults.items():
        pats.setdefault(field, [])
        for rx in arr:
            pats[field].append(re.compile(rx, flags=re.I|re.S|re.U))
    bspec = rules.get("banks", {}).get(bank, {}).get("patterns", {})
    for field, arr in bspec.items():
        pats.setdefault(field, [])
        for rx in arr:
            pats[field].append(re.compile(rx, flags=re.I|re.S|re.U))
    return pats

def extract(text: str, bank: str, rules_path: str) -> List[Dict[str, Any]]:
    rules = load_rules(rules_path)
    patterns = compile_patterns(rules, bank)
    out: List[Dict[str, Any]] = []
    for field, rxs in patterns.items():
        for rx in rxs:
            m = rx.search(text)
            if m:
                val = to_number(m.group(1), decimal_comma=True)
                unit = standardize_unit(m.group(2) if len(m.groups())>=2 else "")
                ev = _window(text, m.start(1), m.end(1))
                out.append({"field": field, "value_raw": m.group(1), "value": val, "unit": unit,
                            "confidence": 0.75, "source": "heuristic", "evidence": ev})
                break
    return out
