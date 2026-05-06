from datetime import datetime
from typing import Any


BASE_PRICES = {
    "北京-上海": 880,
    "上海-北京": 910,
    "广州-成都": 760,
    "成都-广州": 790,
    "上海-深圳": 820,
    "深圳-上海": 840,
}


def get_price(route: str, date: str) -> dict[str, Any]:
    """查询指定航线日期的模拟票价。"""

    normalized_route = route.replace("到", "-").replace("—", "-").replace(">", "-")
    try:
        travel_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {
            "found": False,
            "route": normalized_route,
            "date": date,
            "message": "日期格式需为 YYYY-MM-DD。",
        }

    base_price = BASE_PRICES.get(normalized_route)
    if base_price is None:
        return {
            "found": False,
            "route": normalized_route,
            "date": str(travel_date),
            "message": "暂未查询到该航线票价。",
        }

    day_factor = travel_date.toordinal() % 5 * 30
    price = base_price + day_factor
    return {
        "found": True,
        "route": normalized_route,
        "date": str(travel_date),
        "currency": "CNY",
        "price": price,
        "cabin": "经济舱",
        "inventory": "有票",
    }
