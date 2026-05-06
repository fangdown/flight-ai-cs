import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path(__file__).resolve().parent / "flight.db"


def get_connection() -> sqlite3.Connection:
    """创建 SQLite 连接。"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化订单表和演示数据。"""

    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                passenger_name TEXT NOT NULL,
                route TEXT NOT NULL,
                flight_no TEXT NOT NULL,
                flight_date TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                status TEXT NOT NULL,
                ticket_type TEXT NOT NULL,
                price INTEGER NOT NULL,
                abnormal INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        rows = [
            (
                "123",
                "张三",
                "北京-上海",
                "CZ8888",
                "2026-05-20",
                "2026-05-20 09:30:00",
                "已出票",
                "经济舱",
                860,
                0,
            ),
            (
                "456",
                "李四",
                "广州-成都",
                "CZ6666",
                "2026-05-08",
                "2026-05-08 14:10:00",
                "航班取消",
                "经济舱",
                730,
                1,
            ),
            (
                "789",
                "王五",
                "上海-深圳",
                "CZ5678",
                "2026-05-10",
                "2026-05-10 18:45:00",
                "已退票",
                "公务舱",
                1680,
                0,
            ),
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO orders (
                order_id, passenger_name, route, flight_no, flight_date,
                departure_time, status, ticket_type, price, abnormal
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def fetch_order(order_id: str) -> dict[str, Any] | None:
    """按订单号读取订单。"""

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
    return dict(row) if row else None
