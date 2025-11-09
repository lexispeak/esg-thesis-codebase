import os, json
from typing import List, Dict, Any
from ..schema import load_schema_json, SchemaField

PROMPT_TEMPLATE = """Bạn là trợ lý ESG đọc báo cáo ngân hàng Việt Nam. Hãy trích xuất các KPI theo schema cung cấp.
Trả JSON dạng list: [{{"field": "...","value": number|string,"unit":"...","evidence":"trích dẫn ngắn"}}] 
Nếu không thấy, bỏ qua. Không tự bịa số. Văn bản:
---
{chunk}
"""

def call_openai(model: str, prompt: str):
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[{"role":"user","content":prompt}]
    )
    return resp.choices[0].message.content

def call_ollama(model: str, prompt: str):
    import ollama
    r = ollama.chat(model=model, messages=[{"role":"user","content":prompt}])
    return r['message']['content']

def extract_with_llm(text: str, schema_path: str, provider="openai", model="gpt-4o-mini") -> List[Dict[str,Any]]:
    # simple chunking
    chunks = []
    words = text.split()
    step = 1200
    for i in range(0, len(words), step):
        chunks.append(" ".join(words[i:i+step]))

    outputs = []
    for ch in chunks:
        prompt = PROMPT_TEMPLATE.format(chunk=ch)
        if provider=="openai":
            raw = call_openai(model, prompt)
        elif provider=="ollama":
            raw = call_ollama(model, prompt)
        else:
            continue
        # Attempt to find json in response
        js = None
        try:
            start = raw.find("[")
            end = raw.rfind("]")
            if start!=-1 and end!=-1:
                js = json.loads(raw[start:end+1])
        except Exception:
            js = None
        if isinstance(js, list):
            for item in js:
                item["confidence"] = 0.6
                item["source"] = "llm"
            outputs.extend(js)
    return outputs
