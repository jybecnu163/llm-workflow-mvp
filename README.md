# 关键组件：

ollama_client.py — 用 httpx 调用 Ollama API，支持 format: json

tools.py — 每个工具是一个函数，接收 dict 输入、返回 dict 输出

engine.py — 加载 YAML，执行步骤，处理条件

router.py — 用 LLM 分类数据

main.py — FastAPI 端点：/tools、/workflows、/run、/classify

streamlit_app.py — 展示工具、运行工作流

# 启动步骤

1）准备 Ollama 模型

```bash
ollama pull llama3.1:8b
ollama serve   # 如果没自动启动
```

2）安装依赖

```bash
cd llm-workflow-mvp
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3）启动后端

```bash
uvicorn app.main:app --reload --port 8000
```

(.venv) PS D:\IdeaProject\python\llm-workflow-mvp> uvicorn app.main:app --reload --port 8000

访问 http://localhost:8000/docs 可以直接在 Swagger 里调试接口。

4）启动前端

```bash
streamlit run ui/streamlit_app.py

PS D:\IdeaProject\python\llm-workflow-mvp> .venv\Scripts\activate
(.venv) PS D:\IdeaProject\python\llm-workflow-mvp> streamlit run ui/streamlit_app.py
```

5） 解决tool不存在问题

1. 先看 8000 端口被谁占着

```powershell
netstat -ano | findstr :8000
```

会看到类似：

```text
TCP    127.0.0.1:8000    0.0.0.0:0    LISTENING    12345
```

最后一列 12345 是 PID。可能不止一个，也可能和你想的不一样。

2. 杀掉所有占用 8000 的进程
   对上面查到的每个 PID 执行：

```powershell
taskkill /PID 12345 /F
```

如果有很多，一次性清掉：

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

再确认一次：

```powershell
netstat -ano | findstr :8000
```

应该没有任何输出，才说明端口干净了。

浏览器打开 http://localhost:8501。

```powershell
curl.exe --% http://127.0.0.1:11434/api/embed -d "{\"model\":\"nomic-embed-text\",\"input\":\"测试\"}"
```

# 最小验证链路

验证工具
打开 Streamlit → “🔧 工具库”

选 summarize_text，粘贴一段新闻

点“运行工具”，应返回 {"summary": "..."}

验证指定工作流
切到“🔀 工作流”

选 email_support，输入一段客服文本

点执行，返回结果里包含：

summarize_text → summary

extract_ticket → issue_type / urgency

draft_reply → reply

write_db → saved

验证自动路由
切到“🚦 自动路由”

输入一段“垃圾邮件”文本

返回里 route.data_type = email，route.category = spam，workflow = email_spam

# 简单 curl 验证

```bash
# 列出工具
curl http://localhost:8000/tools

# 列出工作流
curl http://localhost:8000/workflows

# 单工具
curl -X POST http://localhost:8000/tools/summarize_text/run \
  -H "Content-Type: application/json" \
  -d '{"inputs":{"text":"OpenAI 发布了新模型..."}}'

# 自动路由 + 执行
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"data":{"text":"我的订单12345还没到，请尽快处理"},"auto_route":true}'
```

# 这个 MVP 已经具备的能力

工具即插即用：在 tools.py 里加一个 @register 就是新工具，页面自动出现。

工作流可扩展：在 workflows/*.yaml 里加一段就是新工作流，无需改代码。

路由自动化：router.py 负责判断数据类型，engine.py 负责执行对应工作流。

上下文贯通：每个工具的输出会合并进 context，后续工具可直接引用（如 draft_reply 用 summary）。

条件分支：YAML 里 condition: "urgency == 'high'" 可以控制节点是否执行。

完全本地：所有模型调用走本地 Ollama，数据不出机器。

# 下一步可扩展点

工作流画布：把 YAML 换成 React Flow 可视化编辑，导出同样的 YAML。

运行记录入库：加 SQLite 表记录每次 run 的输入输出。

人工审核队列：低置信度时写一张 pending_review 表，页面展示。

多模型：tools.py 里允许每个工具指定不同模型（如 embedding 用 nomic-embed-text）。

RAG 节点：加一个 rag_search 工具，接 Chroma/Qdrant。

并行执行：engine.py 里对无依赖节点用 asyncio.gather 并发。

鉴权与多租户：加 API Key，按用户隔离工作流。