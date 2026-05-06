from datetime import datetime
from typing import Any

from db.db import fetch_order


def judge_refund(order: dict[str, Any]) -> dict[str, Any]:
    """判断订单退票规则。"""

    if order["status"] == "已退票":
        return {
            "eligible": False,
            "fee": None,
            "reason": "订单已完成退票，不能重复办理。",
        }
    if order["abnormal"]:
        return {
            "eligible": True,
            "fee": 0,
            "reason": "航班异常，符合非自愿退票，免收手续费。",
        }

    departure_time = datetime.strptime(order["departure_time"], "%Y-%m-%d %H:%M:%S")
    hours_left = (departure_time - datetime.now()).total_seconds() / 3600
    if hours_left >= 4:
        return {
            "eligible": True,
            "fee": 120,
            "reason": "起飞前4小时以上可申请自愿退票，按舱位规则收取手续费。",
        }
    return {
        "eligible": True,
        "fee": 240,
        "reason": "距起飞不足4小时，仍可申请退票，但手续费较高。",
    }


def get_order(order_id: str) -> dict[str, Any]:
    """查询订单状态并返回退票判断。"""

    order = fetch_order(order_id)
    if not order:
        return {
            "found": False,
            "order_id": order_id,
            "message": "未找到该订单。",
        }

    refund = judge_refund(order)
    return {
        "found": True,
        "order": order,
        "refund": refund,
    }
