"""执行性能测试工具（如 aiakperf），返回原始输出。"""
import asyncio
import shutil
from typing import Optional


async def run_aiakperf(
    model_url: str,
    input_tokens: int,
    output_tokens: int,
    ttft_ms: float,
    tpot_ms: float,
    timeout: Optional[int] = 600,
) -> tuple[str, int]:
    """
    调用 aiakperf 进行压测。返回 (stdout+stderr 文本, 退出码)。
    若未安装 aiakperf，返回模拟输出和退出码 0，便于前端联调。
    """
    cmd = shutil.which("aiakperf")
    if not cmd:
        # 未安装时返回模拟结果，便于开发与演示
        mock = _mock_output(input_tokens, output_tokens, ttft_ms, tpot_ms)
        return mock, 0

    proc = await asyncio.create_subprocess_exec(
        cmd,
        "--url", model_url,
        "--input-tokens", str(input_tokens),
        "--output-tokens", str(output_tokens),
        "--ttft", str(ttft_ms),
        "--tpot", str(tpot_ms),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout or 600)
        return stdout.decode("utf-8", errors="replace"), proc.returncode or 0
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return "Error: 测试超时\n", -1


def _mock_output(
    input_tokens: int,
    output_tokens: int,
    ttft_ms: float,
    tpot_ms: float,
) -> str:
    """生成与 design.mk 中格式一致的模拟输出。"""
    return f"""[perf_tool] [INFO] 1000 requests succeed, 0 requests failed
| Metric | Value |
| Perf Mode | qps 3.0 |
| Dataset | raw_sharegpt |
| Runner | openai |
| Start Time | 2025-08-01 18:14:24 |
| Total Time | 369.2649 |
| Input Tokens | {input_tokens * 1000} |
| Avg Input | {input_tokens} |
| Generated Tokens | {output_tokens * 1000} |
| Avg Output | {output_tokens} |
| Total Tokens | {(input_tokens + output_tokens) * 1000} |
| Num Requests | 1000 |
| Num Succeed | 1000 |
| Num Failed | 0 |
| Input Throughput | 44369.2367 |
| Generation Throughput| 920.7429 |
| Total Throughput | 45289.9796 |
| Avg Otps | 18.1365 |
| Qps | 2.7081 |
| Median Ttft | {ttft_ms} |
| Mean Ttft | {ttft_ms} |
| Std Ttft | 3.2558 |
| Percentiles Ttft | [(80.0, 20.001), (99.0, 22.962)] |
| Median Ttst | 0.6995 |
| Mean Ttst | 0.7257 |
| Std Ttst | 0.1632 |
| Percentiles Ttst | [(80.0, 0.839), (99.0, 1.209)] |
| Median Tpot | {tpot_ms} |
| Mean Tpot | {tpot_ms} |
| Std Tpot | 0.0033 |
| Percentiles Tpot | [(80.0, 0.058), (99.0, 0.062)] |
| Median E2El | 35.5161 |
| Mean E2El | 35.4869 |
| Std E2El | 3.5392 |
| Percentiles E2El | [(80.0, 38.839), (99.0, 42.333)] |
| Median Itl Smoothness| 0.0306 |
| Mean Itl Smoothness | 0.0302 |
| Std Itl Smoothness | 0.0061 |
| Percentiles Itl Smoothness | [(80.0, 0.035), (99.0, 0.043)] |
"""
