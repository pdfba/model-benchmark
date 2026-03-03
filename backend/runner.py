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


DATASET_PATH = "/root/ShareGPT_V3_unfiltered_cleaned_split.json"
# 虚拟环境 bin 路径，可通过环境变量 AIAKPERF_VENV_BIN 覆盖
AIAKPERF_VENV_BIN = os.environ.get("AIAKPERF_VENV_BIN", "/opt/aiakperf-env/bin")


def show_perf_result(data):
    """简单展示性能测试结果"""
    text, exit_code = data

    console = Console()

    # 打印标题
    console.print("\n[bold cyan]🚀 性能测试报告[/bold cyan]")
    console.print("=" * 60)

    # 提取表格数据
    lines = text.split('\n')
    table_data = []
    start_collecting = False

    for line in lines:
        # 找到表格开始
        if '+----------------------------+--------------------------------+' in line:
            start_collecting = True
            continue

        # 如果正在收集且遇到表格结束行
        if start_collecting and '+----------------------------+--------------------------------+' in line:
            start_collecting = False
            continue

        # 收集表格数据行
        if start_collecting and '|' in line:
            # 跳过表头
            if 'Metric' in line and 'Value' in line:
                continue

            # 解析行
            parts = line.strip('|').split('|')
            if len(parts) >= 2:
                metric = parts[0].strip()
                value = parts[1].strip()
                if metric and value:
                    table_data.append((metric, value))

    # 创建rich表格
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green")

    # 添加所有提取到的数据
    for metric, value in table_data:
        table.add_row(metric, value)

    console.print(table)

    # 显示成功/失败信息
    for line in lines:
        if 'requests succeed' in line:
            console.print(f"\n[green]{line}[/green]")
            break

    # 显示输出文件
    for line in lines:
        if 'Dump benchmark result to' in line:
            file_path = line.split('to')[-1].strip()
            console.print(f"\n[blue]📁 结果保存: {file_path}[/blue]")

    if exit_code == 0:
        console.print("\n[bold green]✅ 测试成功完成![/bold green]")
    else:
        console.print(f"\n[bold red]❌ 测试失败，退出码: {exit_code}[/bold red]")


def extract_metrics(data):
    """从性能测试结果中提取指定指标"""
    text, exit_code = data

    # 初始化变量
    mean_ttft = None
    mean_tpot = None
    qps = None
    num_succeed = None
    input_throughput = None
    generation_throughput = None

    # 按行分割文本
    lines = text.split('\n')

    for line in lines:
        # 提取 Mean Ttft
        if 'Mean Ttft' in line and '|' in line:
            match = re.search(r'Mean Ttft\s*\|\s*([\d.]+)', line)
            if match:
                mean_ttft = float(match.group(1))

        # 提取 Mean Tpot
        elif 'Mean Tpot' in line and '|' in line:
            match = re.search(r'Mean Tpot\s*\|\s*([\d.]+)', line)
            if match:
                mean_tpot = float(match.group(1))

        # 提取 Qps
        elif 'Qps' in line and '|' in line and 'Avg Otps' not in line:
            match = re.search(r'Qps\s*\|\s*([\d.]+)', line)
            if match:
                qps = float(match.group(1))

        # 提取 Num Succeed
        elif 'Num Succeed' in line and '|' in line:
            match = re.search(r'Num Succeed\s*\|\s*(\d+)', line)
            if match:
                num_succeed = int(match.group(1))

        # 提取 Input Throughput
        elif 'Input Throughput' in line and '|' in line:
            match = re.search(r'Input Throughput\s*\|\s*([\d.]+)', line)
            if match:
                input_throughput = float(match.group(1))

        # 提取 Generation Throughput
        elif 'Generation Throughput' in line and '|' in line:
            match = re.search(r'Generation Throughput\s*\|\s*([\d.]+)', line)
            if match:
                generation_throughput = float(match.group(1))

    return {
        'mean_ttft': mean_ttft,
        'mean_tpot': mean_tpot,
        'qps': qps,
        'num_succeed': num_succeed,
        'input_throughput': input_throughput,
        'generation_throughput': generation_throughput
    }


async def find_best_qps(
    ttft: float = 5.0,
    tpot: float = 0.05,
    qps_initial: float = 1.0,
    max_iter: int = 20,
    qps_tol: float = 0.05,
    tool: str = "aiakperf",
    model: str = "Qwen3-235B-A22B-Instruct-2507-Int8-Dynamic",
    api_address: str = "your-api-address.com",
    auth_header: str = "your-owner-sk",
    requestor: str = "openai",
    dataset: str = "raw_sharegpt",
    n_value: str = "100",
    if_value: str = "128",
    of_value: str = "128",
    ttft_ms: float = 0.0,
    tpot_ms: float = 0.0,
    timeout: Optional[int] = 600,
    progress_callback: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> tuple[float, str, int, list[dict]]:
    """
    在约束 ttft 与 tpot 下迭代寻找能使实测 Qps 最大的输入 QPS。
    - 输入 qps（input_qps）：作为 -qps 传入命令；n_value = 20 * input_qps。
    - 输出 qps（output_qps）：从回显中解析出的 Qps，即实测值。
    通过多次调整 input_qps，找到满足约束时最大的 output_qps，并返回该 output_qps 及对应回显。
    """
    def _round_qps(x: float) -> float:
        return round(x, 2)

    input_qps = _round_qps(qps_initial)
    best_output_qps: Optional[float] = None  # 满足约束时从回显解析出的最大 Qps
    best_raw_output = ""
    best_exit_code = -1
    last_output = ""
    last_exit_code = -1
    history: list[dict] = []
    qps_low, qps_high = 0.1, 50.0  # input_qps 搜索边界

    

    for i in range(max_iter):
        print(f"第{i+1}次迭代，input_qps={input_qps}")
        # n_value = 20 * input_qps（至少为 10）
        n_value_str = str(max(10, int(round(20 * input_qps))))

        if progress_callback:
            await progress_callback({
                "type": "progress",
                "iter": i + 1,
                "max_iter": max_iter,
                "qps": input_qps,
                "message": f"第 {i + 1}/{max_iter} 次迭代，input_qps={input_qps:.2f}, n_value={n_value_str}",
            })
        raw, exit_code = await run_aiakperf_shell(
            tool=tool,
            model=model,
            api_address=api_address,
            auth_header=auth_header,
            requestor=requestor,
            dataset=dataset,
            n_value=n_value_str,
            if_value=if_value,
            of_value=of_value,
            qps_value=f"{input_qps:.2f}",
            ttft_ms=ttft_ms,
            tpot_ms=tpot_ms,
            timeout=timeout,
        )
        
        last_output, last_exit_code = raw, exit_code
        if exit_code != 0:
            input_qps = _round_qps((qps_low + qps_high) / 2)
            history.append({"iter": i + 1, "input_qps": input_qps, "exit_code": exit_code, "error": "run failed"})
            if progress_callback:
                await progress_callback({
                    "type": "progress",
                    "iter": i + 1,
                    "max_iter": max_iter,
                    "qps": input_qps,
                    "error": "run failed",
                    "message": f"第 {i + 1}/{max_iter} 次迭代失败，退出码 {exit_code}",
                })
            continue

        metrics = extract_metrics((raw, exit_code))
        mean_ttft = metrics.get("mean_ttft")
        mean_tpot = metrics.get("mean_tpot")
        output_qps = metrics.get("qps")  # 回显中解析出的实测 Qps

        _within_or_under_1pct = lambda val, ref: val is not None and (val <= ref * 1.01 if ref else val <= 0)
        ttft_ok = _within_or_under_1pct(mean_ttft, ttft)
        tpot_ok = _within_or_under_1pct(mean_tpot, tpot)
        satisfied = ttft_ok and tpot_ok
        history.append({
            "iter": i + 1,
            "input_qps": input_qps,
            "output_qps": output_qps,
            "mean_ttft": mean_ttft,
            "mean_tpot": mean_tpot,
            "satisfied": satisfied,
        })

   
        if progress_callback:
            await progress_callback({
                "type": "progress",
                "iter": i + 1,
                "max_iter": max_iter,
                "qps": input_qps,
                "output_qps": output_qps,
                "mean_ttft": mean_ttft,
                "mean_tpot": mean_tpot,
                "satisfied": satisfied,
                "message": f"第 {i + 1}/{max_iter} 次：input_qps={input_qps:.2f}, output_qps={output_qps}, Mean TTFT={mean_ttft}, Mean TPOT={mean_tpot}, 满足约束={satisfied}",
            })

        print(f"第{i+1}次迭代，input qps={input_qps},output qps={output_qps}, mean_ttft={mean_ttft}, mean_tpot={mean_tpot}, satisfied={satisfied}")

        if mean_ttft is None and mean_tpot is None:
            qps_high = input_qps
            input_qps = _round_qps((qps_low + qps_high) / 2)
            continue

        if satisfied:
            if output_qps is not None and (best_output_qps is None or output_qps > best_output_qps):
                best_output_qps = output_qps
                best_raw_output = raw
                best_exit_code = exit_code
            qps_low = input_qps
            if qps_high <= qps_low + qps_tol:
                break
            next_input = _round_qps((qps_low + qps_high) / 2)
            if next_input <= input_qps:
                break
            input_qps = next_input
        else:
            qps_high = input_qps
            input_qps = _round_qps((qps_low + qps_high) / 2)
            if qps_high - qps_low < qps_tol:
                break

    result_qps = _round_qps(best_output_qps) if best_output_qps is not None else _round_qps(qps_initial)
    result_output = best_raw_output if best_raw_output else last_output
    result_exit = best_exit_code if best_raw_output else last_exit_code
    return result_qps, result_output, result_exit, history

#下面的run_aiakperf_shell函数如果没有特殊要求，不需要修改
async def run_aiakperf_shell(
    tool: str = "aiakperf",
    model: str = "deepseek-r1-distill-qwen-32b",
    api_address: str = "your-api-address.com",
    auth_header: str = "your-owner-sk",
    requestor: str = "openai",
    dataset: str = "raw_sharegpt",
    n_value: str = "2",
    if_value: str = "128",
    of_value: str = "128",
    qps_value: str = "1",
    ttft_ms: float = 0.0,
    tpot_ms: float = 0.0,
    timeout: Optional[int] = 600,
) -> tuple[str, int]:
    """
    通过本地 shell 执行 aiakperf 命令，返回测试回显。
    入参与 run_aiakperf 一致。
    """
    api_addr = api_address
    tool_path = f"{AIAKPERF_VENV_BIN}/{tool}"
    args_part = (
        f'-m /root/{model} -a {api_addr} '
        #f'-M /home/{model} '
        f'-M {model} '
        f"-d {dataset} -D {DATASET_PATH} "
        f"-H \"Authorization: Bearer {auth_header}\" "
        f"-r {requestor} "
        f"-n {n_value} -if {if_value} -of {of_value} -qps {qps_value} -igr true"
    )
    print(args_part)

    cmd = f"source {AIAKPERF_VENV_BIN}/activate && {tool} {args_part}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            executable="/bin/bash",
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout or 600,
        )
        output = stdout.decode("utf-8", errors="replace")
        print(output)
        print(proc.returncode)
        return output, proc.returncode or 0
    except asyncio.TimeoutError:
        return "Error: 命令执行超时\n", -1
    except Exception as exc:
        return f"Error: 执行异常: {exc}\n", -1



if __name__ == "__main__":
    import asyncio

    # 仅在本文件直接运行（python3 runner.py）时执行，被 main.py 导入时不会执行
    best_qps, raw, code, history = asyncio.run(find_best_qps(
        ttft=5.0,
        tpot=0.05,
        qps_initial=0.1,
        tool="aiakperf",
        model="deepseek-r1-distill-qwen-32b",
        api_address="qianfan.baidubce.com",
        requestor="qianfan_v2",
        dataset="raw_sharegpt",
        if_value="128",
        of_value="128",
        max_iter=1,
        auth_header="your-owner-sk",
    ))
    show_perf_result((raw, code))