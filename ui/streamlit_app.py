import json
import re

import requests
import streamlit as st

API = "http://localhost:8000"

# 复用 TCP 连接 + 缓存只读请求，避免每次 widget 交互都重复访问后端
_session = requests.Session()


@st.cache_data(ttl=30, show_spinner=False)
def api_get(path: str):
    """缓存 GET 请求：同一 path 在 30 秒内直接返回缓存，不再请求后端。"""
    resp = _session.get(f"{API}{path}", timeout=5)
    resp.raise_for_status()
    return resp.json()


# 各工具的预设测试用例：选择工具时自动填入，可直接运行或按需修改
TOOL_SAMPLES = {
    # ---------- 分类 ----------
    "classify_email": {
        "subject": "限时优惠！点击领取您的奖品",
        "body": "尊敬的用户，恭喜您获得一等奖！请点击链接填写个人信息领取奖金。",
    },
    "classify_news": {
        "text": "央行宣布下调基准利率25个基点，分析人士认为这将提振股市表现。",
    },
    "sentiment_aspect": {
        "text": "这款手机拍照效果很好，电池续航也不错，就是价格有点贵，客服态度一般。",
    },
    # ---------- 摘要 / 抽取 ----------
    "summarize_text": {
        "text": "OpenAI发布了新一代大模型GPT-5，在多项基准测试中超越前代产品。新模型在推理速度提升30%的同时，API调用成本降低了50%。业界认为这将加速AI应用的普及。",
    },
    "extract_entities": {
        "text": "张三于2024年3月在北京加入了腾讯公司，年薪50万元。",
    },
    "extract_ticket": {
        "text": "我的订单12345还没发货，已经等了一周了，请尽快处理！",
    },
    # ---------- 生成 ----------
    "draft_reply": {
        "text": "我的订单12345还没到，请尽快处理",
        "summary": "客户催促订单物流进度",
    },
    # ---------- IO / 副作用 ----------
    "write_db": {
        "text": "订单12345已处理完成",
    },
    "alert_ops": {
        "summary": "发现负面评价，需要人工介入",
    },
    # ---------- 翻译 ----------
    "translate_text": {
        "text": "人工智能正在改变世界。",
        "target_lang": "英文",
        "source_lang": "自动检测",
        "style": "formal",
    },
    "summarize_and_translate": {
        "text": "近日，某公司发布了一款新的人工智能产品，可大幅提升办公效率。",
        "target_lang": "英文",
    },
    # ---------- 旅游标签 ----------
    "extract_itinerary_fields": {
        "text": "日本大阪6日游，上海出发，4999元，入住四星酒店，往返春秋航空，适合3-10月出行。",
    },
    "generate_travel_tags": {
        "text": "亲子友好型海岛度假行程，包含潜水体验和亲子活动，适合夏季出行。",
    },
    "normalize_tags": {
        "theme": '[{"tag":"亲子","confidence":0.9,"evidence":"亲子友好"}]',
        "pace": '[{"tag":"轻松","confidence":0.8,"evidence":"度假"}]',
        "extra_tags": '["网红打卡"]',
    },
    "render_tag_summary": {
        "normalized": '{"theme":[{"tag":"亲子"}],"pace":[{"tag":"轻松"}]}',
    },
    "merge_tags": {
        "tag_chunks": '[{"theme":[{"tag":"亲子","confidence":0.8}]},{"theme":[{"tag":"亲子","confidence":0.9},{"tag":"美食","confidence":0.7}]}]',
    },
    # ---------- 文本纠错 ----------
    "correct_text": {
        "text": "我门一起去公圆玩，看到很多漂亮的花。",
        "strict": "false",
    },
    "verify_correction": {
        "text": "我门一起去公圆玩",
        "corrected": "我们一起去公园玩",
    },
    "correct_text_by_sentence": {
        "text": "我门一起去公圆玩。那里的花很漂亮！",
    },
    "protect_terms": {
        "text": "我在京东上买了东西",
        "corrected": "我在京东上买了东西",
    },
    # ---------- Excel ----------
    "excel_describe": {
        "path": "sales.xlsx",
    },
    "excel_plan": {
        "question": "按月份统计各城市的销售额",
        "columns": '["日期","城市","产品","销售额","数量"]',
        "schema": '[{"column":"日期","dtype":"object"},{"column":"城市","dtype":"object"},{"column":"销售额","dtype":"int64"}]',
        "preview": '[{"日期":"2025-01-03","城市":"上海","销售额":12000}]',
    },
    "excel_execute": {
        "path": "sales.xlsx",
        "operations": '[{"type":"groupby","by":"城市","agg":{"销售额":"sum"}}]',
    },
    "excel_answer": {
        "question": "哪个城市销售额最高？",
        "result_rows": "4",
        "result_preview": '[{"城市":"上海","销售额":58200},{"城市":"北京","销售额":24000}]',
        "operations": '[{"type":"groupby","by":"城市","agg":{"销售额":"sum"}}]',
        "errors": "[]",
        "warnings": "无",
    },
    # ---------- RAG ----------
    "rag_ingest": {
        "path": "project_budget.md",
    },
    "rag_search": {
        "question": "项目总预算是多少？",
        "top_k": "5",
        "source_filter": "",
    },
    "rag_answer": {
        "question": "项目总预算是多少？分几期拨付？",
        "top_k": "5",
    },
    "rag_ingest_chapter_dir": {
        "dir": "sanguo",
    },
    "rag_rewrite_query": {
        "question": "诸葛亮怎么死的",
    },
    "rag_answer_v2": {
        "question": "诸葛亮北伐失败的原因是什么？",
        "top_k": "5",
    },
    # ---------- 内容创作 ----------
    "polish_copy": {
        "text": "我们的新手机拍照效果很好，电池续航也不错。",
        "style": "小红书风",
    },
    "generate_hooks": {
        "text": "这款新手机拍照清晰、续航持久，价格也很亲民。",
        "count": "5",
        "tone": "干货",
    },
    "rewrite_style": {
        "text": "今天下雨了，路面很湿。",
        "style": "鲁迅风",
    },
    "expand_article": {
        "text": "新能源汽车市场持续增长",
        "target_length": "300",
        "format": "paragraph",
    },
    # ---------- 办公效率 ----------
    "meeting_notes": {
        "text": "会议讨论了Q3预算。张三负责本周五前完成招聘计划，李四负责跟进供应商合同。风险：预算可能超支10%。决定：优先保障核心项目。",
    },
    "task_extractor": {
        "text": "请在本周五前提交季度报告，下周一安排团队会议，尽快修复线上bug。",
    },
    "email_compose": {
        "points": "通知团队下周一开会，讨论Q3预算，请提前准备各部门数据",
        "tone": "正式",
        "recipient": "项目组全体成员",
    },
    "slide_outline": {
        "text": "2025年公司业务总结：营收增长30%，新客户增长50%，产品迭代3个大版本。",
        "pages": "5",
    },
    # ---------- 学习知识 ----------
    "feynman_explain": {
        "concept": "区块链",
        "audience": "10岁小孩",
        "text": "区块链是一种分布式账本技术，数据按时间顺序打包成区块并串成链。",
    },
    "mindmap_outline": {
        "text": "人工智能主要包括机器学习、深度学习、自然语言处理、计算机视觉等方向。",
        "max_depth": "3",
    },
    "generate_quiz": {
        "text": "《三国演义》中，桃园三结义的三人是刘备、关羽、张飞。诸葛亮字孔明，号卧龙。",
        "count": "5",
        "difficulty": "medium",
    },
    "flashcards": {
        "text": "Python是一种高级编程语言，由Guido van Rossum创建于1991年。",
        "count": "5",
    },
    # ---------- 系统增强 ----------
    "prompt_doctor": {
        "prompt": "帮我写点东西",
        "goal": "生成一篇产品推广文案",
    },
    "tool_matchmaker": {
        "requirement": "我想分析销售数据并生成报告",
    },
    "workflow_advisor": {
        "name": "email_support",
    },
    "result_critic": {
        "content": "您好，您的订单正在处理中，预计明天送达。",
        "criteria": "准确性、礼貌性、信息完整性",
    },
    # ===== 批次二：文本与数据处理 =====
    "text_statistics": {
        "text": "人工智能正在改变世界。机器学习是人工智能的核心分支，深度学习又是机器学习的重要方向。自然语言处理和计算机视觉是深度学习的两大应用场景。",
    },
    "keyword_extractor": {
        "text": "央行宣布下调基准利率25个基点，分析人士认为这将提振股市表现，房地产板块或率先受益。",
        "count": "8",
    },
    "extract_table": {
        "text": "| 城市 | 销售额 | 数量 |\n|------|--------|------|\n| 上海 | 12000 | 12 |\n| 北京 | 8000 | 8 |\n| 深圳 | 15000 | 15 |",
    },
    "text_to_json": {
        "text": "张三于2024年3月在北京加入腾讯公司，年薪50万元。",
        "fields": '["姓名","时间","地点","公司","金额"]',
        "schema_hint": "金额单位万元",
    },
    "dedupe_lines": {
        "text": "苹果\n香蕉\n苹果\n橘子\n香蕉\n葡萄",
        "mode": "exact",
        "case_sensitive": "true",
    },
    # ===== 批次二：格式转换与校验 =====
    "json_validator": {
        "text": '{"name":"测试","items":[1,2,3],"valid":true}',
        "indent": "2",
    },
    "yaml_validator": {
        "text": "name: demo\ndescription: 示例工作流\nsteps:\n  - tool: summarize_text\n  - tool: write_db\n    condition: \"summary != ''\"",
    },
    "regex_generator": {
        "description": "匹配中国大陆手机号（1开头，11位数字）",
        "sample_text": "联系方式：13812345678 或 13900000000",
    },
    "cron_explainer": {
        "expression": "0 9 * * 1-5",
        "description": "",
    },
    "markdown_table": {
        "rows": '[{"城市":"上海","销售额":12000},{"城市":"北京","销售额":8000}]',
        "max_cols": "10",
    },
    # ===== 批次二：开发辅助 =====
    "code_review": {
        "code": "def add(a, b):\n    result = a + b\n    return result\n\ndef get_user(id):\n    query = 'SELECT * FROM users WHERE id = ' + id\n    return query",
        "language": "python",
        "focus": "security",
    },
    "explain_code": {
        "code": "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)",
        "audience": "开发者",
    },
    "sql_generator": {
        "question": "统计各城市的销售额总和，按销售额降序排列",
        "schema": "CREATE TABLE sales (id INT, 城市 VARCHAR(50), 销售额 DECIMAL(10,2), 日期 DATE);",
        "dialect": "sqlite",
    },
    "generate_test_cases": {
        "requirement": "用户登录功能：输入用户名和密码，正确则登录成功，错误则提示失败",
        "count": "8",
    },
    "commit_message": {
        "diff": "+ @register(name='new_tool')\n+ async def new_tool(inputs):\n+     return {'ok': True}\n- old_function()",
        "style": "conventional",
    },
    # ===== 批次二：决策与分析 =====
    "pros_cons": {
        "topic": "是否将项目从虚拟环境迁移到 Docker 容器",
        "context": "团队 5 人，需要统一开发环境",
    },
    "swot_analysis": {
        "subject": "公司新推出的智能客服产品",
        "context": "面向中小企业市场，竞品已有两家头部厂商",
    },
    "priority_matrix": {
        "tasks": '[{"task":"修复线上支付bug"},{"task":"整理下季度规划"},{"task":"回复垃圾邮件"},{"task":"准备周一紧急会议材料"}]',
    },
    "risk_assessment": {
        "subject": "计划在双十一上线新推荐算法",
        "context": "流量预计增长 5 倍，团队缺乏大促经验",
    },
    # ===== 批次二：内容增强 =====
    "hashtag_generator": {
        "text": "秋天的第一杯奶茶，暖心又暖胃，快来打卡吧！",
        "platform": "xhs",
        "count": "8",
    },
    "readability_check": {
        "text": "人工智能技术是一种通过模拟人类智能行为来实现自动化处理的前沿技术领域，它在当今社会的各个行业和场景中都得到了越来越广泛的应用和深入的探索。",
    },
    "seo_keywords": {
        "text": "本文介绍了如何选择适合的笔记本电脑，包括处理器、内存、显卡等核心配置的选择建议。",
        "target_keyword": "笔记本电脑选购",
    },
    "language_detect": {
        "text": "Hello world! 这是一段中英混合的文本。",
    },
}

# 各工作流的默认测试用例：选择工作流时自动填入 text 与附加 data 字段
WORKFLOW_SAMPLES = {
    "default": {
        "text": "OpenAI发布了新一代大模型GPT-5，在多项基准测试中超越前代产品，API成本降低50%。",
        "extra": "",
    },
    "email_spam": {
        "text": "限时优惠！恭喜您获得一等奖，请点击链接填写个人信息领取奖金。",
        "extra": "",
    },
    "email_support": {
        "text": "我的订单12345还没到，已经等了一周了，请尽快处理！",
        "extra": "",
    },
    "review_negative": {
        "text": "这款产品质量太差了，物流也慢，客服态度还很不好，非常失望！",
        "extra": "",
    },
    "news_finance": {
        "text": "央行宣布下调基准利率25个基点，分析人士认为这将提振股市表现，科技板块或率先受益。",
        "extra": "",
    },
    "translate_only": {
        "text": "人工智能正在改变世界，大模型技术让生活更便捷。",
        "extra": '{"target_lang":"英文","style":"formal"}',
    },
    "translate_summary": {
        "text": "近日某公司发布新一代AI产品，可大幅提升办公效率。该产品采用最新大模型技术，支持多语言处理，已在多个行业落地应用。",
        "extra": '{"target_lang":"英文"}',
    },
    "travel_tagging": {
        "text": "日本大阪6日游，上海出发，4999元，入住四星酒店，往返春秋航空，适合亲子家庭夏季出行，含潜水体验。"
    },
    "text_correction": {
        "text": "我门一起去公圆玩，看到很多漂亮的花，心晴很好。",
        "extra": "",
    },
    "excel_nl_ops": {
        "text": "按月份统计各城市的销售额",
        "extra": '{"path":"sales.xlsx"}',
    },
    "doc_qa": {
        "text": "项目总预算是多少？分几期拨付？",
        "extra": "",
    },
    "doc_ingest_and_qa": {
        "text": "项目总预算是多少？",
        "extra": '{"path":"project_budget.md"}',
    },
    "content_factory": {
        "text": "新款降噪耳机：续航40小时、主动降噪、轻巧便携，售价599元。",
        "extra": "",
    },
    "study_buddy": {
        "text": "什么是临床试验？",
        "extra": "",
    },
    "meeting_secretary": {
        "text": "会议讨论Q3预算。张三负责本周五前完成招聘计划，李四负责跟进供应商合同。风险：预算可能超支10%。决定：优先保障核心项目。",
        "extra": "",
    },
    "support_qa": {
        "text": "你们的产品太差了，物流慢质量差，客服还不回复， urgently需要处理！",
        "extra": "",
    },
    "data_cleaning_pipeline": {
        "text": "| 城市 | 销售额 | 数量 |\n|------|--------|------|\n| 上海 | 12000 | 12 |\n| 北京 | 8000 | 8 |\n| 深圳 | 15000 | 15 |",
        "extra": "",
    },
    "smart_meeting_upgrade": {
        "text": "会议讨论Q3预算。张三本周五前完成招聘计划；李四跟进供应商合同；本月底前上线新功能。请尽快回复垃圾推销邮件。",
        "extra": "",
    },
    "code_review_assistant": {
        "text": "请审查以下代码并生成测试用例。",
        "extra": '{"code":"def get_user(id):\\n    query = \'SELECT * FROM users WHERE id = \' + id\\n    return query"}',
    },
    "rag_enhanced_search": {
        "text": "诸葛亮北伐失败的原因是什么？",
        "extra": "",
    },
    "news_intelligence": {
        "text": "The Fed announced a rate cut of 25 basis points. 央行同步下调基准利率，科技股上涨。",
        "extra": "",
    },
    "content_seo_optimizer": {
        "text": "本文介绍了如何选择适合的笔记本电脑。处理器、内存和显卡是三大核心配置。建议根据预算和使用场景综合考量，选择Intel或AMD处理器，内存至少16GB。",
        "extra": "",
    },
    "knowledge_mindmap": {
        "text": "什么是机器学习？",
        "extra": "",
    },
    "decision_advisor": {
        "text": "是否将项目从虚拟环境迁移到Docker容器？",
        "extra": "",
    },
    "dev_delivery": {
        "text": "请交付以下功能的开发成果。",
        "extra": '{"code":"def fib(n):\\n    if n <= 1:\\n        return n\\n    return fib(n-1) + fib(n-2)"}',
    },
    "proofread_professional": {
        "text": "我门一起去公圆玩，看到很多漂亮的花。京东的俺们服务很好，心晴不错。",
        "extra": "",
    },
    "text_cleanup": {
        "text": "人工智能改变世界\n机器学习是AI核心\n人工智能改变世界\n深度学习是重要方向\n机器学习是AI核心",
        "extra": "",
    },
    "tag_aggregation": {
        "text": "亲子友好型海岛度假行程，含潜水体验，适合夏季出行，轻奢预算，网红打卡。",
        "extra": "",
    },
    "prompt_lab": {
        "text": "帮我写点东西",
        "extra": "",
    },
    "deck_builder": {
        "text": "2025年公司业务总结：营收增长30%，新客户增长50%，产品迭代3个大版本。明年计划拓展海外市场并加大AI投入。",
        "extra": "",
    },
    "sql_analyst": {
        "text": "统计各城市的销售额总和，按销售额降序排列",
        "extra": '{"schema":"CREATE TABLE sales (id INT, 城市 VARCHAR(50), 销售额 DECIMAL(10,2), 日期 DATE);"}',
    },
    "novel_kb_builder": {
        "text": "诸葛亮北伐失败的原因是什么？",
        "extra": "",
    },
    "regex_assistant": {
        "text": "生成手机号正则并给出测试用例。",
        "extra": '{"description":"匹配中国大陆手机号（1开头，11位数字）","sample_text":"13812345678"}',
    },
    "format_validator": {
        "text": '{"name":"测试","items":[1,2,3],"valid":true}',
        "extra": "",
    },
    "cron_helper": {
        "text": "生成工作日早上9点执行的定时任务说明。",
        "extra": '{"expression":"0 9 * * 1-5"}',
    },
}

st.set_page_config(page_title="LLM Workflow MVP", layout="wide")
st.title("🧠 本地 LLM 工作流 MVP")
st.caption("FastAPI + Ollama(llama3.1:8b) + YAML 工作流 + Streamlit")

# 健康检查（走缓存，30 秒内不重复请求）
try:
    h = api_get("/health")
    st.success(f"API 状态: {h['status']}")
except Exception as e:
    st.error(f"无法连接后端: {e}")
    st.stop()


# ---------- 智能命令 Tab（fragment：预览计划 / 确认执行） ----------
@st.fragment
def render_plan_tab():
    st.markdown("用一句话下达一串命令，系统先生成可依次执行的计划，确认后再顺序执行。")

    examples = [
        (
            "把这段文字润色成小红书风，再加话题标签",
            "新款保温杯，500ml 大容量，24 小时保温，配色清新，适合通勤和户外使用。",
        ),
        (
            "从这段文本里抽取表格，再转成 Markdown",
            "季度销售数据：\n| 城市 | 销售额 | 状态 |\n|---|---|---|\n| 上海 | 12000 | 超额完成 |\n| 北京 | 9800 | 达标 |\n| 广州 | 7500 | 待提升 |",
        ),
        (
            "整理会议记录，提取任务排优先级，最后写封通知邮件",
            "会议讨论 Q3 预算。张三负责本周五前完成招聘计划，李四负责跟进供应商合同。"
            "风险：预算可能超支 10%。决定：优先保障核心项目。",
        ),
    ]
    st.caption("💡 示例指令（点击一键填入指令 + 对应输入文本）：")
    cols = st.columns(3)
    for i, (ex, sample_text) in enumerate(examples):
        with cols[i]:
            if st.button(
                ex[:10] + "…",
                key=f"plan_ex_{i}",
                help=f"指令：{ex}\n\n输入文本：{sample_text}",
            ):
                st.session_state["plan_instruction"] = ex
                st.session_state["plan_text"] = sample_text
                st.rerun(scope="fragment")

    instruction = st.text_area(
        "自然语言指令",
        key="plan_instruction",
        height=90,
        placeholder="例如：先润色这段文字，再加话题标签",
    )
    input_text = st.text_area(
        "输入文本（作为 data['text'] 传入）",
        key="plan_text",
        height=120,
    )

    if st.button("🧭 生成计划", key="btn_gen_plan"):
        if not instruction.strip():
            st.warning("请输入指令")
        else:
            with st.spinner("正在规划..."):
                r = requests.post(
                    f"{API}/plan",
                    json={"instruction": instruction},
                    timeout=180,
                )
            if r.status_code == 200:
                payload = r.json()
                st.session_state["plan_data"] = payload["plan"]
                st.session_state["plan_workflow"] = payload["workflow"]
            else:
                st.error(r.text)

    plan_data = st.session_state.get("plan_data")
    if plan_data:
        st.markdown("### 📋 计划预览")
        st.markdown(f"**意图：** {plan_data.get('intent', '')}")

        warnings = plan_data.get("warnings") or []
        if warnings:
            st.warning("计划存在以下告警，请确认后再执行：")
            for w in warnings:
                st.markdown(f"- ⚠️ {w}")

        for i, step in enumerate(plan_data.get("steps", []), 1):
            st.markdown(f"**{i}. `{step.get('tool')}`** — {step.get('reason', '')}")
            if step.get("with"):
                st.json(step["with"])
            if step.get("condition"):
                st.caption(f"条件: {step['condition']}")

        if not plan_data.get("steps"):
            st.warning("计划中没有可执行的步骤")

        if st.button("▶ 确认执行", key="btn_exec_plan"):
            with st.spinner("执行中..."):
                r = requests.post(
                    f"{API}/plan/execute",
                    json={
                        "workflow": st.session_state["plan_workflow"],
                        "data": {"text": input_text},
                    },
                    timeout=300,
                )
            if r.status_code == 200:
                result = r.json()["result"]
                st.markdown("### 🛠 执行结果")
                for i, s in enumerate(result.get("steps", []), 1):
                    if s.get("skipped"):
                        st.caption(f"{i}. `{s.get('tool')}` 已跳过（条件不满足）")
                    elif s.get("error"):
                        st.error(f"{i}. `{s.get('tool')}` 出错: {s['error']}")
                    else:
                        with st.expander(f"{i}. `{s.get('tool')}` 输出", expanded=(i == 1)):
                            st.json(s.get("output"))
            else:
                st.error(r.text)


# ---------- 工具库 Tab（fragment：切换工具只重跑本区域） ----------
@st.fragment
def render_tools_tab():
    tools = api_get("/tools")
    names = [t["name"] for t in tools]
    tool_name = st.selectbox("选择工具", names)
    tool = next(t for t in tools if t["name"] == tool_name)

    st.markdown(f"**说明：** {tool['description']}")
    with st.expander("输入 / 输出 Schema"):
        st.json({"input": tool["input_schema"], "output": tool["output_schema"]})

    # 预设用例：优先取字典中的示例值，未覆盖的字段留空
    sample = TOOL_SAMPLES.get(tool_name, {})
    if sample:
        st.caption("💡 已载入预设测试用例，可直接运行或按需修改")
        if st.button("🔄 恢复预设用例", key="reset_tool_sample"):
            for k in list(st.session_state.keys()):
                if k.startswith(f"tool_{tool_name}_"):
                    del st.session_state[k]
            st.rerun(scope="fragment")
    else:
        st.caption("ℹ️ 该工具暂无预设用例，请手动填写输入")

    # 渲染字段：以 input_schema 为主，补充样例中额外的键（如 normalize_tags 等空 schema 工具）
    fields = list(tool["input_schema"].keys())
    for k in sample:
        if k not in fields:
            fields.append(k)

    inputs = {}
    for key in fields:
        typ = tool["input_schema"].get(key, "string")
        inputs[key] = st.text_area(
            f"{key} ({typ})",
            value=str(sample.get(key, "")),
            key=f"tool_{tool_name}_{key}",
        )

    if st.button("▶ 运行工具", key="run_tool"):
        with st.spinner("调用 Ollama 中..."):
            r = requests.post(
                f"{API}/tools/{tool_name}/run",
                json={"inputs": inputs},
                timeout=180,
            )
        st.json(r.json())


# ---------- 工作流测试 Tab（fragment：切换工作流只重跑本区域） ----------
@st.fragment
def render_workflow_test_tab():
    wfs = api_get("/workflows")
    wf_name = st.selectbox("选择工作流", list(wfs.keys()))
    st.json(wfs[wf_name])

    sample = WORKFLOW_SAMPLES.get(wf_name, {})
    if sample:
        st.caption("💡 已载入该工作流的默认测试用例，可直接执行或按需修改")
        if st.button("🔄 恢复默认用例", key="reset_wf_sample"):
            for k in list(st.session_state.keys()):
                if k.startswith(f"wf_{wf_name}_"):
                    del st.session_state[k]
            st.rerun(scope="fragment")
    else:
        st.caption("ℹ️ 该工作流暂无默认用例，请手动填写输入")

    text = st.text_area(
        "输入文本 (会作为 data['text'] 传入)",
        value=sample.get("text", ""),
        key=f"wf_{wf_name}_text",
    )
    extra = st.text_input(
        "附加 data 字段（JSON，可选）",
        value=sample.get("extra", ""),
        key=f"wf_{wf_name}_extra",
        placeholder='例如 {"path": "sales.xlsx", "question": "上海销售额前5"}',
    )

    if st.button("▶ 执行工作流", key="run_wf"):
        data = {"text": text}
        if extra.strip():
            try:
                data.update(json.loads(extra))
            except Exception as e:
                st.error(f"附加字段不是合法 JSON: {e}")
                return

        with st.spinner("执行工作流中..."):
            r = requests.post(
                f"{API}/run",
                json={"data": data, "workflow": wf_name},
                timeout=300,
            )
        st.json(r.json())


tab_tools, tab_wf, tab_wf_edit, tab_route, tab_rag, tab_plan = st.tabs(
    ["🔧 工具库", "🔀 工作流测试", "✏️ 工具库更新", "🚦 自动路由", "📚 文档问答", "🗣️ 智能命令"]
)

with tab_tools:
    render_tools_tab()

with tab_wf:
    render_workflow_test_tab()

# ---------- 修改工作流 ----------
with tab_wf_edit:
    wfs = api_get("/workflows")
    names = sorted(wfs.keys())

    left, right = st.columns([1, 2])

    # ---------- 左侧：列表 / 新建 / 删除 ----------
    with left:
        st.markdown("### 📚 工作流")

        with st.expander("➕ 新建工作流", expanded=False):
            new_name = st.text_input("名称（字母/数字/下划线）", key="new_wf_name")
            new_desc = st.text_input("描述（可选）", key="new_wf_desc")
            if st.button("创建", key="btn_create_wf"):
                if not new_name:
                    st.warning("请输入名称")
                elif not re.match(r"^[A-Za-z0-9_-]+$", new_name):
                    st.error("名称只允许字母、数字、下划线和短横线")
                elif new_name in names:
                    st.error("已存在同名工作流")
                else:
                    template = (
                        f"name: {new_name}\n"
                        f"description: {new_desc or '新工作流'}\n"
                        f"steps:\n"
                        f"  - tool: summarize_text\n"
                    )
                    r = requests.put(
                        f"{API}/workflows/{new_name}",
                        json={"yaml": template},
                    )
                    if r.status_code == 200:
                        st.cache_data.clear()  # 写操作后失效缓存，保证列表即时更新
                        st.success(f"已创建 {new_name}")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", r.text))

        if not names:
            st.info("暂无工作流，请先新建。")
            selected = None
        else:
            selected = st.radio("选择工作流", names, key="wf_select")

        if selected and st.button("🗑 删除当前工作流", key="btn_del_wf"):
            r = requests.delete(f"{API}/workflows/{selected}")
            if r.status_code == 200:
                st.cache_data.clear()
                st.session_state.pop(f"wf_yaml_{selected}", None)
                st.success(f"已删除 {selected}")
                st.rerun()
            else:
                st.error(r.json().get("detail", r.text))

        st.markdown("---")
        st.markdown("**可用工具**")
        try:
            for t in api_get("/tools"):
                st.caption(f"`{t['name']}` — {t['description']}")
        except Exception:
            st.caption("(无法获取工具列表)")

    # ---------- 右侧：YAML 编辑器 + 执行 ----------
    with right:
        if not selected:
            st.info("请先在左侧选择或新建工作流。")
        else:
            st.markdown(f"### ✏️ 编辑 `{selected}`")

            try:
                current_yaml = api_get(f"/workflows/{selected}/raw")["yaml"]
            except Exception as e:
                st.error(f"加载失败: {e}")
                current_yaml = None

            if current_yaml is not None:
                state_key = f"wf_yaml_{selected}"
                edited = st.text_area(
                    "YAML 内容（可直接编辑）",
                    value=current_yaml,
                    height=420,
                    key=state_key,
                )

                c1, c2, c3 = st.columns([1, 1, 3])
                with c1:
                    if st.button("💾 保存", key="btn_save_wf"):
                        r = requests.put(
                            f"{API}/workflows/{selected}",
                            json={"yaml": edited},
                        )
                        if r.status_code == 200:
                            st.cache_data.clear()
                            st.success("已保存")
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", r.text))
                with c2:
                    if st.button("🔄 重置", key="btn_reset_wf"):
                        st.session_state.pop(state_key, None)
                        st.rerun()
                with c3:
                    st.caption("保存后立即生效；执行时按磁盘上的最新版本加载。")

        # st.markdown("---")
        # st.markdown("### ▶ 执行工作流")
        # run_text = st.text_area(
        #     "输入文本（会作为 data['text'] 传入；其它字段可在 YAML 里用 with 覆盖）",
        #     key=f"wf_run_text_{selected}",
        # )
        # extra = st.text_input(
        #     "附加 data 字段（JSON，可选，例如 {\"target_lang\":\"英文\"}）",
        #     key=f"wf_run_extra_{selected}",
        # )
        #
        # if st.button("执行", key="btn_run_wf"):
        #     data = {"text": run_text}
        #     if extra.strip():
        #         try:
        #             data.update(json.loads(extra))
        #         except Exception as e:
        #             st.error(f"附加字段不是合法 JSON: {e}")
        #             st.stop()
        #
        #     with st.spinner("执行中..."):
        #         r = requests.post(
        #             f"{API}/run",
        #             json={"data": data, "workflow": selected},
        #             timeout=300,
        #         )
        #     if r.status_code == 200:
        #         st.json(r.json())
        #     else:
        #         st.error(r.text)

# ---------- 自动路由 ----------
with tab_route:
    st.markdown("输入任意文本，后端会先分类再选择对应工作流执行。")
    text = st.text_area("输入文本", key="route_text")
    if st.button("🚀 自动路由并执行", key="run_route"):
        with st.spinner("分类 + 执行中..."):
            r = requests.post(
                f"{API}/run",
                json={"data": {"text": text}, "auto_route": True},
                timeout=300,
            )
        st.json(r.json())

# ---------- 文档 RAG 问答 ----------
with tab_rag:
    st.markdown("### 📤 上传文档入库")
    uploaded = st.file_uploader(
        "支持 PDF / TXT / MD，上传后点击“入库”",
        type=["pdf", "txt", "md", "markdown"],
        key="rag_uploader",
    )

    if uploaded and st.button("⬆️ 入库到知识库", key="btn_ingest"):
        import os

        save_path = f"./data/rag_docs/{uploaded.name}"
        os.makedirs("./data/rag_docs", exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())

        with st.spinner(f"正在切分并向量化 {uploaded.name} ..."):
            r = requests.post(
                f"{API}/tools/rag_ingest/run",
                json={"inputs": {"path": uploaded.name}},
                timeout=600,
            )
        if r.status_code == 200:
            st.success(f"已入库: {r.json()['output']}")
        else:
            st.error(r.text)

    st.markdown("---")
    st.markdown("### 💬 知识库问答")

    question = st.text_area(
        "输入问题",
        key="rag_question",
        placeholder="例如：文档里提到的项目预算是多少？",
    )
    top_k = st.slider("检索片段数 top_k", 1, 10, 5, key="rag_top_k")

    if st.button("🔍 提问", key="btn_rag_ask"):
        if not question.strip():
            st.warning("请输入问题")
        else:
            with st.spinner("检索 + 生成中..."):
                r = requests.post(
                    f"{API}/tools/rag_answer/run",
                    json={"inputs": {"question": question, "top_k": top_k}},
                    timeout=300,
                )
            if r.status_code == 200:
                out = r.json()["output"]
                st.markdown("**回答：**")
                st.write(out.get("answer", ""))
                st.markdown(f"**使用片段数：** {out.get('chunks_used', 0)}")
                srcs = out.get("sources") or []
                if srcs:
                    st.markdown("**来源：**")
                    for s in srcs:
                        st.caption(
                            f"- {s['source']} 第 {s['page']} 页（相似度 {s['score']}）"
                        )
            else:
                st.error(r.text)

# ---------- 智能命令 ----------
with tab_plan:
    render_plan_tab()
