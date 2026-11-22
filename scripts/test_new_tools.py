"""TASKS.md 扩展工具离线测试：mock chat()/rag.search()，不依赖 Ollama。"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import rag, tools
from app.engine import execute_workflow, load_workflows

PASS = 0
FAIL = 0
PROMPTS = []

NEW_TOOLS = [
    "polish_copy", "generate_hooks", "rewrite_style", "expand_article",
    "meeting_notes", "task_extractor", "email_compose", "slide_outline",
    "feynman_explain", "mindmap_outline", "generate_quiz", "flashcards",
    "prompt_doctor", "tool_matchmaker", "workflow_advisor", "result_critic",
]

ALL_REPLIES = {
    ("文案润色专家",): {"polished": "润色结果", "tips": ["建议1"]},
    ("标题创作专家",): {"hooks": ["标题A", "标题B", "标题C"]},
    ("文字风格大师",): {"rewritten": "改写结果"},
    ("内容扩写专家",): {"expanded": "扩写结果"},
    ("会议纪要助手",): {"todos": [{"task": "完成XX", "owner": "张三", "deadline": "周五", "priority": "high"}], "decisions": [], "risks": [], "owners": ["张三"]},
    ("任务提取助手",): {"tasks": [{"task": "任务1", "priority": "high", "due": ""}]},
    ("邮件撰写助手",): {"subject": "会议通知", "body": "各位好..."},
    ("演示文稿设计专家",): {"slides": [{"title": "页1", "bullets": ["a", "b"]}]},
    ("费曼讲解大师",): {"explanation": "通俗解释", "analogy": "像水管", "key_points": ["点1"]},
    ("结构化专家",): {"outline": "- 主题\n  - 分支"},
    ("出题老师",): {"questions": [{"q": "题1", "options": ["A"], "answer": "A", "explanation": "解析"}]},
    ("记忆卡片专家",): {"cards": [{"front": "Q", "back": "A", "tags": ["t"]}]},
    ("提示工程专家",): {"diagnosis": "不够清晰", "optimized": "优化后", "suggestions": ["加格式"]},
    ("工具编排顾问",): {"tools": ["excel_describe", "not_exist_tool"], "reason": "分析数据", "suggested_workflow": "excel_nl_ops"},
    ("工作流架构师",): {"issues": ["顺序可优化"], "suggestions": ["调整条件"]},
    ("质量评审专家",): {"score": 4.0, "strengths": ["准确"], "weaknesses": ["简短"], "suggestions": ["补充"]},
    ("邮件分类助手",): {"category": "spam", "confidence": 0.9, "reason": "广告"},
    ("评价分析助手",): {"sentiment": "negative", "aspects": [], "summary": "体验很差"},
}


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


def make_chat(reply_map=None):
    reply_map = reply_map or ALL_REPLIES

    async def _chat(prompt, system="", **kwargs):
        PROMPTS.append(prompt)
        combined = prompt + " " + (system or "")
        for keywords, reply in reply_map.items():
            if all(k in combined for k in keywords):
                if isinstance(reply, str) and reply.strip().startswith("{"):
                    return reply
                return json.dumps(reply, ensure_ascii=False)
        return "{}"
    return _chat


async def fake_search(question, **kwargs):
    return [{"text": "临床试验材料", "source": "test.md", "page": 1, "chunk_index": 0, "score": 0.9}]


async def test_registration():
    print("\n=== 1. 工具注册检查 ===")
    ok("工具总数 >= 46", len(tools.TOOLS) >= 46, f"实际 {len(tools.TOOLS)}")
    for name in NEW_TOOLS:
        t = tools.TOOLS.get(name)
        ok(f"已注册: {name}", t is not None)
        if t:
            ok(f"  Schema完整: {name}",
               isinstance(t.get("input_schema"), dict)
               and isinstance(t.get("output_schema"), dict)
               and callable(t.get("func")))


async def test_helper():
    print("\n=== 2. _tool_text 输入解析 ===")
    h = tools._tool_text
    ok("input_from 优先", h({"text": "原始", "hooks": ["标题1", "标题2"], "input_from": "hooks"}) == "标题1")
    ok("chunks 拼接", "A" in h({"chunks": [{"text": "A"}, {"text": "B"}]}, "chunks") and "B" in h({"chunks": [{"text": "A"}, {"text": "B"}]}, "chunks"))
    ok("dict 解包", h({"data": {"summary": "摘要"}}, "data") == "摘要")
    ok("回退链", h({"summary": "摘要"}, "text", "summary") == "摘要")
    ok("空输入返回空", h({}) == "")
    ok("长度截断4000", len(h({"text": "x" * 5000}, "text")) == 4000)


async def test_tools():
    print("\n=== 3. 16 个工具功能测试（mock chat） ===")
    with patch.object(tools, "chat", new=make_chat()):
        r = await tools.polish_copy({"text": "原文"})
        ok("polish_copy", r["polished"] == "润色结果" and r["style"] == "小红书风")

        r = await tools.generate_hooks({"text": "文章", "count": 3})
        ok("generate_hooks", r["count"] == 3)

        r = await tools.rewrite_style({"text": "原文", "style": "鲁迅风"})
        ok("rewrite_style", r["rewritten"] == "改写结果")

        r = await tools.expand_article({"text": "要点"})
        ok("expand_article", r["expanded"] == "扩写结果")

        r = await tools.meeting_notes({"text": "会议记录"})
        ok("meeting_notes", r["todos"][0]["owner"] == "张三")

        r = await tools.task_extractor({"text": "邮件"})
        ok("task_extractor", r["count"] == 1)

        r = await tools.email_compose({"todos": [{"task": "任务A", "owner": "张三", "deadline": "周五"}]})
        ok("email_compose 从todos拼接", r["subject"] == "会议通知" and "任务A" in PROMPTS[-1])

        r = await tools.slide_outline({"text": "内容", "pages": 5})
        ok("slide_outline", r["total_pages"] == 1)

        r = await tools.feynman_explain({"text": "区块链", "audience": "10岁小孩", "input_from": "chunks", "chunks": [{"text": "材料"}]})
        ok("feynman_explain 概念未被劫持", r["analogy"] == "像水管" and "区块链" in PROMPTS[-1])

        r = await tools.mindmap_outline({"text": "长文"})
        ok("mindmap_outline", r["outline"].startswith("- 主题"))

        r = await tools.generate_quiz({"text": "材料", "count": 1})
        ok("generate_quiz", r["count"] == 1)

        r = await tools.flashcards({"text": "知识", "count": 1})
        ok("flashcards", r["count"] == 1)

        r = await tools.prompt_doctor({"prompt": "总结文本"})
        ok("prompt_doctor", r["optimized"] == "优化后")

        r = await tools.tool_matchmaker({"requirement": "分析销售数据"})
        ok("tool_matchmaker 过滤非法工具名", r["tools"] == ["excel_describe"])

        r = await tools.workflow_advisor({"name": "email_support"})
        ok("workflow_advisor 读取YAML", "summarize_text" in r["current"] and r["issues"])

        r = await tools.result_critic({"content": "一段回复"})
        ok("result_critic", r["score"] == 4.0 and r["strengths"] == ["准确"])

        ok("polish_copy 空输入", (await tools.polish_copy({}))["polished"] == "")
        ok("generate_quiz 空输入", (await tools.generate_quiz({}))["count"] == 0)
        ok("result_critic 空输入", (await tools.result_critic({}))["score"] == 0)


async def test_workflows():
    print("\n=== 4. 工作流编排测试（真实引擎 + mock） ===")
    wfs = load_workflows()
    for name in ["content_factory", "study_buddy", "meeting_secretary", "support_qa"]:
        ok(f"工作流已加载: {name}", name in wfs)

    with patch.object(tools, "chat", new=make_chat()), patch.object(rag, "search", new=fake_search):
        r = await execute_workflow(wfs["content_factory"], {"text": "产品卖点"})
        ctx = r["context"]
        ok("content_factory 全链路产物",
           len(ctx.get("hooks", [])) == 3
           and ctx.get("expanded") == "扩写结果"
           and ctx.get("rewritten") == "改写结果"
           and ctx.get("polished") == "润色结果")
        ok("content_factory 无错误", all("error" not in s for s in r["steps"]))

        r = await execute_workflow(wfs["meeting_secretary"], {"text": "会议记录"})
        ctx = r["context"]
        ok("meeting_secretary 全链路产物",
           len(ctx.get("todos", [])) == 1 and ctx.get("subject") == "会议通知")
        ok("meeting_secretary 无错误", all("error" not in s for s in r["steps"]))

        r = await execute_workflow(wfs["support_qa"], {"text": "垃圾邮件"})
        ctx = r["context"]
        ok("support_qa 产出score", ctx.get("score") == 4.0)
        alert_step = [s for s in r["steps"] if s["tool"] == "alert_ops"][0]
        ok("support_qa 低分触发告警", not alert_step.get("skipped") and ctx.get("alerted") is True)

        r = await execute_workflow(wfs["study_buddy"], {"text": "什么是临床试验"})
        ctx = r["context"]
        ok("study_buddy 全链路产物",
           ctx.get("explanation") == "通俗解释"
           and ctx.get("count") in (1, 10)
           and "cards" in ctx)
        ok("study_buddy 无错误", all("error" not in s for s in r["steps"]))

        # 条件表达式边界验证
        from app.engine import _eval_condition
        ok("条件表达式 score<6 为假", _eval_condition("score < 6", {"score": 8.0}) is False)
        ok("条件表达式 score<6 为真", _eval_condition("score < 6", {"score": 4.0}) is True)


async def main():
    print("=" * 60)
    print("TASKS.md 扩展工具离线测试（Ollama 未启动，依赖已 mock）")
    print("=" * 60)
    await test_registration()
    await test_helper()
    await test_tools()
    await test_workflows()
    print("\n" + "=" * 60)
    print(f"测试结果: PASS={PASS}  FAIL={FAIL}")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
