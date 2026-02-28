"""SQLite 数据库初始化与模型性能结果存储。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "benchmark.db"


def init_db():
    """创建数据库表。"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_url TEXT NOT NULL,
                test_tool TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                ttft_ms REAL NOT NULL,
                tpot_ms REAL NOT NULL,
                raw_output TEXT,
                qps REAL,
                mean_ttft REAL,
                mean_tpot REAL,
                total_time REAL,
                num_requests INTEGER,
                num_succeed INTEGER,
                num_failed INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_result(conn, data: dict) -> int:
    """将单次测试结果写入数据库，返回新插入行的 id。"""
    cur = conn.execute(
        """
        INSERT INTO test_results (
            model_url, test_tool, input_tokens, output_tokens,
            ttft_ms, tpot_ms, raw_output, qps, mean_ttft, mean_tpot,
            total_time, num_requests, num_succeed, num_failed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["model_url"],
            data["test_tool"],
            data["input_tokens"],
            data["output_tokens"],
            data["ttft_ms"],
            data["tpot_ms"],
            data.get("raw_output", ""),
            data.get("qps"),
            data.get("mean_ttft"),
            data.get("mean_tpot"),
            data.get("total_time"),
            data.get("num_requests"),
            data.get("num_succeed"),
            data.get("num_failed"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_results(limit: int = 100):
    """查询最近的测试结果列表。"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, model_url, test_tool, input_tokens, output_tokens,
                   ttft_ms, tpot_ms, qps, mean_ttft, mean_tpot, created_at
            FROM test_results
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
