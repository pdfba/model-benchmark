"""通过 OpenClaw OpenAI 兼容 API 执行指令，返回模型回复。"""
import asyncio
import json
import logging
import os
from typing import AsyncIterator, Awaitable, Callable, Optional
from rich.console import Console
from rich.table import Table

import aiohttp

import re

logger = logging.getLogger(__name__)
if os.environ.get("DEBUG"):
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
        logger.addHandler(h)

API_URL = "http://127.0.0.1:8789/v1/chat/completions"
API_KEY = "open claw key"
MODEL = "openclaw"
DATASET_PATH = "/root/ShareGPT_V3_unfiltered_cleaned_split.json"
# 虚拟环境 bin 路径，可通过环境变量 AIAKPERF_VENV_BIN 覆盖
AIAKPERF_VENV_BIN = os.environ.get("AIAKPERF_VENV_BIN", "/opt/aiakperf-env/bin")




async def run_aiakperf(  # 名称保持不变，内部改为调用 OpenClaw
    tool: str = "aiakperf",
    model: str = "deepseek-r1-distill-qwen-32b",
    api_address: str = "qianfan.baidubce.com",
    auth_header: str = "your-owner-sk",
    requestor: str = "qianfan_v2",
    dataset: str = "raw_sharegpt",
    n_value: str = "2",
    if_value: str = "128",
    of_value: str = "128",
    qps_value: str = "1",
    ttft_ms: float = 0.0,
    tpot_ms: float = 0.0,
    timeout: Optional[int] = 300,
) -> tuple[str, int]:
    """
    调用 OpenClaw OpenAI 兼容接口。

    参数中 model_url / input_tokens / output_tokens / ttft_ms / tpot_ms
    可用于前端展示或后续扩展，这里主要使用 content 作为用户指令。

    返回 (完整回复文本, 退出码)，退出码 0 表示成功。
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 定义变量
    #tool = "aiakperf"
    #model = "deepseek-r1-distill-qwen-32b"
    #api_address = "qianfan.baidubce.com"
    #auth_header = "your-owner-sk"
    #requestor = "qianfan_v2"
    #dataset = "raw_sharegpt"
    #n_value = "100"
    #if_value = "1024"
    #of_value = "512"
    #qps_value = "1"

    # 拼出最终字符串
    content = f"""需要你执行模型的性能测试。
    测试工具是{tool}，测试工具安装在了虚拟环境aiakperf-env中，使用下面的命令激活环境
    source /opt/aiakperf-env/bin/activate
    具体的调用方式是
    {tool} -m /root/{model} -a {api_address} -M {model} -H "Authorization: Bearer {auth_header}" -r {requestor} -d {dataset} -D /root/ShareGPT_V3_unfiltered_cleaned_split.json -n {n_value} -if {if_value} -of {of_value} -qps {qps_value} -igr true 
    在执行完命令行后，需要将命令的回显保存到一个文件。最后需要你提供详细的性能测试报告。"""


    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "stream": True,
    }

    print(f"run_aiakperf 开始: url={API_URL}, tool={tool}, model={model}, timeout={timeout}")
    print(f"请求 content 长度: {len(content)} 字符")

    accumulated = []
    chunk_count = 0
    raw_samples = []

    try:
        async with aiohttp.ClientSession() as session:
            print("正在连接 OpenClaw API...")
            async with session.post(API_URL, headers=headers, json=payload, timeout=timeout) as response:
                print(f"响应状态: {response.status} {response.reason}")
                if response.status != 200:
                    error_text = await response.text()
                    print(f"OpenClaw 请求失败: status={response.status}, body={error_text[:200]}")
                    return f"Error: OpenClaw 请求失败 ({response.status})\\n{error_text}", response.status

                # 使用行缓冲解析 SSE，与 run_aiakperf_stream 一致（response.content 迭代返回的是字节块而非行）
                buffer = b""
                done = False
                async for chunk in response.content.iter_chunked(1024):
                    buffer += chunk
                    while b"\n" in buffer or b"\r\n" in buffer:
                        sep = b"\n" if b"\n" in buffer else b"\r\n"
                        line_bytes, buffer = buffer.split(sep, 1)
                        line = line_bytes.decode("utf-8", errors="ignore").strip()
                        if not line:
                            continue
                        if len(raw_samples) < 10:
                            raw_samples.append(line[:300])
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            done = True
                            break
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            print(f"JSON 解析失败，原始行: {line[:100]}")
                            continue
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        piece = delta.get("content") or ""
                        if not piece and delta:
                            print(f"收到 delta 但无 content，keys={list(delta.keys())}")
                        if piece:
                            piece = piece.replace("\\n", "\n").replace("\\t", "\t")
                            accumulated.append(piece)
                            chunk_count += 1
                            if chunk_count <= 5 or chunk_count % 100 == 0:
                                print(f"已接收 chunk #{chunk_count}, 累计 {sum(len(p) for p in accumulated)} 字符")
                    if done:
                        break
    except Exception as exc:  # 网络错误等
        logger.exception("run_aiakperf 异常: %s", exc)
        return f"Error: OpenClaw 调用异常: {exc}", -1

    text = "".join(accumulated)
    if not text:
        print(
            f"流式响应为空 (chunk_count={chunk_count})，尝试非流式请求..."
        )
        if raw_samples:
            print("--- 原始流式响应（诊断用）---")
            for i, s in enumerate(raw_samples):
                print(f"  [{i}] {s}")
        # 回退：使用 stream=False 获取完整响应（OpenClaw 可能不支持流式或格式不同）
        try:
            payload_no_stream = {**payload, "stream": False}
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, headers=headers, json=payload_no_stream, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("choices") or []
                        if choices:
                            msg = choices[0].get("message") or {}
                            text = msg.get("content") or ""
                            if text:
                                text = text.replace("\\n", "\n").replace("\\t", "\t")
                                print(f"非流式请求成功，获取 {len(text)} 字符")
                    if not text:
                        text = "Warning: OpenClaw 未返回任何内容"
        except Exception as e:
            print(f"非流式回退失败: {e}")
            text = "Warning: OpenClaw 未返回任何内容"

    print(f"run_aiakperf 完成: chunk_count={chunk_count}, 总字符数={len(text)}, exit_code=0")
    return text, 0



        
