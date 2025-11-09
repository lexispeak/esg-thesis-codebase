from typing import List, Dict, Any

PLAUSIBLE = {
    "Female_Board_Ratio": (0, 100),
    "Board_Size": (3, 25),
    "GHG_Scope1": (0, 10000000),
    "Energy_Consumption": (0, 10000000000),
}

def _is_plausible(field, value):
    if value is None: return False
    if field in PLAUSIBLE:
        lo, hi = PLAUSIBLE[field]
        try:
            v = float(value); return lo <= v <= hi
        except Exception:
            return False
    return True

def score_disclosure(mapped_records: List[Dict[str, Any]], raw_candidates: List[Dict[str, Any]]):
    if not mapped_records:
        return {"disclosure_quality": 0.0, "detail": {}}
    by_field = {}
    for r in mapped_records:
        sf = r.get("schema_field"); by_field.setdefault(sf, []); by_field[sf].append(r)
    total = len(by_field); presence = total
    evidence_ok = unit_ok = consistent = plausible = 0
    for sf, rows in by_field.items():
        e_ok = any(len((r.get("evidence") or "")) >= 20 for r in rows)
        u_ok = any((r.get("unit") or "").strip() != "" for r in rows)
        p_ok = any(_is_plausible(sf, r.get("value")) for r in rows)
        hv = [r for r in rows if r.get("source")=="heuristic" and isinstance(r.get("value"), (int,float))]
        lv = [r for r in rows if r.get("source")=="llm" and isinstance(r.get("value"), (int,float))]
        c_ok = False
        if hv and lv:
            h = hv[0]["value"]; l = lv[0]["value"]
            denom = max(abs(h), abs(l), 1e-9)
            c_ok = (abs(h-l)/denom) <= 0.1
        evidence_ok += 1 if e_ok else 0
        unit_ok += 1 if u_ok else 0
        plausible += 1 if p_ok else 0
        consistent += 1 if c_ok else 0
    score = (0.30*(presence/total) + 0.20*(evidence_ok/total) + 0.15*(unit_ok/total)
             + 0.20*(consistent/total) + 0.15*(plausible/total)) * 100.0
    return {"disclosure_quality": float(round(score,2)),
            "detail": {
              "presence_ratio": round(presence/total, 3),
              "evidence_ratio": round(evidence_ok/total, 3),
              "unit_ratio": round(unit_ok/total, 3),
              "consistency_ratio": round(consistent/total, 3),
              "plausible_ratio": round(plausible/total, 3),
              "total_fields": total
            }}
