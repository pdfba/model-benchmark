"""SQLite 数据库初始化与模型性能结果存储。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "benchmark.db"


def init_db():
    """创建数据库表；若为旧表结构则迁移到新结构（增加 model、n_value，移除 ttft_ms、tpot_ms）。"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_url TEXT NOT NULL,
                test_tool TEXT NOT NULL,
                model TEXT,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                n_value TEXT,
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
        # 若已存在旧表且无 model 列，则迁移
        cur = conn.execute("PRAGMA table_info(test_results)")
        cols = [r[1] for r in cur.fetchall()]
        if "model" not in cols and "ttft_ms" in cols:
            conn.execute("""
                CREATE TABLE test_results_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_url TEXT NOT NULL,
                    test_tool TEXT NOT NULL,
                    model TEXT,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    n_value TEXT,
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
            conn.execute("""
                INSERT INTO test_results_new (
                    id, model_url, test_tool, model, input_tokens, output_tokens, n_value,
                    raw_output, qps, mean_ttft, mean_tpot, total_time,
                    num_requests, num_succeed, num_failed, created_at
                )
                SELECT id, model_url, test_tool, '', input_tokens, output_tokens, '',
                       raw_output, qps, mean_ttft, mean_tpot, total_time,
                       num_requests, num_succeed, num_failed, created_at
                FROM test_results
            """)
            conn.execute("DROP TABLE test_results")
            conn.execute("ALTER TABLE test_results_new RENAME TO test_results")
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
            model_url, test_tool, model, input_tokens, output_tokens, n_value,
            raw_output, qps, mean_ttft, mean_tpot,
            total_time, num_requests, num_succeed, num_failed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["model_url"],
            data["test_tool"],
            data.get("model", ""),
            data["input_tokens"],
            data["output_tokens"],
            data.get("n_value", ""),
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
            SELECT id, model_url, test_tool, model, input_tokens, output_tokens,
                   n_value, qps, mean_ttft, mean_tpot, num_succeed, created_at
            FROM test_results
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
