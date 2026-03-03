"""模型性能与精度压测后端 API。"""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database import get_connection, init_db, list_results, save_result
from parser import extract_metrics_for_db, parse_aiakperf_output
from runner import find_best_qps, run_aiakperf_shell

# 从配置文件读取默认 API Key（不硬编码）
_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
try:
    _config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
except Exception:
    _config = {}
DEFAULT_API_KEY: str = _config.get("default_api_key", "")

app = FastAPI(title="模型压测服务", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TestShellRequest(BaseModel):
    """用于 shell 执行 aiakperf 的入参。"""
    tool: str = Field(default="aiakperf", description="测试工具")
    model: str = Field(default="deepseek-r1-distill-qwen-32b", description="模型名")
    api_address: str = Field(default="qianfan.baidubce.com", description="API 地址")
    auth_header: str = Field(
        default_factory=lambda: DEFAULT_API_KEY,
        description="Authorization Bearer，默认从 backend/config.json 的 default_api_key 读取",
    )
    requestor: str = Field(default="qianfan_v2", description="请求方")
    dataset: str = Field(default="raw_sharegpt", description="数据集")
    n_value: str = Field(default="2", description="请求数")
    if_value: str = Field(default="128", description="输入 token 长度")
    of_value: str = Field(default="128", description="输出 token 长度")
    qps_value: str = Field(default="1", description="QPS")
    ttft_ms: float = Field(default=0.0, ge=0, description="TTFT (ms)")
    tpot_ms: float = Field(default=0.0, ge=0, description="TPOT (ms)")
    timeout: int = Field(default=600, ge=1, description="超时秒数")


class FindBestQpsRequest(BaseModel):
    """寻找最佳 QPS 的入参。"""
    ttft: float = Field(default=5.0, ge=0, description="TTFT 约束 (秒)")
    tpot: float = Field(default=0.05, ge=0, description="TPOT 约束 (秒)")
    qps_initial: float = Field(default=1.0, gt=0, description="初始 QPS")
    max_iter: int = Field(default=20, ge=1, le=50, description="最大迭代次数")
    qps_tol: float = Field(default=0.05, ge=0, description="QPS 收敛精度")
    tool: str = Field(default="aiakperf", description="测试工具")
    model: str = Field(default="deepseek-r1-distill-qwen-32b", description="模型名")
    api_address: str = Field(default="qianfan.baidubce.com", description="API 地址")
    auth_header: str = Field(default_factory=lambda: DEFAULT_API_KEY)
    requestor: str = Field(default="qianfan_v2")
    dataset: str = Field(default="raw_sharegpt")
    n_value: str = Field(default="10")
    if_value: str = Field(default="128")
    of_value: str = Field(default="128")
    timeout: int = Field(default=600, ge=1)


class StoreResultRequest(BaseModel):
    model_url: str
    test_tool: str = "aiakperf"
    model: str = ""
    input_tokens: int
    output_tokens: int
    n_value: str = ""
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


async def _stream_find_best_qps(req: FindBestQpsRequest):
    """将 find_best_qps 的进度与结果通过 SSE 推送。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def on_progress(data: dict):
        await queue.put(data)

    async def run():
        try:
            best_qps, raw_output, exit_code, history = await find_best_qps(
                ttft=req.ttft,
                tpot=req.tpot,
                qps_initial=req.qps_initial,
                max_iter=req.max_iter,
                qps_tol=req.qps_tol,
                tool=req.tool,
                model=req.model,
                api_address=req.api_address,
                auth_header=req.auth_header,
                requestor=req.requestor,
                dataset=req.dataset,
                n_value=req.n_value,
                if_value=req.if_value,
                of_value=req.of_value,
                timeout=req.timeout,
                progress_callback=on_progress,
            )
            await queue.put({
                "type": "done",
                "best_qps": best_qps,
                "raw_output": raw_output,
                "exit_code": exit_code,
                "history": history,
            })
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})

    asyncio.create_task(run())

    while True:
        data = await queue.get()
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        if data.get("type") in ("done", "error"):
            break


@app.post("/api/test/best-qps/stream")
async def run_find_best_qps_stream(req: FindBestQpsRequest):
    """寻找最佳 QPS（SSE 推送进度与结果）。"""
    return StreamingResponse(
        _stream_find_best_qps(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/test/shell")
async def run_test_shell(req: TestShellRequest):
    """通过本地 shell 执行 aiakperf，返回测试回显。"""
    raw_output, exit_code = await run_aiakperf_shell(
        tool=req.tool,
        model=req.model,
        api_address=req.api_address,
        auth_header=req.auth_header,
        requestor=req.requestor,
        dataset=req.dataset,
        n_value=req.n_value,
        if_value=req.if_value,
        of_value=req.of_value,
        qps_value=req.qps_value,
        ttft_ms=req.ttft_ms,
        tpot_ms=req.tpot_ms,
        timeout=req.timeout,
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
        "model": req.model,
        "input_tokens": req.input_tokens,
        "output_tokens": req.output_tokens,
        "n_value": req.n_value,
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
    uvicorn.run(app, host="0.0.0.0", port=8900)
