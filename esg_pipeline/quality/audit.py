import pandas as pd
from typing import List, Dict, Any

def audit_coverage(mapped_records: List[Dict[str,Any]]):
    if not mapped_records:
        return {"coverage": 0.0, "by_field": {}}
    df = pd.DataFrame(mapped_records)
    cov = df.groupby("schema_field").agg(
        count=("schema_field","count"),
        avg_conf=("confidence","mean"),
        avg_match=("match_score","mean")
    ).reset_index()
    coverage = len(cov) / len(set(df["schema_field"]))
    return {"coverage": float(coverage), "detail": cov.to_dict(orient="records")}
