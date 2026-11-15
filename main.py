from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="记账助手后端API")

class ParseRequest(BaseModel):
    text: str

class QueryRequest(BaseModel):
    question: str

@app.get("/api/v1/health")
def health_check():
    return {"code": 0, "message": "ok", "data": "Backend is running"}

@app.post("/api/v1/records/parse")
def parse_record(request: ParseRequest):
    # TODO: 这里以后要调用李语琛写的 agent.py
    # 暂时返回假数据，供林丹苗联调
    return {
        "code": 0, 
        "data": {"amount": 32.0, "category": "交通", "occurred_at": "2026-11-14"}
    }

@app.post("/api/v1/query")
def query_records(request: QueryRequest):
    # TODO: 这里以后要调用蔡适伶写的数据库查询逻辑
    return {
        "code": 0, 
        "data": {"answer_text": f"你问的是：{request.question}，后端正在努力算账...", "total": 1286.5}
    }