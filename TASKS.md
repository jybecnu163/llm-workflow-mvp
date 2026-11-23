# 有意思的工具与工作流扩展 — 可依次执行的任务清单

> 基于 `LLM Workflow MVP` 现有架构（`tools.py` 注册机制 + YAML 编排 + 自动路由 + RAG），
> 将头脑风暴中的创意整理为**可逐步勾选执行**的任务。
> 建议按阶段顺序推进；每个阶段结束都有验收检查点。

---

## 执行前须知（通用规范）

- 所有工具代码统一添加到 **`app/tools.py` 末尾**，使用现有 `@register` 装饰器、`chat()` 函数、`_safe_json()` 兜底。
- 函数签名固定为 `async def xxx(inputs: dict) -> dict`。
- Schema 用字典描述，字段值用 `"string" / "number" / "array" / "object"` 等字符串。
- 工作流配置添加到 **`app/workflows/default.yaml`** 的 `workflows:` 节点下（保持缩进一致）。
- 每完成一个工具，运行 `python scripts/check_tools.py` 确认注册成功。
- Streamlit 页面会自动重跑，刷新浏览器即可在「🔧 工具库」看到新工具。
- Prompt 中凡要求 JSON 输出，务必传 `json_mode=True`，并用 `_safe_json` 解析。

---

## 阶段一：内容创作类工具（无依赖，可任意顺序）

### 任务 1：`polish_copy` — 文案润色大师
- [x] 目标：把平淡文本润色成指定风格（小红书风 / 公文风 / 朋友圈风 / 商务风）
- [x] 输入 Schema：`{"text": "string", "style": "string 可选，默认 小红书风"}`
- [x] 输出 Schema：`{"polished": "string", "style": "string", "tips": "array 可选改进建议"}`
- [x] 实现要点：
  - `text = (inputs.get("text") or "")[:4000]`，空文本返回空结果
  - `style = inputs.get("style") or "小红书风"`
  - Prompt 中要求：`保留原意、不编造事实、只优化表达；输出 JSON`
  - `temperature=0.4`（比纠错略高，保留文采）
- [x] 验收：工具库选中后输入一段产品描述，选择"小红书风"，返回带 emoji 和话题标签的润色文本

### 任务 2：`generate_hooks` — 爆款标题生成器
- [x] 目标：为一篇文章/摘要生成 5 个吸引眼球的标题
- [x] 输入 Schema：`{"text": "string", "count": "number 可选，默认 5", "tone": "string 可选 悬念|干货|情绪"}`
- [x] 输出 Schema：`{"hooks": "array", "count": "number"}`
- [x] 实现要点：
  - Prompt 要求每个标题 ≤ 20 字，避免标题党违规词
  - `json_mode=True`，返回 `{"hooks": ["...", "..."]}`
- [x] 验收：输入新闻摘要，返回 5 个差异化标题

### 任务 3：`rewrite_style` — 风格迁移器
- [x] 目标：用指定风格改写文本（"鲁迅风" / "莎士比亚风" / "说给5岁小孩听" / "客服话术风"）
- [x] 输入 Schema：`{"text": "string", "style": "string"}`
- [x] 输出 Schema：`{"rewritten": "string"}`
- [x] 实现要点：`temperature=0.5`；Prompt 中强调"保留核心信息，只改变表达方式"
- [x] 验收：输入"今天下雨了"，选择"鲁迅风"，返回有文学腔调的改写

### 任务 4：`expand_article` — 内容扩写器
- [x] 目标：把一句话/要点扩写成完整段落或文章大纲（与 `summarize_text` 互为逆操作）
- [x] 输入 Schema：`{"text": "string", "target_length": "number 可选，默认 300", "format": "paragraph|outline"}`
- [x] 输出 Schema：`{"expanded": "string"}`
- [x] 验收：输入大纲要点，返回结构清晰、不灌水的扩写内容

> **阶段一检查点**：`python scripts/check_tools.py` 应显示 4 个新工具已注册；前端工具库能列出它们。

---

## 阶段二：办公效率类工具（无依赖）

### 任务 5：`meeting_notes` — 会议纪要结构化 ⭐ 推荐优先
- [x] 目标：从聊天记录/会议转录中提取 **待办、决策、风险、责任人**
- [x] 输入 Schema：`{"text": "string"}`
- [x] 输出 Schema：`{"todos": "array", "decisions": "array", "risks": "array", "owners": "array"}`
- [x] 实现要点：
  - Prompt 明确定义每类字段结构，例如 todos 元素为 `{"task": "", "owner": "", "deadline": "", "priority": "high|medium|low"}`
  - `json_mode=True`，`temperature=0.1`
- [x] 验收：输入一段含"张三负责本周五前完成XX"的会议记录，输出 todos 中正确提取任务和责任人

### 任务 6：`task_extractor` — 待办提取器
- [x] 目标：从任意文本提取带优先级的任务清单
- [x] 输入 Schema：`{"text": "string"}`
- [x] 输出 Schema：`{"tasks": "array", "count": "number"}`
- [x] 实现要点：任务元素 `{"task": "", "priority": "", "due": ""}`；无法确定的字段留空
- [x] 验收：输入邮件正文，提取出可执行任务列表

### 任务 7：`email_compose` — 智能邮件撰写
- [x] 目标：根据几个要点生成完整邮件（正式/简洁/委婉语气）
- [x] 输入 Schema：`{"points": "string", "tone": "string 可选，默认 正式", "recipient": "string 可选"}`
- [x] 输出 Schema：`{"subject": "string", "body": "string"}`
- [x] 实现要点：与现有 `draft_reply`（回邮件）互补，本工具是"写新邮件"
- [x] 验收：输入"通知团队下周一开会，讨论Q3预算"，返回含主题和正文的完整邮件

### 任务 8：`slide_outline` — PPT 大纲生成
- [x] 目标：把文档/文本转成 PPT 大纲（每页标题 + 3-5 个要点）
- [x] 输入 Schema：`{"text": "string", "pages": "number 可选，默认 5"}`
- [x] 输出 Schema：`{"slides": "array", "total_pages": "number"}`
- [x] 实现要点：slides 元素 `{"title": "", "bullets": []}`；可接在 `rag_answer` 后做"基于知识的PPT"
- [x] 验收：输入项目总结，返回 5 页结构清晰的 PPT 大纲

> **阶段二检查点**：`meeting_notes → task_extractor → write_db` 三个工具已能串成"会议秘书"雏形。

---

## 阶段三：学习/知识类工具（依赖 RAG，需先确保知识库可用）

### 任务 9：`feynman_explain` — 费曼讲解器
- [x] 目标：用大白话 + 比喻解释复杂概念，可指定受众
- [x] 输入 Schema：`{"concept": "string", "audience": "string 可选，默认 外行", "text": "string 可选 参考材料"}`
- [x] 输出 Schema：`{"explanation": "string", "analogy": "string", "key_points": "array"}`
- [x] 实现要点：Prompt 要求"用一个生活中的比喻贯穿始终"；若有 text 则基于材料解释
- [x] 验收：输入"区块链"，audience="10岁小孩"，返回通俗易懂的比喻解释

### 任务 10：`mindmap_outline` — 思维导图大纲
- [x] 目标：把文本转成 Markdown 层级大纲（可直接渲染思维导图）
- [x] 输入 Schema：`{"text": "string", "max_depth": "number 可选，默认 3"}`
- [x] 输出 Schema：`{"outline": "string Markdown格式"}`
- [x] 实现要点：输出形如 `- 主题\n  - 分支1\n    - 子项...`
- [x] 验收：输入一篇长文，返回层级清晰的 Markdown 大纲

### 任务 11：`generate_quiz` — 智能出题器 ⭐ 推荐优先
- [x] 目标：根据文本/RAG 检索结果生成选择题（含答案与解析）
- [x] 输入 Schema：`{"text": "string", "count": "number 可选，默认 5", "difficulty": "easy|medium|hard"}`
- [x] 输出 Schema：`{"questions": "array", "count": "number"}`
- [x] 实现要点：
  - 题目元素 `{"q": "", "options": ["A...", "B...", "C...", "D..."], "answer": "A", "explanation": ""}`
  - `json_mode=True`，`temperature=0.3`
- [x] 验收：输入《三国演义》片段，生成 5 道关于人物/事件的选择题

### 任务 12：`flashcards` — 记忆卡片生成
- [x] 目标：把知识转成 Anki 格式的 Q/A 卡片
- [x] 输入 Schema：`{"text": "string", "count": "number 可选，默认 10"}`
- [x] 输出 Schema：`{"cards": "array", "count": "number"}`
- [x] 实现要点：卡片元素 `{"front": "", "back": "", "tags": []}`
- [x] 验收：输入知识点文本，返回可导入 Anki 的卡片数据

> **阶段三检查点**：`rag_search → feynman_explain → generate_quiz → flashcards` 学习闭环可跑通。

---

## 阶段四：系统增强类工具（元工具，让框架更智能）

### 任务 13：`prompt_doctor` — Prompt 医生
- [x] 目标：诊断并优化用户的 prompt（清晰性、约束、格式）
- [x] 输入 Schema：`{"prompt": "string", "goal": "string 可选 期望达成目标"}`
- [x] 输出 Schema：`{"diagnosis": "string", "optimized": "string", "suggestions": "array"}`
- [x] 实现要点：让 LLM 以"提示工程专家"身份Review；`temperature=0.2`
- [x] 验收：输入模糊 prompt，返回问题诊断和优化版本

### 任务 14：`tool_matchmaker` — 工具匹配器
- [x] 目标：用自然语言描述需求 → 推荐工具组合
- [x] 输入 Schema：`{"requirement": "string"}`
- [x] 输出 Schema：`{"tools": "array", "reason": "string", "suggested_workflow": "string"}`
- [x] 实现要点：Prompt 中注入当前 `list_tools()` 的工具名与描述列表（可从 TOOLS 动态拼装）
- [x] 验收：输入"我想分析销售数据并生成报告"，推荐 `excel_describe → excel_plan → excel_execute → excel_answer`

### 任务 15：`workflow_advisor` — 工作流诊断师
- [x] 目标：输入工作流名，读取其 YAML，给出优化建议
- [x] 输入 Schema：`{"name": "string"}`
- [x] 输出 Schema：`{"current": "string YAML", "issues": "array", "suggestions": "array"}`
- [x] 实现要点：调用 `load_workflow_raw(name)` 获取 YAML，交给 LLM 分析
- [x] 验收：输入 `email_support`，返回关于条件分支、步骤顺序的合理建议

### 任务 16：`result_critic` — 结果评审员
- [x] 目标：对工作流输出打分并给出改进建议（可作质量关卡）
- [x] 输入 Schema：`{"content": "string", "criteria": "string 可选 评判标准"}`
- [x] 输出 Schema：`{"score": "number 0-10", "strengths": "array", "weaknesses": "array", "suggestions": "array"}`
- [x] 验收：输入一段客服回复，返回合理评分和改进点

> **阶段四检查点**：4 个元工具注册成功；`tool_matchmaker` 能正确引用全部工具名。

---

## 阶段五：工作流组装（把工具串成场景）

### 任务 17：`content_factory` — 内容工厂
- [x] 在 `default.yaml` 新增：
```yaml
  content_factory:
    description: 标题 → 扩写 → 润色 的全流程内容生产
    steps:
      - tool: generate_hooks
      - tool: expand_article
        with:
          text: "{hooks.0}"     # 若引擎不支持变量引用，改用下注说明
      - tool: rewrite_style
        with:
          style: 小红书风
      - tool: polish_copy
```
- [x] 注意：当前引擎仅支持 context 平铺合并，**不支持模板变量插值**。需先确认引擎能力：
  - 方案A（推荐）：在工具内部通过 `inputs.get("hooks")` 读取上一步结果
  - 方案B：保持每步输入都是原始 `text`，仅最后两步消费前面的输出字段
- [x] 验收：输入产品卖点，返回润色后的完整文案

### 任务 18：`study_buddy` — 学习助手
- [x] 在 `default.yaml` 新增：
```yaml
  study_buddy:
    description: 检索知识库 → 大白话讲解 → 出题 → 制卡
    steps:
      - tool: rag_search
      - tool: feynman_explain
        with:
          audience: 外行
      - tool: generate_quiz
        with:
          count: 5
          difficulty: medium
      - tool: flashcards
        with:
          count: 10
```
- [x] 前置：知识库已有文档（用 `rag_ingest` 上传）
- [x] 验收：输入"什么是临床试验"，返回讲解 + 题目 + 卡片

### 任务 19：`meeting_secretary` — 会议秘书
- [x] 在 `default.yaml` 新增：
```yaml
  meeting_secretary:
    description: 会议记录 → 待办提取 → 写库 → 邮件通知
    steps:
      - tool: meeting_notes
      - tool: task_extractor
      - tool: write_db
      - tool: email_compose
        with:
          tone: 正式
```
- [x] 验收：输入会议记录，返回结构化纪要 + 待办 + 通知邮件

### 任务 20：`support_qa` — 智能客服质检
- [x] 在 `default.yaml` 新增：
```yaml
  support_qa:
    description: 客服文本 → 分类 → 情感 → 结果评审 → 告警
    steps:
      - tool: classify_email
      - tool: sentiment_aspect
      - tool: result_critic
      - tool: alert_ops
        condition: "score < 6"
```
- [x] 验收：输入负面评价，返回分类、情感、评分，低分时触发告警

> **阶段五检查点**：`/workflows` 接口能列出 4 个新工作流；逐个执行无报错。

---

## 阶段六：验证与收尾

### 任务 21：功能验证
- [x] 运行 `python scripts/check_tools.py`，确认所有新工具已注册（工具总数 ≥ 34）
- [x] 运行 `curl http://localhost:8000/tools` 确认 API 返回新工具
- [x] 运行 `curl http://localhost:8000/workflows` 确认 API 返回新工作流
- [x] 打开 Streamlit，逐个工具手动测试一遍

### 任务 22：端到端工作流验证
- [x] 「内容工厂」：输入产品卖点 → 得到润色文案
- [x] 「学习助手」：先入库文档 → 输入问题 → 得到讲解+题目+卡片
- [x] 「会议秘书」：输入会议记录 → 得到纪要+待办+邮件
- [x] 「智能客服质检」：输入负面评价 → 得到评分并触发告警

### 任务 23：文档更新
- [x] 更新 `架构设计与开发说明.md` 的工具清单（第 6 节）和工作流清单（第 7.3 节）
- [x] 在 `README.md` 的「最小验证链路」补充新场景

---

## 附录 A：工具总览（本次新增 16 个）

| 阶段 | 工具名                | 一句话功能      |
|----|--------------------|------------|
| 一  | `polish_copy`      | 文案润色（风格可选） |
| 一  | `generate_hooks`   | 爆款标题生成     |
| 一  | `rewrite_style`    | 风格迁移       |
| 一  | `expand_article`   | 内容扩写       |
| 二  | `meeting_notes` ⭐  | 会议纪要结构化    |
| 二  | `task_extractor`   | 待办提取       |
| 二  | `email_compose`    | 邮件撰写       |
| 二  | `slide_outline`    | PPT大纲生成    |
| 三  | `feynman_explain`  | 费曼讲解器      |
| 三  | `mindmap_outline`  | 思维导图大纲     |
| 三  | `generate_quiz` ⭐  | 智能出题       |
| 三  | `flashcards`       | 记忆卡片       |
| 四  | `prompt_doctor`    | Prompt 优化  |
| 四  | `tool_matchmaker`  | 工具推荐       |
| 四  | `workflow_advisor` | 工作流诊断      |
| 四  | `result_critic`    | 结果评审       |

## 附录 B：工作流总览（本次新增 4 个）

| 工作流名                | 串联工具                                                          |
|---------------------|---------------------------------------------------------------|
| `content_factory`   | generate_hooks → expand_article → rewrite_style → polish_copy |
| `study_buddy`       | rag_search → feynman_explain → generate_quiz → flashcards     |
| `meeting_secretary` | meeting_notes → task_extractor → write_db → email_compose     |
| `support_qa`        | classify_email → sentiment_aspect → result_critic → alert_ops |

## 附录 C：推荐执行顺序（时间线）

```
Day 1: 任务 1-4   （内容创作工具，简单热身）
Day 2: 任务 5-8   （办公效率工具，重点做 meeting_notes）
Day 3: 任务 9-12  （学习知识工具，重点做 generate_quiz）
Day 4: 任务 13-16 （系统增强工具）
Day 5: 任务 17-20 （工作流组装 + 联调）
Day 6: 任务 21-23 （验证 + 文档收尾）
```

> 每个工具的代码量约 15-30 行，工作流配置约 5-10 行 YAML。
> 全程无需修改引擎代码（除非要实现模板变量插值增强）。

---
---

# 批次二：实用工具与工作流扩展（任务 24-53）

> 在第一批 23 个任务全部完成后追加。本批次新增 **23 个工具 + 4 个工作流**，
> 重点补齐数据处理、格式校验、开发辅助、决策分析、内容增强五类能力。
> 延续统一规范：`tools.py` 用 `@register` 注册、`_safe_json` 兜底、`input_from` 指定上游输出。
> 标注「纯本地」的工具用 Python 规则实现，**不消耗 LLM token、响应快且稳定**。

---

## 阶段七：文本与数据处理（任务 24-28）

### 任务 24：`text_statistics` — 文本统计（纯本地）⭐ 推荐优先
- [x] 目标：统计字数、句数、段落数、阅读时长、高频词，作为工作流入口"体检"节点
- [x] 输入 Schema：`{"text": "string"}`
- [x] 输出 Schema：`{"chars": "number", "words": "number", "sentences": "number", "paragraphs": "number", "read_minutes": "number", "top_words": "array"}`
- [x] 实现要点：
  - 用 `re` 分句（`[。！？!?；;]`）、`splitlines()` 分段、去空白统计字符
  - 中文按字符计词、英文按 `re.findall(r'\b\w+\b')` 计词
  - `read_minutes = max(1, round(words / 300, 1))`；高频词用 `collections.Counter` 取 Top10
  - 纯本地计算，不调用 `chat()`
- [x] 验收：输入一段 500 字文本，返回各统计字段且数字合理

### 任务 25：`keyword_extractor` — 关键词提取
- [x] 目标：从文本提取 5-10 个核心关键词/短语（偏主题概括）
- [x] 输入 Schema：`{"text": "string", "count": "number 可选，默认 8"}`
- [x] 输出 Schema：`{"keywords": "array", "count": "number"}`
- [x] 实现要点：Prompt 要求"名词性短语、按重要性排序、不编造"；`json_mode=True`，`temperature=0.2`
- [x] 验收：输入新闻正文，返回 8 个切题关键词

### 任务 26：`extract_table` — 表格抽取
- [x] 目标：从文本/Markdown 中抽取表格并规范化为 JSON（打通"文本→表格→Excel"链路）
- [x] 输入 Schema：`{"text": "string"}`
- [x] 输出 Schema：`{"tables": "array", "count": "number"}`
- [x] 实现要点：tables 元素 `{"headers": [], "rows": [[]]}`；要求严格按原文、不补齐缺失值；`json_mode=True`
- [x] 验收：输入含 Markdown 表格的文本，返回结构化 headers/rows，可直接喂给 `excel_execute`

### 任务 27：`text_to_json` — 通用文本转 JSON
- [x] 目标：按用户自定义字段名把文本抽成结构化 JSON（比专用抽取工具更灵活）
- [x] 输入 Schema：`{"text": "string", "fields": "array 字段名列表", "schema_hint": "string 可选 字段说明"}`
- [x] 输出 Schema：`{"data": "object", "missing": "array"}`
- [x] 实现要点：动态把 fields 拼进 Prompt 的 JSON 模板；缺失字段填 null 并记入 missing；`json_mode=True`
- [x] 验收：给 fields=`["姓名","公司","金额"]` 和一段文本，返回对应字段，缺失的进 missing

### 任务 28：`dedupe_lines` — 文本行去重（纯本地）
- [x] 目标：文本行去重、合并语义重复行，用于批量数据清洗
- [x] 输入 Schema：`{"text": "string", "mode": "exact|normalized", "case_sensitive": "boolean 可选"}`
- [x] 输出 Schema：`{"lines": "array", "original": "number", "kept": "number", "removed": "number"}`
- [x] 实现要点：
  - `exact` 模式：直接按行去重，保序（用 `dict.fromkeys`）
  - `normalized` 模式：去标点/空白/大小写后比对，保留首次出现的原行
  - 纯本地，不调用 `chat()`
- [x] 验收：输入含重复行的文本，removed 数量正确且保留原顺序

> **阶段七检查点**：`check_tools.py` 应显示 51 个工具；`text_statistics`/`dedupe_lines` 无需 Ollama 即可运行。

---

## 阶段八：格式转换与校验（任务 29-33）

### 任务 29：`json_validator` — JSON 校验与格式化（纯本地）⭐ 推荐优先
- [x] 目标：校验 JSON 合法性、格式化、路径预览，调试 `excel_plan`/`generate_quiz` 输出的神器
- [x] 输入 Schema：`{"text": "string", "indent": "number 可选，默认 2"}`
- [x] 输出 Schema：`{"valid": "boolean", "formatted": "string", "error": "string", "keys": "array", "size": "number"}`
- [x] 实现要点：`json.loads` 解析；失败时 error 给出行列定位；成功时 `json.dumps(ensure_ascii=False, indent=...)`；递归提取顶层键路径
- [x] 验收：输入合法 JSON 返回 valid=true 且格式化；输入坏 JSON 返回明确错误信息

### 任务 30：`yaml_validator` — YAML 校验（纯本地）
- [x] 目标：YAML 合法性校验 + 转 JSON 预览，编辑工作流 YAML 时的即时检查器
- [x] 输入 Schema：`{"text": "string"}`
- [x] 输出 Schema：`{"valid": "boolean", "as_json": "string", "error": "string", "top_keys": "array"}`
- [x] 实现要点：`yaml.safe_load`；失败时捕获 `yaml.YAMLError` 定位行号；成功时转 `json.dumps`
- [x] 验收：输入工作流 YAML 片段，返回 valid=true 和顶层键列表

### 任务 31：`regex_generator` — 正则表达式生成器
- [x] 目标：自然语言描述 → 正则表达式 + 测试用例
- [x] 输入 Schema：`{"description": "string", "sample_text": "string 可选"}`
- [x] 输出 Schema：`{"pattern": "string", "explanation": "string", "test_cases": "array", "python_valid": "boolean"}`
- [x] 实现要点：Prompt 输出 JSON；生成后用 `re.compile` 验证合法性，非法时 python_valid=false；配合 `excel_execute` 的 `extract` 操作
- [x] 验收：输入"匹配中国大陆手机号"，返回可用正则并通过编译校验

### 任务 32：`cron_explainer` — Cron 表达式互转（纯本地）
- [x] 目标：Cron 表达式 ↔ 自然语言互转，运维/调度场景
- [x] 输入 Schema：`{"expression": "string 可选", "description": "string 可选"}`
- [x] 输出 Schema：`{"expression": "string", "description": "string", "fields": "object"}`
- [x] 实现要点：
  - 输入 expression：拆分 5/6 段，逐段翻译（分/时/日/月/周），生成中文描述
  - 输入 description：用 LLM 生成 cron（此分支调用 chat）
  - fields 返回 `{minute, hour, day, month, weekday}` 各段原始值
- [x] 验收：输入 `0 9 * * 1-5`，返回"每周一至周五 09:00 执行"

### 任务 33：`markdown_table` — Markdown 表格美化（纯本地）
- [x] 目标：任意 JSON 数组 → Markdown 表格，作为所有工具输出的美化收尾
- [x] 输入 Schema：`{"rows": "array", "max_cols": "number 可选，默认 10"}`
- [x] 输出 Schema：`{"markdown": "string", "rows": "number", "columns": "array"}`
- [x] 实现要点：取首行键为表头；单元格内 `|` 转义为 `\|`、换行转 `<br>`；超 max_cols 截断并标注
- [x] 验收：输入 `[{"a":1,"b":2}]`，返回合法 Markdown 表格字符串

> **阶段八检查点**：工具总数 56；4 个纯本地工具（29/30/32/33 的表达式分支）无需 LLM 即可测试。

---

## 阶段九：开发辅助（任务 34-38）

### 任务 34：`code_review` — 代码审查 ⭐ 推荐优先
- [x] 目标：审查代码片段的 bug、风格、性能、安全问题
- [x] 输入 Schema：`{"code": "string", "language": "string 可选，默认 python", "focus": "string 可选 bug|style|performance|security"}`
- [x] 输出 Schema：`{"issues": "array", "score": "number", "summary": "string"}`
- [x] 实现要点：issues 元素 `{"severity":"high|medium|low","line":0,"problem":"","suggestion":""}`；`json_mode=True`，`temperature=0.1`；可接 `result_critic` 双重评审
- [x] 验收：输入含明显 bug 的代码，issues 中定位到问题行

### 任务 35：`explain_code` — 代码解释
- [x] 目标：逐段解释代码在做什么（面向代码，区别于 `feynman_explain` 面向概念）
- [x] 输入 Schema：`{"code": "string", "audience": "string 可选，默认 开发者"}`
- [x] 输出 Schema：`{"overview": "string", "sections": "array", "notes": "string"}`
- [x] 实现要点：sections 元素 `{"code":"片段","explanation":"解释"}`；`json_mode=True`
- [x] 验收：输入一个函数，返回概览 + 分段解释

### 任务 36：`sql_generator` — 自然语言转 SQL
- [x] 目标：自然语言 + 表结构 → SQL 查询语句（与 `excel_plan` 平行，面向数据库）
- [x] 输入 Schema：`{"question": "string", "schema": "string 表结构 DDL 或描述", "dialect": "string 可选 sqlite|mysql|postgresql"}`
- [x] 输出 Schema：`{"sql": "string", "explanation": "string", "assumptions": "array"}`
- [x] 实现要点：Prompt 强调"只输出 SELECT、不编造列名、不确定处写入 assumptions"；`json_mode=True`
- [x] 验收：给表结构和"统计各城市销售额"，返回合理 SELECT 语句

### 任务 37：`generate_test_cases` — 测试用例生成
- [x] 目标：根据需求描述生成测试用例（正常/边界/异常）
- [x] 输入 Schema：`{"requirement": "string", "count": "number 可选，默认 8"}`
- [x] 输出 Schema：`{"cases": "array", "count": "number"}`
- [x] 实现要点：cases 元素 `{"type":"normal|boundary|exception","input":"","expected":"","steps":[]}`；`json_mode=True`
- [x] 验收：输入"用户登录功能"，返回覆盖三类用例的列表

### 任务 38：`commit_message` — Commit Message 生成
- [x] 目标：根据 git diff/变更描述生成规范 commit message（Conventional Commits）
- [x] 输入 Schema：`{"diff": "string", "style": "string 可选 conventional|中文"}`
- [x] 输出 Schema：`{"subject": "string", "body": "string", "type": "string", "scope": "string"}`
- [x] 实现要点：Prompt 要求 subject ≤ 50 字、type 取 feat/fix/docs/refactor/test/chore；`json_mode=True`，`temperature=0.2`
- [x] 验收：输入一段 diff，返回 `feat(tools): ...` 格式的 subject

> **阶段九检查点**：工具总数 61；5 个开发辅助工具注册成功。

---

## 阶段十：决策与分析（任务 39-42）

### 任务 39：`pros_cons` — 利弊分析
- [x] 目标：结构化利弊分析 + 决策建议
- [x] 输入 Schema：`{"topic": "string", "context": "string 可选"}`
- [x] 输出 Schema：`{"pros": "array", "cons": "array", "recommendation": "string", "confidence": "number"}`
- [x] 实现要点：pros/cons 元素 `{"point":"","weight":"high|medium|low"}`；`json_mode=True`
- [x] 验收：输入"是否迁移到新框架"，返回双方论据和建议

### 任务 40：`swot_analysis` — SWOT 分析
- [x] 目标：优势/劣势/机会/威胁四象限分析
- [x] 输入 Schema：`{"subject": "string", "context": "string 可选"}`
- [x] 输出 Schema：`{"strengths": "array", "weaknesses": "array", "opportunities": "array", "threats": "array", "strategy": "string"}`
- [x] 实现要点：每象限 3-5 条；strategy 给出基于四象限的行动建议；`json_mode=True`
- [x] 验收：输入某产品，返回四象限内容与策略

### 任务 41：`priority_matrix` — 优先级矩阵 ⭐ 推荐优先
- [x] 目标：艾森豪威尔矩阵，按紧急/重要把任务分四象限
- [x] 输入 Schema：`{"tasks": "array 任务列表", "input_from": "string 可选，默认从 tasks/todos 读取"}`
- [x] 输出 Schema：`{"do_first": "array", "schedule": "array", "delegate": "array", "eliminate": "array"}`
- [x] 实现要点：
  - 用 `_tool_text`/`inputs.get("tasks")` 读取上游 `task_extractor`/`meeting_notes` 的输出
  - 四象限：重要且紧急(do_first)、重要不紧急(schedule)、不重要紧急(delegate)、都不重要(eliminate)
  - 每项带 `{"task":"","reason":""}`；`json_mode=True`
- [x] 验收：输入 5 个任务，正确分配到四象限

### 任务 42：`risk_assessment` — 风险评估
- [x] 目标：识别风险、评级、给出缓解建议，可插入工作流做风控关卡
- [x] 输入 Schema：`{"subject": "string", "context": "string 可选"}`
- [x] 输出 Schema：`{"risks": "array", "overall_level": "string low|medium|high", "mitigation": "array"}`
- [x] 实现要点：risks 元素 `{"risk":"","probability":"","impact":"","level":""}`；`json_mode=True`
- [x] 验收：输入一个项目计划，返回风险列表和总体等级

> **阶段十检查点**：工具总数 65；`priority_matrix` 能读取上游 tasks。

---

## 阶段十一：内容增强（任务 43-46）

### 任务 43：`hashtag_generator` — 话题标签生成
- [x] 目标：为文案生成平台风格的话题标签（配合 `polish_copy`）
- [x] 输入 Schema：`{"text": "string", "platform": "string 可选 xhs|weibo|douyin", "count": "number 可选，默认 8"}`
- [x] 输出 Schema：`{"hashtags": "array", "count": "number"}`
- [x] 实现要点：按平台调整标签风格；返回带 # 前缀；`json_mode=True`
- [x] 验收：输入美妆文案 platform=xhs，返回 8 个小红书风格标签

### 任务 44：`readability_check` — 可读性评分
- [x] 目标：可读性评分 + 拆解长句建议
- [x] 输入 Schema：`{"text": "string"}`
- [x] 输出 Schema：`{"score": "number", "level": "string", "long_sentences": "array", "suggestions": "array"}`
- [x] 实现要点：结合纯本地统计（平均句长/段落长）+ LLM 评价；`json_mode=True`
- [x] 验收：输入一段长难句文本，score 合理并指出长句

### 任务 45：`seo_keywords` — SEO 关键词布局
- [x] 目标：为内容给出 SEO 关键词布局建议
- [x] 输入 Schema：`{"text": "string", "target_keyword": "string 可选"}`
- [x] 输出 Schema：`{"primary": "string", "secondary": "array", "placement": "array", "suggestions": "array"}`
- [x] 实现要点：placement 给出"标题/首段/小标题/结尾"等位置建议；`json_mode=True`
- [x] 验收：输入一篇博客，返回主关键词和布局建议

### 任务 46：`language_detect` — 语言检测（纯本地为主）
- [x] 目标：检测文本语言，可作自动路由前置节点
- [x] 输入 Schema：`{"text": "string"}`
- [x] 输出 Schema：`{"language": "string", "language_name": "string", "confidence": "number", "method": "string"}`
- [x] 实现要点：
  - 纯规则：中文字符占比 > 30% 判 zh；否则按常见词/字母特征判 en/ja/ko 等
  - method 标注 "rule"；置信度按字符占比估算
  - 不调用 `chat()`，快速稳定
- [x] 验收：输入中英混合文本，返回主要语言及合理置信度

> **阶段十一检查点**：工具总数 69；`language_detect` 无需 LLM 即可测试。

---

## 阶段十二：工作流组装（任务 47-50）

### 任务 47：`data_cleaning_pipeline` — 数据清洗流水线
- [x] 在 `default.yaml` 新增：
```yaml
  data_cleaning_pipeline:
    description: 表格抽取 → 校验 → 结构化 → 美化
    steps:
      - tool: extract_table
      - tool: json_validator
        with:
          input_from: tables
      - tool: text_to_json
        with:
          fields: ["类别", "数值", "备注"]
      - tool: markdown_table
```
- [x] 验收：输入含表格的文本，最终产出 Markdown 表格

### 任务 48：`smart_meeting_upgrade` — 智能纪要升级
- [x] 在 `default.yaml` 新增：
```yaml
  smart_meeting_upgrade:
    description: 会议 → 任务 → 优先级矩阵 → 邮件
    steps:
      - tool: meeting_notes
      - tool: task_extractor
      - tool: priority_matrix
        with:
          input_from: tasks
      - tool: email_compose
        with:
          tone: 正式
```
- [x] 验收：输入会议记录，返回按四象限分类的任务和通知邮件

### 任务 49：`code_review_assistant` — 代码评审助手
- [x] 在 `default.yaml` 新增：
```yaml
  code_review_assistant:
    description: 代码审查 → 解释 → 测试用例 → 双重评审
    steps:
      - tool: code_review
      - tool: explain_code
      - tool: generate_test_cases
      - tool: result_critic
        with:
          criteria: 审查完整性与建议可行性
```
- [x] 验收：输入一段代码，返回审查意见、解释、用例和评审分

### 任务 50：`rag_enhanced_search` — RAG 增强检索
- [x] 在 `default.yaml` 新增：
```yaml
  rag_enhanced_search:
    description: 关键词提取 → 查询改写 → 多路检索问答
    steps:
      - tool: keyword_extractor
      - tool: rag_rewrite_query
      - tool: rag_answer_v2
        with:
          top_k: 8
```
- [x] 前置：知识库已有文档
- [x] 验收：输入口语化问题，返回带来源的高质量答案

> **阶段十二检查点**：`/workflows` 接口能列出 20 个工作流；4 个新工作流逐个执行无报错。

---

## 阶段十三：验证与收尾（任务 51-53）

### 任务 51：功能验证
- [x] 运行 `python scripts/check_tools.py`，确认工具总数 ≥ 69
- [x] 运行 `curl http://localhost:8000/tools` 确认 API 返回新工具
- [x] 运行 `curl http://localhost:8000/workflows` 确认 API 返回 20 个工作流
- [x] 为新增 23 个工具在 `ui/streamlit_app.py` 的 `TOOL_SAMPLES` 补充预设用例
- [x] 校验预设用例覆盖全部工具（`tools - keys` 与 `keys - tools` 均为空）

### 任务 52：端到端验证
- [x] 数据清洗流水线：输入含表格文本 → 得到 Markdown 表格
- [x] 智能纪要升级：输入会议记录 → 得到四象限任务 + 邮件
- [x] 代码评审助手：输入代码 → 得到审查 + 解释 + 用例 + 评分
- [x] RAG 增强检索：先入库文档 → 输入问题 → 得到带来源答案

### 任务 53：文档与日志更新
- [x] 更新 `架构设计与开发说明.md` 工具清单（→ 69 个）与工作流清单（→ 20 个）
- [x] 更新 `README.md` 验证场景
- [x] 在 `EXECUTION_LOG.md` 追加批次二的设计、编码、测试、签收记录
- [x] 在 `TASKS.md` 勾选批次二全部任务

---

## 附录 D：批次二工具总览（新增 23 个）

| 阶段 | 工具名                   | 一句话功能              | 类型  |
|----|-----------------------|--------------------|-----|
| 七  | `text_statistics` ⭐   | 文本统计（纯本地）          | 本地  |
| 七  | `keyword_extractor`   | 关键词提取              | LLM |
| 七  | `extract_table`       | 表格抽取为 JSON         | LLM |
| 七  | `text_to_json`        | 按自定义字段转 JSON       | LLM |
| 七  | `dedupe_lines`        | 文本行去重（纯本地）         | 本地  |
| 八  | `json_validator` ⭐    | JSON 校验格式化         | 本地  |
| 八  | `yaml_validator`      | YAML 校验转 JSON      | 本地  |
| 八  | `regex_generator`     | 正则生成器              | LLM |
| 八  | `cron_explainer`      | Cron 表达式互转         | 混合  |
| 八  | `markdown_table`      | JSON 转 Markdown 表格 | 本地  |
| 九  | `code_review` ⭐       | 代码审查               | LLM |
| 九  | `explain_code`        | 代码解释               | LLM |
| 九  | `sql_generator`       | 自然语言转 SQL          | LLM |
| 九  | `generate_test_cases` | 测试用例生成             | LLM |
| 九  | `commit_message`      | Commit Message 生成  | LLM |
| 十  | `pros_cons`           | 利弊分析               | LLM |
| 十  | `swot_analysis`       | SWOT 分析            | LLM |
| 十  | `priority_matrix` ⭐   | 优先级四象限             | LLM |
| 十  | `risk_assessment`     | 风险评估               | LLM |
| 十一 | `hashtag_generator`   | 话题标签生成             | LLM |
| 十一 | `readability_check`   | 可读性评分              | 混合  |
| 十一 | `seo_keywords`        | SEO 关键词布局          | LLM |
| 十一 | `language_detect`     | 语言检测               | 本地  |

## 附录 E：批次二工作流总览（新增 4 个）

| 工作流名                     | 串联工具                                                             |
|--------------------------|------------------------------------------------------------------|
| `data_cleaning_pipeline` | extract_table → json_validator → text_to_json → markdown_table   |
| `smart_meeting_upgrade`  | meeting_notes → task_extractor → priority_matrix → email_compose |
| `code_review_assistant`  | code_review → explain_code → generate_test_cases → result_critic |
| `rag_enhanced_search`    | keyword_extractor → rag_rewrite_query → rag_answer_v2            |

## 附录 F：批次二推荐执行顺序（时间线）

```
Day 7:  任务 24-28  （文本数据处理，先做 text_statistics）
Day 8:  任务 29-33  （格式校验，重点 json_validator）
Day 9:  任务 34-38  （开发辅助，重点 code_review）
Day 10: 任务 39-42  （决策分析，重点 priority_matrix）
Day 11: 任务 43-46  （内容增强）
Day 12: 任务 47-50  （工作流组装 + 联调）
Day 13: 任务 51-53  （验证 + 文档收尾）
```

> 批次二合计：23 个工具（其中 7 个纯本地/混合，零或低 LLM 成本）+ 4 个工作流。
> 完成后工具总数 69 个，工作流总数 20 个。
