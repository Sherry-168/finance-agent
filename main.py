from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="记账助手后端API")

class ParseRequest(BaseModel):
    text: str
    session_id: Optional[str] = None

class RecordItem(BaseModel):
    amount: float
    category: str
    merchant: Optional[str] = None
    occurred_at: str
    note: Optional[str] = None
    raw_text: str

# 1. 记账解析（同意前端的 v1.1 结构）
@app.post("/api/v1/records/parse")
def parse_record(request: ParseRequest):
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "draft_id": "d_001",
            "fields": {
                "amount": 32.0,
                "category": "交通",
                "merchant": None,
                "occurred_at": "2026-11-14",
                "note": None
            },
            "confidence": 0.95,
            "missing_fields": [],
            "clarify_question": None
        }
    }

# 2. 确认入库（实现它）
@app.post("/api/v1/records")
def save_record(item: RecordItem):
    # 这里以后要调用蔡适伶写的数据库插入逻辑
    # 现在先返回一个假的 id
    return {
        "code": 0,
        "message": "ok",
        "data": {"id": 101, "confirmed": 1}
    }

# 3. 自然语言查账
@app.post("/api/v1/query")
def query_records(request: ParseRequest):
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "answer_text": "你 10 月餐饮共支出 ¥1,286.50，共 42 笔。",
            "table": [ { "category": "餐饮", "total": 1286.5, "count": 42 } ]
        }
    }