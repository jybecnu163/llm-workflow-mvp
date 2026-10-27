import json
import re

import requests
import streamlit as st

API = "http://localhost:8000"

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

    inputs = {}
    for key, typ in tool["input_schema"].items():
        inputs[key] = st.text_area(f"{key} ({typ})", key=f"tool_{tool_name}_{key}")

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
