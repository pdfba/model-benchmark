"""解析 aiakperf 等工具输出的文本报告，提取指标。"""
import re
from typing import Any


def parse_aiakperf_output(raw: str) -> dict[str, Any]:
    """
    解析 aiakperf 输出的表格文本，提取 Metric | Value 形式的行。
    返回键为指标名（去掉空格、转小写）、值为浮点或整数的字典。
    """
    result = {}
    # 表格行格式: | Metric Name | Value |
    pattern = re.compile(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("---"):
            continue
        m = pattern.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        value_str = m.group(2).strip()
        key = name.lower().replace(" ", "_")
        # 数值解析
        try:
            if "." in value_str:
                result[key] = float(value_str)
            else:
                result[key] = int(value_str)
        except ValueError:
            result[key] = value_str
    return result


def extract_metrics_for_db(parsed: dict) -> dict[str, Any]:
    """从解析结果中取出需要入库的字段。"""
    def get(key: str, default=None):
        # 兼容多种键名
        for k in (key, key.replace("_", " "), key.replace(" ", "_")):
            if k in parsed:
                return parsed[k]
        return default

    return {
        "qps": get("qps"),
        "mean_ttft": get("mean_ttft"),
        "mean_tpot": get("mean_tpot"),
        "total_time": get("total_time"),
        "num_requests": get("num_requests"),
        "num_succeed": get("num_succeed"),
        "num_failed": get("num_failed"),
    }
