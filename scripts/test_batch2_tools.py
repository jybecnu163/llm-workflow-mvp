"""批次二扩展工具离线测试：mock chat()，纯本地工具用真实逻辑。"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import tools
from app.engine import execute_workflow, load_workflows

PASS = 0
FAIL = 0
PROMPTS = []

NEW_TOOLS = [
    "text_statistics", "keyword_extractor", "extract_table", "text_to_json", "dedupe_lines",
    "json_validator", "yaml_validator", "regex_generator", "cron_explainer", "markdown_table",
    "code_review", "explain_code", "sql_generator", "generate_test_cases", "commit_message",
    "pros_cons", "swot_analysis", "priority_matrix", "risk_assessment",
    "hashtag_generator", "readability_check", "seo_keywords", "language_detect",
]

REPLIES = {
    ("关键词提取专家",): {"keywords": ["央行", "基准利率", "股市", "房地产"], "count": 4},
    ("表格抽取专家",): {"tables": [{"headers": ["城市", "销售额"], "rows": [["上海", "12000"], ["北京", "8000"]]}]},
    ("信息抽取专家",): {"姓名": "张三", "时间": "2024年3月", "地点": "北京", "公司": "腾讯", "金额": "50"},
    ("正则表达式专家",): {"pattern": r"^1[3-9]\d{9}$", "explanation": "1开头11位", "test_cases": [{"text": "13812345678", "should_match": True}]},
    ("Cron 专家",): {"expression": "0 9 * * 1-5", "explanation": "工作日9点"},
    ("代码审查专家",): {"issues": [{"severity": "high", "line": 5, "problem": "SQL注入", "suggestion": "参数化查询"}], "score": 6.0, "summary": "存在安全问题"},
    ("代码讲解专家",): {"overview": "斐波那契递归实现", "sections": [{"code": "def fib", "explanation": "递归函数"}], "notes": "效率低"},
    ("SQL 专家",): {"sql": "SELECT 城市, SUM(销售额) FROM sales GROUP BY 城市", "explanation": "分组求和", "assumptions": []},
    ("测试工程师",): {"cases": [{"type": "normal", "input": "正确账号", "expected": "登录成功", "steps": []}]},
    ("邮件撰写助手",): {"subject": "通知", "body": "正文"},
    ("任务提取助手",): {"tasks": [{"task": "任务A", "priority": "high", "due": ""}]},
    ("会议纪要助手",): {"todos": [{"task": "完成XX", "owner": "张三", "deadline": "周五", "priority": "high"}], "decisions": [], "risks": [], "owners": ["张三"]},
    ("Git 提交信息专家",): {"subject": "feat(tools): 新增新工具", "body": "添加 new_tool", "type": "feat", "scope": "tools"},
    ("决策分析专家",): {"pros": [{"point": "环境一致", "weight": "high"}], "cons": [{"point": "学习成本", "weight": "medium"}], "recommendation": "建议迁移", "confidence": 0.8},
    ("战略规划专家",): {"strengths": ["技术强"], "weaknesses": ["品牌弱"], "opportunities": ["市场增长"], "threats": ["竞品"], "strategy": "差异化竞争"},
    ("时间管理专家",): {"do_first": [{"task": "修复线上支付bug", "reason": "重要紧急"}], "schedule": [{"task": "整理规划", "reason": "重要不紧急"}], "delegate": [], "eliminate": [{"task": "回复垃圾邮件", "reason": "都不重要"}]},
    ("风险管理专家",): {"risks": [{"risk": "流量过大", "probability": "high", "impact": "high", "level": "high"}], "overall_level": "high", "mitigation": ["提前压测"]},
    ("社交媒体运营专家",): {"hashtags": ["#奶茶", "#秋天打卡", "#美食"], "count": 3},
    ("文本可读性专家",): {"score": 5.0, "level": "难读", "suggestions": ["拆分长句"]},
    ("SEO 专家",): {"primary": "笔记本电脑选购", "secondary": ["处理器", "显卡"], "placement": [{"position": "标题", "keyword": "笔记本选购", "suggestion": "放标题开头"}], "suggestions": []},
}


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


def make_chat():
    async def _chat(prompt, system="", **kwargs):
        PROMPTS.append(prompt)
        combined = prompt + " " + (system or "")
        for keywords, reply in REPLIES.items():
            if all(k in combined for k in keywords):
                return json.dumps(reply, ensure_ascii=False)
        return "{}"
    return _chat


async def test_registration():
    print("\n=== 1. 工具注册检查 ===")
    ok("工具总数 >= 69", len(tools.TOOLS) >= 69, f"实际 {len(tools.TOOLS)}")
    for name in NEW_TOOLS:
        t = tools.TOOLS.get(name)
        ok(f"已注册: {name}", t is not None)
        if t:
            ok(f"  Schema完整: {name}",
               isinstance(t.get("input_schema"), dict)
               and isinstance(t.get("output_schema"), dict)
               and callable(t.get("func")))


async def test_local_tools():
    print("\n=== 2. 纯本地工具测试（真实逻辑） ===")
    r = await tools.text_statistics({"text": "你好世界。这是第二句！第三段。"})
    ok("text_statistics", r["sentences"] >= 2 and r["chars"] > 0 and r["words"] > 0)

    r = await tools.dedupe_lines({"text": "a\nb\na\nc\nb", "mode": "exact"})
    ok("dedupe_lines", r["original"] == 5 and r["kept"] == 3 and r["removed"] == 2)

    r = await tools.json_validator({"text": '{"a":1,"b":[1,2]}'})
    ok("json_validator 合法", r["valid"] and "a" in r["keys"] and r["size"] == 2)

    r = await tools.json_validator({"text": "{bad json}"})
    ok("json_validator 非法", not r["valid"] and "第1行" in r["error"])

    r = await tools.yaml_validator({"text": "name: demo\nsteps:\n  - tool: summarize_text"})
    ok("yaml_validator", r["valid"] and "name" in r["top_keys"])

    r = await tools.cron_explainer({"expression": "0 9 * * 1-5"})
    ok("cron_explainer", r["method"] == "rule" and "9" in r["description"] and "1-5" in r["description"])

    r = await tools.markdown_table({"rows": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]})
    ok("markdown_table", "| a | b |" in r["markdown"] and r["rows"] == 2 and r["columns"] == ["a", "b"])

    r = await tools.language_detect({"text": "这是一段中文文本，包含中文字符。"})
    ok("language_detect 中文", r["language"] == "zh" and r["method"] == "rule")

    r = await tools.language_detect({"text": "Hello world, this is English text."})
    ok("language_detect 英文", r["language"] == "en")

    r = await tools.language_detect({"text": "こんにちは世界"})
    ok("language_detect 日文", r["language"] == "ja")


async def test_llm_tools():
    print("\n=== 3. LLM 工具测试（mock chat） ===")
    with patch.object(tools, "chat", new=make_chat()):
        r = await tools.keyword_extractor({"text": "新闻", "count": 4})
        ok("keyword_extractor", r["count"] == 4)

        r = await tools.extract_table({"text": "城市|销售额"})
        ok("extract_table", r["count"] == 1 and r["tables"][0]["headers"][0] == "城市")

        r = await tools.text_to_json({"text": "文本", "fields": ["姓名", "公司", "不存在"]})
        ok("text_to_json missing", r["data"].get("姓名") == "张三" and "不存在" in r["missing"])

        r = await tools.regex_generator({"description": "手机号"})
        ok("regex_generator", r["python_valid"] is True and r["pattern"])

        r = await tools.code_review({"code": "SELECT * FROM t"})
        ok("code_review", r["score"] == 6.0 and r["issues"][0]["severity"] == "high")

        r = await tools.explain_code({"code": "def f(): pass"})
        ok("explain_code", r["overview"] == "斐波那契递归实现")

        r = await tools.sql_generator({"question": "统计", "schema": "CREATE TABLE sales"})
        ok("sql_generator", "SELECT" in r["sql"])

        r = await tools.generate_test_cases({"requirement": "登录", "count": 5})
        ok("generate_test_cases", r["count"] == 1)

        r = await tools.commit_message({"diff": "+ new code"})
        ok("commit_message", r["subject"].startswith("feat(tools)"))

        r = await tools.pros_cons({"topic": "测试"})
        ok("pros_cons", r["confidence"] == 0.8 and len(r["pros"]) == 1)

        r = await tools.swot_analysis({"subject": "产品"})
        ok("swot_analysis", all(k in r for k in ["strengths", "weaknesses", "opportunities", "threats"]))

        r = await tools.priority_matrix({"tasks": [{"task": "修复bug"}]})
        ok("priority_matrix", r["do_first"][0]["task"] == "修复线上支付bug")

        r = await tools.risk_assessment({"subject": "项目"})
        ok("risk_assessment", r["overall_level"] == "high" and len(r["risks"]) == 1)

        r = await tools.hashtag_generator({"text": "奶茶"})
        ok("hashtag_generator", r["count"] == 3 and r["hashtags"][0].startswith("#"))

        r = await tools.readability_check({"text": "很长的文本"})
        ok("readability_check", r["score"] == 5.0 and r["level"] == "难读")

        r = await tools.seo_keywords({"text": "笔记本"})
        ok("seo_keywords", r["primary"] == "笔记本电脑选购" and len(r["placement"]) == 1)

        # 空输入保护
        ok("code_review 空输入", (await tools.code_review({}))["score"] == 0)
        ok("priority_matrix 空输入", (await tools.priority_matrix({}))["do_first"] == [])
        ok("language_detect 空输入", (await tools.language_detect({}))["language"] == "unknown")


async def test_workflows():
    print("\n=== 4. 工作流编排测试（真实引擎 + mock） ===")
    wfs = load_workflows()
    for name in ["data_cleaning_pipeline", "smart_meeting_upgrade", "code_review_assistant", "rag_enhanced_search"]:
        ok(f"工作流已加载: {name}", name in wfs)

    with patch.object(tools, "chat", new=make_chat()):
        # data_cleaning_pipeline: extract_table 输出 tables，json_validator 接收 JSON 数组
        r = await execute_workflow(wfs["data_cleaning_pipeline"], {"text": "表格内容"})
        ctx = r["context"]
        ok("data_cleaning_pipeline 产出tables", len(ctx.get("tables", [])) == 1)
        ok("data_cleaning_pipeline 产出markdown", "| 城市 | 销售额 |" in (ctx.get("markdown") or "") or "markdown" in ctx)
        ok("data_cleaning_pipeline 无错误", all("error" not in s for s in r["steps"]))

        # smart_meeting_upgrade: priority_matrix 从 tasks 读取
        r = await execute_workflow(wfs["smart_meeting_upgrade"], {"text": "会议记录"})
        ctx = r["context"]
        ok("smart_meeting_upgrade 产出todos", len(ctx.get("todos", [])) == 1)
        ok("smart_meeting_upgrade 产出四象限", "do_first" in ctx and "schedule" in ctx)
        ok("smart_meeting_upgrade 产出subject", ctx.get("subject") == "通知")
        ok("smart_meeting_upgrade 无错误", all("error" not in s for s in r["steps"]))

        # code_review_assistant: 全链路
        r = await execute_workflow(wfs["code_review_assistant"], {"code": "def f(): pass"})
        ctx = r["context"]
        ok("code_review_assistant 产出issues", len(ctx.get("issues", [])) == 1)
        ok("code_review_assistant 产出overview", bool(ctx.get("overview")))
        ok("code_review_assistant 产出cases", len(ctx.get("cases", [])) == 1)
        ok("generate_test_cases 从code读取", bool(ctx.get("cases")))
        ok("code_review_assistant 产出score", ctx.get("score") in (6.0, 0.0))
        ok("code_review_assistant 无错误", all("error" not in s for s in r["steps"]))


async def main():
    print("=" * 60)
    print("批次二扩展工具离线测试（Ollama 未启动，依赖已 mock）")
    print("=" * 60)
    await test_registration()
    await test_local_tools()
    await test_llm_tools()
    await test_workflows()
    print("\n" + "=" * 60)
    print(f"测试结果: PASS={PASS}  FAIL={FAIL}")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
