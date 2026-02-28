"""模型性能与精度压测后端 API。"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import get_connection, init_db, list_results, save_result
from parser import extract_metrics_for_db, parse_aiakperf_output
from runner import run_aiakperf

app = FastAPI(title="模型压测服务", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TestRequest(BaseModel):
    model_url: str = Field(..., description="待测试的模型服务地址")
    test_tool: str = Field(default="aiakperf", description="测试工具")
    input_tokens: int = Field(..., ge=1, description="输入 Token 长度")
    output_tokens: int = Field(..., ge=1, description="输出 Token 长度")
    ttft_ms: float = Field(..., ge=0, description="TTFT (ms)")
    tpot_ms: float = Field(..., ge=0, description="TPOT (ms)")


class StoreResultRequest(BaseModel):
    model_url: str
    test_tool: str = "aiakperf"
    input_tokens: int
    output_tokens: int
    ttft_ms: float
    tpot_ms: float
    raw_output: str = ""
    qps: float | None = None
    mean_ttft: float | None = None
    mean_tpot: float | None = None
    total_time: float | None = None
    num_requests: int | None = None
    num_succeed: int | None = None
    num_failed: int | None = None


@app.on_event("startup")
def startup():
    init_db()


@app.post("/api/test")
async def run_test(req: TestRequest):
    """执行模型性能测试，返回原始输出与解析后的指标。"""
    if req.test_tool != "aiakperf":
        raise HTTPException(status_code=400, detail="当前仅支持测试工具: aiakperf")
    raw_output, exit_code = await run_aiakperf(
        model_url=req.model_url,
        input_tokens=req.input_tokens,
        output_tokens=req.output_tokens,
        ttft_ms=req.ttft_ms,
        tpot_ms=req.tpot_ms,
    )
    parsed = parse_aiakperf_output(raw_output)
    metrics = extract_metrics_for_db(parsed)
    return {
        "success": exit_code == 0,
        "raw_output": raw_output,
        "parsed_metrics": parsed,
        "exit_code": exit_code,
        "summary": {
            "qps": metrics.get("qps"),
            "mean_ttft": metrics.get("mean_ttft"),
            "mean_tpot": metrics.get("mean_tpot"),
            "total_time": metrics.get("total_time"),
            "num_requests": metrics.get("num_requests"),
            "num_succeed": metrics.get("num_succeed"),
            "num_failed": metrics.get("num_failed"),
        },
    }


@app.post("/api/results")
def store_result(req: StoreResultRequest):
    """将一次模型性能测试结果写入数据库。"""
    data = {
        "model_url": req.model_url,
        "test_tool": req.test_tool,
        "input_tokens": req.input_tokens,
        "output_tokens": req.output_tokens,
        "ttft_ms": req.ttft_ms,
        "tpot_ms": req.tpot_ms,
        "raw_output": req.raw_output,
        "qps": req.qps,
        "mean_ttft": req.mean_ttft,
        "mean_tpot": req.mean_tpot,
        "total_time": req.total_time,
        "num_requests": req.num_requests,
        "num_succeed": req.num_succeed,
        "num_failed": req.num_failed,
    }
    with get_connection() as conn:
        rid = save_result(conn, data)
    return {"id": rid, "message": "已保存"}


@app.get("/api/results")
def get_results(limit: int = 100):
    """获取历史测试结果列表。"""
    return list_results(limit=limit)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
