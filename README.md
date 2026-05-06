# flight-ai-cs

机票 AI 客服系统 Demo，包含网页对话界面、RAG 知识库、工具调用、多轮上下文和流式输出。

## Features

- FastAPI 提供网页 UI 和聊天接口
- `/chat` 普通 JSON 聊天接口
- `/chat/stream` SSE 流式聊天接口
- FAISS + `sentence-transformers/all-MiniLM-L6-v2` 检索本地 `rag/faq.txt`
- SQLite 模拟订单数据
- DeepSeek OpenAI-compatible API 调用
- 本地兜底：无 key 时仍支持订单、票价、机票规则类问题
- 基于 `session_id` 的进程内多轮上下文记忆
- 工具函数：
  - `get_order(order_id)`
  - `get_price(route, date)`

## Tech Stack

- Python 3.11+
- FastAPI
- Uvicorn
- FAISS local index
- sentence-transformers
- SQLite
- DeepSeek API
- Docker / Docker Compose

## Project Structure

```text
flight-ai-cs/
├── main.py
├── index.html
├── llm/
│   └── agent.py
├── rag/
│   ├── embed.py
│   ├── search.py
│   └── faq.txt
├── tools/
│   ├── order.py
│   └── price.py
├── db/
│   └── db.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── docs/
│   ├── sequence-diagram.md
│   └── sequence-flow.mmd
└── .env.example
```

## Getting Started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```env
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

启动：

```bash
uvicorn main:app --reload --port 8100
```

访问：

```text
http://127.0.0.1:8100
```

## Docker

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
docker compose up --build
```

访问：

```text
http://127.0.0.1:8100
```

## API Reference

### `GET /`

客服聊天界面。

### `GET /health`

健康检查。

```bash
curl http://127.0.0.1:8100/health
```

响应：

```json
{"status":"ok"}
```

### `POST /chat`

普通聊天接口。

```bash
curl -X POST http://127.0.0.1:8100/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s1","message":"查订单123"}'
```

请求体：

```json
{
  "session_id": "s1",
  "message": "查订单123"
}
```

响应字段：

```json
{
  "session_id": "s1",
  "answer": "订单123当前状态：已出票，航班CZ8888，航线北京-上海，起飞时间2026-05-20 09:30:00。",
  "data": {
    "get_order": {
      "found": true,
      "order": {
        "order_id": "123",
        "passenger_name": "张三",
        "route": "北京-上海",
        "flight_no": "CZ8888",
        "flight_date": "2026-05-20",
        "departure_time": "2026-05-20 09:30:00",
        "status": "已出票",
        "ticket_type": "经济舱",
        "price": 860,
        "abnormal": 0
      },
      "refund": {
        "eligible": true,
        "fee": 120,
        "reason": "起飞前4小时以上可申请自愿退票，按舱位规则收取手续费。"
      }
    }
  },
  "sources": [
    {
      "title": "退票规则",
      "score": 0.8333
    }
  ],
  "tool_calls": [
    {
      "name": "get_order",
      "arguments": {
        "order_id": "123"
      }
    }
  ]
}
```

### `POST /chat/stream`

SSE 流式聊天接口，前端页面使用该接口。

```bash
curl -N -X POST http://127.0.0.1:8100/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s1","message":"退票规则"}'
```

事件格式：

```text
data: {"type":"delta","content":"根据"}

data: {"type":"done","sources":[...],"tool_calls":[...]}
```

错误响应：

- `400`：`message` 为空。
- SSE 运行时异常：返回 `{"type":"error","message":"..."}`。

## Usage Examples

```text
查订单123
这个订单能退吗
退票规则
北京到上海2026-05-20机票多少钱
```

可测试订单：

- `123`：已出票
- `456`：航班取消
- `789`：已退票

## Diagrams

- [Mermaid 时序图](docs/sequence-diagram.md)
- [主流程 PNG 图片](docs/主流程.png)
- [聊天流程 PNG 图片](docs/聊天流程.png)

## Key Implementation Notes

- `main.py`：FastAPI 应用、网页 UI、`/chat`、`/chat/stream`
- `index.html`：单页聊天界面，调用 `/chat/stream` 展示流式回复
- `llm/agent.py`：DeepSeek 调用、工具调用、本地兜底、进程内多轮记忆
- `rag/embed.py`：启动时加载 FAQ、生成 embedding、构建内存 FAISS 索引
- `rag/search.py`：FAQ 检索入口
- `tools/order.py`：订单查询和退票判断
- `tools/price.py`：模拟票价查询
- `db/db.py`：SQLite 初始化和订单读取
- `.env.example`：DeepSeek 相关环境变量占位

会话记忆保存在进程内，服务重启后会清空；SQLite 演示库位于 `db/flight.db`，启动时自动创建并写入演示订单。

## Development

```bash
python3 -m compileall main.py llm rag tools db
```

## Troubleshooting

- 未配置 `DEEPSEEK_API_KEY`：系统只使用本地兜底能力。
- 修改代码后页面没变化：使用 `uvicorn main:app --reload --port 8100`，或重启服务。
- Docker 中 key 不生效：确认 `.env` 位于 `docker-compose.yml` 同级目录。
- 首次 RAG 查询较慢：`sentence-transformers` 模型需要首次下载和加载。
