import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from db.db import init_db
from llm.agent import chat_agent
from rag.embed import get_vector_store


app = FastAPI(title="Flight AI Customer Service Demo")
BASE_PATH = "/flight-cs"
INDEX_HTML_PATH = Path(__file__).with_name("index.html")
STATIC_PATH = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static-root")
app.mount(f"{BASE_PATH}/static", StaticFiles(directory=STATIC_PATH), name="static")


class ChatRequest(BaseModel):
    """聊天请求体。"""

    message: str = Field(..., min_length=1)
    session_id: str = "default"


class ChatResponse(BaseModel):
    """聊天响应体。"""

    session_id: str
    answer: str
    data: dict[str, Any]
    sources: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


@app.on_event("startup")
def startup() -> None:
    """启动时初始化数据库并预热 RAG。"""

    init_db()
    get_vector_store()


@app.get(f"{BASE_PATH}/health")
@app.get("/health")
def health() -> dict[str, str]:
    """健康检查。"""

    return {"status": "ok"}


@app.get(BASE_PATH, response_class=HTMLResponse)
@app.get(f"{BASE_PATH}/", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
def root() -> str:
    """Return chat page."""

    return INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.post(f"{BASE_PATH}/chat", response_model=ChatResponse)
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict[str, Any]:
    """处理多轮聊天。"""

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")
    return chat_agent.chat(session_id=request.session_id, user_message=message)


@app.post(f"{BASE_PATH}/chat/stream")
@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """流式返回聊天结果。"""

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    def event_stream() -> Iterator[str]:
        try:
            result = chat_agent.chat(session_id=request.session_id, user_message=message)
            answer = result["answer"]
            for index in range(0, len(answer), 2):
                chunk = answer[index : index + 2]
                payload = {"type": "delta", "content": chunk}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                time.sleep(0.02)
            done = {
                "type": "done",
                "sources": result["sources"],
                "tool_calls": result["tool_calls"],
            }
            yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
        except Exception as exc:
            payload = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
