下面这份可以直接作为新提示词用：

```text
你是一个资深 Python 后端工程师 + AI 系统架构师 + 前端产品工程师。

请一次性实现一个“机票 AI 客服系统 Demo”，要求可以直接运行、可交互、可测试。

语言要求：
- 所有说明使用中文
- 代码、命令、路径保持原语言
- 不要写伪代码
- 不要省略 import

目标效果：
- 打开 http://127.0.0.1:8000 后看到一个客服聊天界面
- 支持输入问题并流式显示 AI 回复
- 回复前显示主流三点跳动“思考中”动画
- 支持多轮对话，例如先问“查订单123”，再问“这个订单能退吗”
- 不在界面展示 session_id、工具名、知识库来源等调试信息
- 非机票业务问题不要乱套知识库；如果未配置大模型 key，应明确提示

技术要求：
- 后端框架：FastAPI
- 前端：直接由 FastAPI 返回 HTML/CSS/JS，不引入前端框架
- 流式输出：SSE 接口 `/chat/stream`
- 普通接口：`/chat`
- 向量检索：FAISS 本地
- Embedding：sentence-transformers，模型 `all-MiniLM-L6-v2`
- 数据库：SQLite
- LLM：DeepSeek，使用 OpenAI-compatible SDK
- DeepSeek key 从环境变量 `DEEPSEEK_API_KEY` 读取
- 支持 Docker / docker-compose
- 必须包含 README.md、requirements.txt、Dockerfile、docker-compose.yml、.env.example、.gitignore

功能要求：
1. 聊天接口
   - `POST /chat`
   - 请求字段：`session_id`、`message`
   - 返回字段：`session_id`、`answer`、`data`、`sources`、`tool_calls`
   - 支持简单上下文记忆

2. 流式接口
   - `POST /chat/stream`
   - 使用 SSE 返回
   - 前端必须调用该接口
   - 答案要逐段显示

3. 网页聊天界面
   - 首页 `/` 是聊天界面，不是 JSON
   - 包含欢迎语、输入框、发送按钮、快捷问题
   - 快捷问题至少包含：
     - 查订单123
     - 这个订单能退吗
     - 退票规则
     - 北京到上海2026-05-20机票多少钱
   - 发消息后显示三点跳动思考动画
   - 不显示 session 输入框
   - 不显示“工具：xxx”“知识库：xxx”等调试 meta

4. RAG 知识库
   - 从本地 `rag/faq.txt` 加载
   - 实现 FAQ 切分、embedding、FAISS 检索
   - “退票规则”“改签规则”“证件信息错误怎么办”等问题走知识库
   - 低相关、非航空问题不要强行使用知识库

5. 工具调用
   实现并让 LLM 可调用：
   - `get_order(order_id)`
   - `get_price(route, date)`

6. 模拟业务逻辑
   - SQLite 初始化订单数据
   - 订单号至少包含：
     - 123：已出票，北京-上海
     - 456：航班取消
     - 789：已退票
   - 查询订单状态
   - 判断退票规则
   - 查询模拟票价
   - 返回结构化数据 + 自然语言

7. DeepSeek 调用
   - 环境变量：
     - `DEEPSEEK_API_KEY`
     - `DEEPSEEK_MODEL=deepseek-chat`
     - `DEEPSEEK_BASE_URL=https://api.deepseek.com`
   - 没有 key 或调用失败时，本地兜底只处理机票客服相关问题
   - 非机票问题在无 key 时返回：当前未配置或未连通 DeepSeek，本地兜底只支持机票客服问题

项目结构必须为：

flight-ai-cs/
├── main.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
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

代码要求：
- 每个文件完整可运行
- 每个函数加简短注释
- KISS，避免过度设计
- 不主动引入不必要依赖
- 不修改无关文件
- 不把真实 key 写进代码或 README

README 必须包含：
- 项目说明
- 功能列表
- 技术栈
- 项目结构
- 本地启动
- Docker 启动
- 环境变量说明
- curl 示例：
  - `/health`
  - `/chat`
  - `/chat/stream`
- 常见问题

最后必须自检：
- `python -m py_compile` 通过
- `uvicorn main:app` 可启动
- `/` 返回聊天界面
- `/chat` 可返回结果
- `/chat/stream` 可流式返回
- 输入“查订单123”能调用订单工具
- 输入“退票规则”能走 RAG
- 输入“中国的首都在哪里”在无 key 时不能乱套知识库

完成后只输出：
1. 生成/修改的文件
2. 启动命令
3. 测试命令
4. 自检结果
```
