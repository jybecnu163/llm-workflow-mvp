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

| 阶段 | 工具名 | 一句话功能 |
|------|--------|-----------|
| 一 | `polish_copy` | 文案润色（风格可选） |
| 一 | `generate_hooks` | 爆款标题生成 |
| 一 | `rewrite_style` | 风格迁移 |
| 一 | `expand_article` | 内容扩写 |
| 二 | `meeting_notes` ⭐ | 会议纪要结构化 |
| 二 | `task_extractor` | 待办提取 |
| 二 | `email_compose` | 邮件撰写 |
| 二 | `slide_outline` | PPT大纲生成 |
| 三 | `feynman_explain` | 费曼讲解器 |
| 三 | `mindmap_outline` | 思维导图大纲 |
| 三 | `generate_quiz` ⭐ | 智能出题 |
| 三 | `flashcards` | 记忆卡片 |
| 四 | `prompt_doctor` | Prompt 优化 |
| 四 | `tool_matchmaker` | 工具推荐 |
| 四 | `workflow_advisor` | 工作流诊断 |
| 四 | `result_critic` | 结果评审 |

## 附录 B：工作流总览（本次新增 4 个）

| 工作流名 | 串联工具 |
|----------|----------|
| `content_factory` | generate_hooks → expand_article → rewrite_style → polish_copy |
| `study_buddy` | rag_search → feynman_explain → generate_quiz → flashcards |
| `meeting_secretary` | meeting_notes → task_extractor → write_db → email_compose |
| `support_qa` | classify_email → sentiment_aspect → result_critic → alert_ops |

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
