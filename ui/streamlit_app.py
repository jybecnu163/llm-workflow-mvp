import json
import re

import requests
import streamlit as st

API = "http://localhost:8000"

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
}

st.set_page_config(page_title="LLM Workflow MVP", layout="wide")
st.title("🧠 本地 LLM 工作流 MVP")
st.caption("FastAPI + Ollama(llama3.1:8b) + YAML 工作流 + Streamlit")

# 健康检查
try:
    h = requests.get(f"{API}/health", timeout=3).json()
    st.success(f"API 状态: {h['status']}")
except Exception as e:
    st.error(f"无法连接后端: {e}")
    st.stop()

tab_tools, tab_wf, tab_wf_edit, tab_route, tab_rag = st.tabs(
    ["🔧 工具库", "🔀 工作流测试", "✏️ 工具库更新", "🚦 自动路由", "📚 文档问答"]
)

# ---------- 工具库 ----------
with tab_tools:
    tools = requests.get(f"{API}/tools").json()
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
            st.rerun()
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

# ---------- 测试工作流 ----------
with tab_wf:
    wfs = requests.get(f"{API}/workflows").json()
    wf_name = st.selectbox("选择工作流", list(wfs.keys()))
    st.json(wfs[wf_name])

    text = st.text_area("输入文本 (会作为 data['text'] 传入)", key="wf_text")
    extra = st.text_input(
        "附加 data 字段（JSON，可选）",
        key="wf_extra",
        placeholder='例如 {"path": "sales.xlsx", "question": "上海销售额前5"}',
    )

    if st.button("▶ 执行工作流", key="run_wf"):
        data = {"text": text}
        if extra.strip():
            try:
                data.update(json.loads(extra))
            except Exception as e:
                st.error(f"附加字段不是合法 JSON: {e}")
                st.stop()

        with st.spinner("执行工作流中..."):
            r = requests.post(
                f"{API}/run",
                json={"data": data, "workflow": wf_name},
                timeout=300,
            )
        st.json(r.json())

# ---------- 修改工作流 ----------
with tab_wf_edit:
    wfs_resp = requests.get(f"{API}/workflows")
    wfs = wfs_resp.json() if wfs_resp.status_code == 200 else {}
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
                st.success(f"已删除 {selected}")
                st.session_state.pop(f"wf_yaml_{selected}", None)
                st.rerun()
            else:
                st.error(r.json().get("detail", r.text))

        st.markdown("---")
        st.markdown("**可用工具**")
        try:
            tools = requests.get(f"{API}/tools").json()
            for t in tools:
                st.caption(f"`{t['name']}` — {t['description']}")
        except Exception:
            st.caption("(无法获取工具列表)")

    # ---------- 右侧：YAML 编辑器 + 执行 ----------
    with right:
        if not selected:
            st.stop()

        st.markdown(f"### ✏️ 编辑 `{selected}`")

        raw_resp = requests.get(f"{API}/workflows/{selected}/raw")
        if raw_resp.status_code != 200:
            st.error(f"加载失败: {raw_resp.text}")
            st.stop()
        current_yaml = raw_resp.json()["yaml"]

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
                    st.success("已保存")
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
