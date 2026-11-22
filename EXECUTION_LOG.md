# TASKS.md 执行日志

> 记录 `TASKS.md` 全部任务的**设计 → 编码 → 测试 → 验证 → 签收**全过程。
> 执行日期：2026-11-21

---

## 0. 环境检查记录

| 项目 | 结果 |
|------|------|
| 全局 Python | 3.14.4（缺少 fastapi 等依赖，**不可用**） |
| 项目 `.venv` | Python 3.14.4，fastapi/httpx/yaml/pandas/chromadb/pypdf 全部可用 ✅ |
| Ollama 服务 (`11434`) | **未启动**（连接被拒绝） |
| 测试策略 | 采用 `.venv` 运行；LLM 调用通过 mock `chat()` 验证，不依赖真实模型 |

> 结论：编码与静态/逻辑测试可完整执行；需要真实 LLM 的验收项将记录为"待 Ollama 启动后手工验证"。

---

## 1. 设计阶段

### 1.1 核心难点：引擎上下文传递机制

`engine.py::execute_workflow` 的上下文传递方式为平铺合并：

```python
step_inputs = {**context, **with_params}
result = await tool["func"](step_inputs)
if isinstance(result, dict):
    context.update(result)
```

即：**所有上游工具的输出都会平铺进 context，下游工具通过 `inputs.get(键名)` 读取**。引擎**不支持** `{hooks.0}` 这类模板变量插值。

### 1.2 设计决策：通用输入源选择参数 `input_from`

为保持工具单一职责、不修改引擎，设计统一辅助函数 `_tool_text(inputs, *default_keys)`：

- 若 `with` 中指定 `input_from: 某键`，则优先从该键取值；
- 否则按 `default_keys` 顺序取第一个非空值；
- 自动解包常见结构：字符串数组（取首个）、字典（取 text/summary/content/answer 等字段）、chunks 列表（拼接全部 text）。

**示例**：工作流中显式指定数据流向

```yaml
- tool: generate_hooks          # 输出 hooks: ["标题1", ...]
- tool: expand_article
  with:
    input_from: hooks           # 明确从 hooks 取值，而非原始 text
- tool: rewrite_style
  with:
    input_from: expanded        # 从扩写结果取值
```

该方案是 TASKS.md "方案A（工具内部读取上一步结果）"的通用化实现，无需修改引擎代码。

### 1.3 16 个工具接口设计

| # | 工具名 | 输入（含 input_from） | 输出 | 取值回退链 |
|---|--------|----------------------|------|-----------|
| 1 | `polish_copy` | text, style | polished, style, tips | text←rewritten/expanded/summary |
| 2 | `generate_hooks` | text, count, tone | hooks, count | text←summary/expanded |
| 3 | `rewrite_style` | text, style | rewritten | text←expanded/summary |
| 4 | `expand_article` | text, target_length, format | expanded | text←hooks/summary |
| 5 | `meeting_notes` | text | todos, decisions, risks, owners | text←body/content |
| 6 | `task_extractor` | text | tasks, count | text←todos/summary |
| 7 | `email_compose` | points, tone, recipient | subject, body | points←todos拼接/text/summary |
| 8 | `slide_outline` | text, pages | slides, total_pages | text←answer/summary/chunks |
| 9 | `feynman_explain` | concept, audience, text | explanation, analogy, key_points | concept←question/text；材料←chunks |
| 10 | `mindmap_outline` | text, max_depth | outline | text←summary/answer/content |
| 11 | `generate_quiz` | text, count, difficulty | questions, count | text←chunks/summary/answer |
| 12 | `flashcards` | text, count | cards, count | text←chunks/questions/summary |
| 13 | `prompt_doctor` | prompt, goal | diagnosis, optimized, suggestions | prompt←text |
| 14 | `tool_matchmaker` | requirement | tools, reason, suggested_workflow | requirement←text；动态注入工具清单 |
| 15 | `workflow_advisor` | name | current, issues, suggestions | name←workflow/text；延迟 import engine |
| 16 | `result_critic` | content, criteria | score, strengths, weaknesses, suggestions | content←summary/answer/reply/text |

**循环导入处理**：`workflow_advisor` 需要 `engine.load_workflow_raw`，但 `engine.py` 顶层已 import `tools`。采用**函数内延迟导入**（与 `rag.py` 中 `from app.config import RAG_EMBED_BATCH` 同一模式）避免循环导入。

### 1.4 4 个工作流数据流设计

| 工作流 | 数据流 |
|--------|--------|
| `content_factory` | 原始卖点 → generate_hooks(hooks) → expand_article(input_from=hooks) → rewrite_style(input_from=expanded) → polish_copy(input_from=rewritten) |
| `study_buddy` | 问题 → rag_search(chunks) → feynman_explain(input_from=chunks, concept 取自原始 text) → generate_quiz(input_from=chunks) → flashcards(input_from=chunks) |
| `meeting_secretary` | 会议记录 → meeting_notes(todos) → task_extractor → write_db → email_compose(自动拼接 todos 为要点) |
| `support_qa` | 客服文本 → classify_email → sentiment_aspect(summary) → result_critic(input_from=summary, score) → alert_ops(condition: score < 6) |

> 工具基数：现有 30 个 + 新增 16 个 = **46 个**（TASKS.md 中"≥34"为估算值，以实际 46 为准）。

---

## 2. 编码阶段

| 阶段 | 任务 | 产出 | 状态 |
|------|------|------|------|
| 一 | 1-4 | `polish_copy`、`generate_hooks`、`rewrite_style`、`expand_article` + 通用 `_tool_text()` | ✅ |
| 二 | 5-8 | `meeting_notes`、`task_extractor`、`email_compose`、`slide_outline` | ✅ |
| 三 | 9-12 | `feynman_explain`、`mindmap_outline`、`generate_quiz`、`flashcards` | ✅ |
| 四 | 13-16 | `prompt_doctor`、`tool_matchmaker`、`workflow_advisor`、`result_critic` | ✅ |
| 五 | 17-20 | 4 个工作流写入 `default.yaml` | ✅ |

**编码中修复的设计缺陷**：`feynman_explain` 的 concept 初版用 `_tool_text(inputs, "text")` 取值，在工作流中会被 `input_from: chunks` 劫持，导致把检索片段当成待解释概念。已改为直接读取原始 `text`/`question` 字段，参考材料才走 `input_from`。

**涉及文件**：
- `app/tools.py`：新增 16 个工具 + 1 个辅助函数（约 490 行）
- `app/workflows/default.yaml`：新增 4 个工作流（约 59 行）

---

## 3. 测试与验证阶段

### 3.1 注册验证
```
python scripts/check_tools.py
→ ✅ tools.py 加载成功，已注册 46 个工具（30 原有 + 16 新增）
```

### 3.2 YAML 加载验证
```
load_workflows() → 工作流总数 16
新增 4 个全部加载成功，步骤顺序与设计一致
```

### 3.3 离线功能测试
```
脚本：scripts/test_new_tools.py（mock chat / rag.search，不依赖 Ollama）
结果：PASS=72  FAIL=0
覆盖：工具注册(33) + _tool_text(6) + 工具功能(19) + 工作流编排(14)
```

测试过程中发现并修复的问题：
1. mock 匹配仅检查 `prompt` 参数，遗漏 `system` 参数 → 修正后覆盖全部工具
2. `chunks 拼接`/`长度截断` 测试用例未传入 key → 修正测试调用

### 3.4 API 端点验证
```
启动 uvicorn app.main:app --port 8123
→ /health          : ok
→ /tools           : 46 个工具
→ /workflows       : 16 个工作流
→ 4 个新工作流均在线
```

### 3.5 未能执行的验证项
因 **Ollama 服务未启动**（11434 端口连接被拒绝），以下真实模型调用验证无法执行，需用户启动 Ollama 后手工完成：
- 各工具真实 LLM 输出质量（如润色效果、出题质量）
- 4 个工作流的端到端真实运行（Streamlit 页面）
- RAG 知识库检索（`study_buddy` 依赖已入库文档）

---

## 4. 签收

| 项目 | 结果 |
|------|------|
| TASKS.md 任务 1-23 | 全部完成并勾选 ✅ |
| 新增工具 | 16 个（总数 46） |
| 新增工作流 | 4 个（总数 16） |
| 离线测试 | 72/72 PASS |
| API 验证 | 通过 |
| Lint 检查 | 无新增错误 |
| 文档更新 | 架构文档、README、TASKS.md 已同步 |

**签收结论**：TASKS.md 中定义的 16 个工具与 4 个工作流已完成设计、编码与离线验证，全部功能逻辑正确、工作流串联无误。真实 LLM 调用验证因 Ollama 未启动而保留为待办项，不影响代码交付。

**签收时间**：2026-11-21
**环境**：Python 3.14.4 (.venv) / FastAPI / mock 测试模式

