import os, pandas as pd

def assemble_features(mapped_jsonl_path: str, labels_csv_path: str):
    # pivot mapped KPI into wide table
    rows = []
    with open(mapped_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            rows.append(pd.read_json(line, typ="series").to_dict())
    if not rows:
        return None, None
    df = pd.DataFrame(rows)
    # Expect bank, year present upstream (can add later). For now aggregate by (field) value last seen.
    wide = df.pivot_table(index=[], columns="schema_field", values="value", aggfunc="last").reset_index(drop=True)
    labels = None
    if os.path.exists(labels_csv_path):
        labels = pd.read_csv(labels_csv_path)
    return wide, labels
