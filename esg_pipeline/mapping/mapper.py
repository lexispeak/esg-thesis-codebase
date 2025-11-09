from rapidfuzz import process, fuzz
from typing import List, Dict, Any
from ..schema import load_schema_json

def map_to_schema(candidates: List[Dict[str,Any]], schema_path: str, threshold=87):
    schema = load_schema_json(schema_path)
    choices = [s.field for s in schema]
    mapped = []
    for c in candidates:
        field = c["field"]
        match, score, idx = process.extractOne(field, choices, scorer=fuzz.WRatio)
        if score >= threshold:
            c2 = dict(c)
            c2["schema_field"] = match
            c2["match_score"] = float(score)
            mapped.append(c2)
    return mapped
