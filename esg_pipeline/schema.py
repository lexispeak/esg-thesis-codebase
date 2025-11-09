from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import json, csv

class SchemaField(BaseModel):
    pillar: str
    field: str
    Type: Optional[str] = None
    Unit: Optional[str] = None
    Source: Optional[str] = None
    Standard: Optional[str] = None
    Update: Optional[str] = None

def load_schema_json(path: str) -> List[SchemaField]:
    with open(path, "r", encoding="utf-8") as f:
        js = json.load(f)
    return [SchemaField(**x) for x in js]

def load_schema_csv(path: str) -> List[SchemaField]:
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append(SchemaField(**row))
    return out
