import json
import os
import re
from datetime import date, timedelta
from typing import Any

from rag.search import search_faq
from tools.order import get_order
from tools.price import get_price


SYSTEM_PROMPT = """你是航空公司机票 AI 客服。
要求：
1. 优先使用工具返回的结构化数据回答订单和价格问题。
2. 退票、改签、证件、姓名、航班异常等规则问题必须参考知识库。
3. 回复要简洁，包含自然语言结论。
"""


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "查询订单状态和退票判断",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price",
            "description": "查询机票价格",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "description": "航线，如 北京-上海"},
                    "date": {"type": "string", "description": "日期，格式 YYYY-MM-DD"},
                },
                "required": ["route", "date"],
            },
        },
    },
]


class FlightAgent:
    """机票客服 Agent。"""

    def __init__(self) -> None:
        """初始化会话记忆和 OpenAI 客户端。"""

        self.memory: dict[str, list[dict[str, Any]]] = {}
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.client = self._build_openai_client()

    def chat(self, session_id: str, user_message: str) -> dict[str, Any]:
        """执行一次多轮聊天。"""

        sources = search_faq(user_message, top_k=3)
        if self._is_policy_intent(user_message) and not self._extract_order_id(user_message):
            result = self._chat_locally(session_id, user_message, sources)
        elif self.client:
            try:
                result = self._chat_with_openai(session_id, user_message, sources)
            except Exception:
                result = self._chat_locally(session_id, user_message, sources)
        else:
            result = self._chat_locally(session_id, user_message, sources)

        self._save_memory(session_id, user_message, result["answer"], result["data"])
        response_sources = sources if result.get("use_sources", True) else []
        return {
            "session_id": session_id,
            "answer": result["answer"],
            "data": result["data"],
            "sources": self._brief_sources(response_sources),
            "tool_calls": result["tool_calls"],
        }

    def _build_openai_client(self) -> Any | None:
        """按环境变量创建 OpenAI 客户端。"""

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None
        return OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

    def _chat_with_openai(
        self,
        session_id: str,
        user_message: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """使用 OpenAI tool calling 生成回复。"""

        messages = self._build_messages(session_id, user_message, sources)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,
        )
        message = response.choices[0].message
        tool_calls = []
        data: dict[str, Any] = {}

        if message.tool_calls:
            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                tool_result = self._run_tool(call.function.name, call.function.arguments)
                tool_calls.append(
                    {
                        "name": call.function.name,
                        "arguments": json.loads(call.function.arguments or "{}"),
                    }
                )
                data[call.function.name] = tool_result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

            final_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
            )
            answer = final_response.choices[0].message.content or ""
        else:
            answer = message.content or ""

        return {"answer": answer, "data": data, "tool_calls": tool_calls}

    def _chat_locally(
        self,
        session_id: str,
        user_message: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """无 OpenAI Key 时使用本地意图兜底。"""

        data: dict[str, Any] = {}
        tool_calls: list[dict[str, Any]] = []

        explicit_order_id = self._extract_order_id(user_message)
        if self._is_policy_intent(user_message) and not explicit_order_id:
            answer = self._rag_answer(user_message, sources)
            return {"answer": answer, "data": data, "tool_calls": tool_calls}

        order_id = explicit_order_id or self._last_order_id(session_id)
        if order_id and self._is_order_intent(user_message):
            order_data = get_order(order_id)
            data["get_order"] = order_data
            tool_calls.append({"name": "get_order", "arguments": {"order_id": order_id}})
            answer = self._order_answer(order_data, user_message)
            return {"answer": answer, "data": data, "tool_calls": tool_calls}

        if self._is_price_intent(user_message):
            route = self._extract_route(user_message)
            travel_date = self._extract_date(user_message)
            price_data = get_price(route, travel_date)
            data["get_price"] = price_data
            tool_calls.append(
                {
                    "name": "get_price",
                    "arguments": {"route": route, "date": travel_date},
                }
            )
            answer = self._price_answer(price_data)
            return {"answer": answer, "data": data, "tool_calls": tool_calls}

        if not self._is_airline_intent(user_message):
            return {
                "answer": "当前未配置或未连通 DeepSeek，本地兜底只支持机票客服问题。请设置 DEEPSEEK_API_KEY 后重启服务。",
                "data": data,
                "tool_calls": tool_calls,
                "use_sources": False,
            }

        answer = self._rag_answer(user_message, sources)
        return {"answer": answer, "data": data, "tool_calls": tool_calls}

    def _build_messages(
        self,
        session_id: str,
        user_message: str,
        sources: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """组装 LLM 消息。"""

        context = "\n\n".join(item["content"][:1200] for item in sources)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"知识库检索结果：\n{context}"},
        ]
        for item in self.memory.get(session_id, [])[-8:]:
            messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": user_message})
        return messages

    def _run_tool(self, name: str, arguments: str) -> dict[str, Any]:
        """执行工具函数。"""

        args = json.loads(arguments or "{}")
        if name == "get_order":
            return get_order(str(args["order_id"]))
        if name == "get_price":
            return get_price(str(args["route"]), str(args["date"]))
        return {"error": f"unknown tool: {name}"}

    def _save_memory(
        self,
        session_id: str,
        user_message: str,
        answer: str,
        data: dict[str, Any],
    ) -> None:
        """保存简单上下文记忆。"""

        history = self.memory.setdefault(session_id, [])
        history.append({"role": "user", "content": user_message})
        history.append(
            {
                "role": "assistant",
                "content": answer,
                "data": data,
            }
        )
        self.memory[session_id] = history[-12:]

    def _extract_order_id(self, text: str) -> str | None:
        """提取订单号。"""

        match = re.search(r"(?:订单|order)[^\d]*(\d{3,})|(\d{3,})[^\d]*(?:订单|order)", text, re.I)
        if not match:
            return None
        return match.group(1) or match.group(2)

    def _last_order_id(self, session_id: str) -> str | None:
        """从记忆中提取最近订单号。"""

        for item in reversed(self.memory.get(session_id, [])):
            data = item.get("data") or {}
            order_data = data.get("get_order") or {}
            order = order_data.get("order") or {}
            if order.get("order_id"):
                return str(order["order_id"])
        return None

    def _is_order_intent(self, text: str) -> bool:
        """判断是否为订单/退票意图。"""

        return any(word in text for word in ["订单", "状态", "退票", "退款", "能退"])

    def _is_policy_intent(self, text: str) -> bool:
        """判断是否为规则知识库意图。"""

        return any(word in text for word in ["规则", "政策", "规定", "标准", "怎么办"])

    def _is_price_intent(self, text: str) -> bool:
        """判断是否为价格意图。"""

        return any(word in text for word in ["价格", "票价", "多少钱", "机票"])

    def _is_airline_intent(self, text: str) -> bool:
        """判断是否为机票客服相关问题。"""

        keywords = [
            "订单",
            "退票",
            "退款",
            "改签",
            "变更",
            "航班",
            "机票",
            "票价",
            "舱位",
            "旅客",
            "证件",
            "姓名",
            "行李",
            "婴儿",
            "航线",
            "起飞",
            "机场",
            "值机",
            "登机",
            "延误",
            "取消",
            "联程",
            "买错票",
        ]
        return any(word in text for word in keywords)

    def _extract_route(self, text: str) -> str:
        """提取航线。"""

        match = re.search(r"([\u4e00-\u9fa5A-Za-z]+)(?:到|-|—|>)([\u4e00-\u9fa5A-Za-z]+)", text)
        if not match:
            return "北京-上海"
        return f"{match.group(1)}-{match.group(2)}"

    def _extract_date(self, text: str) -> str:
        """提取日期。"""

        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if match:
            return match.group(0)
        return str(date.today() + timedelta(days=7))

    def _order_answer(self, data: dict[str, Any], user_message: str) -> str:
        """生成订单回复。"""

        if not data.get("found"):
            return f"未找到订单 {data['order_id']}。"
        order = data["order"]
        refund = data["refund"]
        if "退" in user_message:
            return (
                f"订单{order['order_id']}当前状态：{order['status']}。"
                f"退票判断：{refund['reason']}手续费：{refund['fee']}。"
            )
        return (
            f"订单{order['order_id']}当前状态：{order['status']}，"
            f"航班{order['flight_no']}，航线{order['route']}，起飞时间{order['departure_time']}。"
        )

    def _price_answer(self, data: dict[str, Any]) -> str:
        """生成价格回复。"""

        if not data.get("found"):
            return data["message"]
        return (
            f"{data['route']} {data['date']} {data['cabin']}票价约"
            f"{data['price']}{data['currency']}，{data['inventory']}。"
        )

    def _rag_answer(self, user_message: str, sources: list[dict[str, Any]]) -> str:
        """生成 RAG 规则回复。"""

        if not sources:
            return "暂未在知识库中找到相关规则。"
        if "退票" in user_message and self._is_policy_intent(user_message):
            filtered = [
                item
                for item in sources
                if "婴儿" not in item["title"] or "婴儿" in user_message
            ]
            items = filtered[:3] or sources[:3]
            lines = []
            for item in items:
                clean_lines = [
                    line.strip("#-0123456789. 、").strip()
                    for line in item["content"].splitlines()
                    if line.strip() and not line.strip().startswith("---")
                ]
                summary = "；".join(clean_lines[1:4])
                lines.append(f"- {item['title']}：{summary}")
            return "根据知识库：\n" + "\n".join(lines)
        top = sources[0]["content"]
        lines = [line.strip("#- ").strip() for line in top.splitlines() if line.strip()]
        summary = "；".join(lines[:5])
        return f"根据知识库：{summary}"

    def _brief_sources(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """压缩来源信息。"""

        return [
            {
                "title": item["title"],
                "score": round(item["score"], 4),
            }
            for item in sources
        ]


chat_agent = FlightAgent()
