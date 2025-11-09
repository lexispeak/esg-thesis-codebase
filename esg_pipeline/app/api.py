from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="ESG Thesis API", version="0.1.0")

class BankItem(BaseModel):
    bank: str
    year: int
    report_url: str

class IngestBody(BaseModel):
    banks: List[BankItem]

@app.get("/health")
def health():
    return {"status":"ok"}
