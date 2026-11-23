"""全工作流离线测试：用 UI 默认用例 + mock LLM 执行全部工作流。"""
import ast
import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# 离线环境缺 RAG 依赖时注入最小替身，仅用于模块导入（不触碰被测逻辑）
for _name, _attrs in (("chromadb", {"PersistentClient": object}), ("pypdf", {"PdfReader": object})):
    try:
        __import__(_name)
    except ImportError:
        _mod = types.ModuleType(_name)
        for _k, _v in _attrs.items():
            setattr(_mod, _k, _v)
        sys.modules[_name] = _mod

from app import rag, tools
from app.engine import execute_workflow, load_workflows

PASS = 0
FAIL = 0

NEW_WORKFLOWS = [
    "news_intelligence", "content_seo_optimizer", "knowledge_mindmap",
    "decision_advisor", "dev_delivery", "proofread_professional",
    "text_cleanup", "tag_aggregation", "prompt_lab", "deck_builder",
    "sql_analyst", "novel_kb_builder", "regex_assistant",
    "format_validator", "cron_helper",
]

REPLIES = {
    ("语言检测",): {"language": "zh", "language_name": "中文", "confidence": 0.9, "method": "rule"},
    ("新闻分类助手",): {"category": "finance", "confidence": 0.9},
    ("文案润色专家",): {"polished": "润色结果", "tips": []},
    ("标题创作专家",): {"hooks": ["标题A", "标题B"]},
    ("内容扩写专家",): {"expanded": "扩写结果"},
    ("文字风格大师",): {"rewritten": "改写结果"},
    ("关键词提取专家",): {"keywords": ["关键词1", "关键词2", "关键词3"]},
    ("翻译",): "Translation result",
    ("话题标签助手",): {"hashtags": ["#话题1", "#话题2"], "count": 2},
    ("文本可读性专家",): {"score": 7.0, "level": "适中", "suggestions": []},
    ("SEO 专家",): {"primary": "笔记本选购", "secondary": ["配置"], "placement": [{"position": "标题", "keyword": "笔记本选购"}], "suggestions": []},
    ("检索查询改写助手",): {"rewritten": ["改写查询"], "keywords": []},
    ("文档问答助手",): {"answer": "答案", "sources": [], "chunks_used": 1},
    ("思维导图大纲",): {"outline": "- 主题\n  - 分支"},
    ("费曼讲解大师",): {"explanation": "通俗讲解", "analogy": "比喻", "key_points": ["点1"]},
    ("记忆卡片专家",): {"cards": [{"front": "Q", "back": "A", "tags": []}]},
    ("决策分析专家",): {"pros": [{"point": "优点", "weight": "high"}], "cons": [], "recommendation": "建议迁移", "confidence": 0.8},
    ("战略规划专家",): {"strengths": ["优势"], "weaknesses": ["劣势"], "opportunities": ["机会"], "threats": ["威胁"], "strategy": "策略"},
    ("风险管理专家",): {"risks": [{"risk": "风险", "level": "medium"}], "overall_level": "medium", "mitigation": ["缓解"]},
    ("邮件撰写助手",): {"subject": "通知", "body": "正文"},
    ("代码审查专家",): {"issues": [{"severity": "medium", "line": 1, "problem": "问题", "suggestion": "建议"}], "score": 7.0, "summary": "代码可优化"},
    ("代码讲解专家",): {"overview": "概述", "sections": [], "notes": ""},
    ("测试工程师",): {"cases": [{"type": "normal", "input": "输入", "expected": "输出", "steps": []}]},
    ("Git 提交信息专家",): {"subject": "feat: 新增功能", "body": "", "type": "feat", "scope": ""},
    ("质量评审助手",): {"score": 8.0, "strengths": ["完整"], "weaknesses": [], "suggestions": []},
    ("纠错",): {"corrected": "我们一起去公园玩，看到很多漂亮的花，心情很好。", "changes": [], "confidence": 0.9, "no_change": False},
    ("旅游标签专家",): {"theme": [{"tag": "亲子", "confidence": 0.9}], "pace": [], "audience": [], "season": [], "experience": [], "budget": [], "marketing": [], "risk": [], "extra_tags": []},
    ("提示工程专家",): {"diagnosis": "问题", "optimized": "优化后的prompt", "suggestions": []},
    ("工具推荐助手",): {"tools": ["summarize_text"], "reason": "推荐理由", "suggested_workflow": "default"},
    ("工作流诊断助手",): {"issues": ["问题"], "suggestions": ["建议"]},
    ("Excel 操作计划生成器",): {"operations": [{"type": "head", "n": 3}], "answer_hint": "取前3行"},
    ("数据分析助手",): "上海销售额最高，共12000。",
    ("演示文稿设计专家",): {"slides": [{"title": "页1", "bullets": ["要点1"]}]},
    ("SQL 专家",): {"sql": "SELECT 城市, SUM(销售额) FROM sales GROUP BY 城市", "explanation": "分组汇总", "assumptions": []},
    ("正则表达式专家",): {"pattern": r"^1[3-9]\d{9}$", "explanation": "手机号", "test_cases": [{"text": "13812345678", "should_match": True}]},
}


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


def load_workflow_samples():
    src = Path("ui/streamlit_app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "WORKFLOW_SAMPLES" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    return {}


def make_chat():
    async def _chat(prompt, system="", **kwargs):
        combined = prompt + " " + (system or "")
        for keywords, reply in REPLIES.items():
            if all(k in combined for k in keywords):
                if isinstance(reply, str):
                    return reply
                return json.dumps(reply, ensure_ascii=False)
        return "{}"
    return _chat


async def fake_search(question, **kwargs):
    return [{"text": "临床试验是一种医学研究", "source": "test.md", "page": 1, "chunk_index": 0, "score": 0.9}]


async def fake_ingest_chapters(dir_name="sanguo"):
    return {"dir": dir_name, "files": 120, "chunks_added": 1500, "collection_size": 1500}


async def fake_ingest_document(path_name="test.md"):
    return {"file": path_name, "pages": 1, "chunks_added": 3, "collection_size": 10}


async def test_coverage():
    print("\n=== 1. 覆盖率检查 ===")
    wfs = load_workflows()
    samples = load_workflow_samples()
    used = {s.get("tool") for w in wfs.values() for s in w["steps"]}
    ok(f"工作流总数 >= 35", len(wfs) >= 35, f"实际 {len(wfs)}")
    ok("全部工具被工作流覆盖", len(used) == len(tools.TOOLS),
       f"未覆盖: {sorted(set(tools.TOOLS) - used)}")
    ok("默认用例覆盖全部工作流", set(samples) == set(wfs),
       f"缺失: {sorted(set(wfs) - set(samples))}")
    ok("每个用例含 text 字段", all("text" in v for v in samples.values()))
    ok("extra 字段均为合法 JSON",
       all(not v.get("extra") or json.loads(v["extra"]) is not None for v in samples.values()))
    for name in NEW_WORKFLOWS:
        ok(f"新工作流已注册: {name}", name in wfs)


async def test_execute_all():
    print("\n=== 2. 全部 35 个工作流执行测试（默认用例 + mock） ===")
    wfs = load_workflows()
    samples = load_workflow_samples()
    with patch.object(tools, "chat", new=make_chat()), \
         patch.object(rag, "search", new=fake_search), \
         patch.object(rag, "ingest_document", new=fake_ingest_document), \
         patch.object(rag, "ingest_chapter_files", new=fake_ingest_chapters):
        for name, wf in wfs.items():
            sample = samples.get(name, {})
            data = {"text": sample.get("text", "测试输入")}
            if sample.get("extra"):
                try:
                    data.update(json.loads(sample["extra"]))
                except Exception:
                    pass
            try:
                r = await execute_workflow(wf, data)
                errors = [s for s in r["steps"] if s.get("error")]
                ok(f"执行: {name}", bool(r.get("steps")) and not errors,
                   f"错误: {[e.get('error') for e in errors]}")
            except Exception as e:
                ok(f"执行: {name}", False, f"异常: {e}")


async def main():
    print("=" * 60)
    print("全工作流离线测试（默认用例 + mock LLM）")
    print("=" * 60)
    await test_coverage()
    await test_execute_all()
    print("\n" + "=" * 60)
    print(f"测试结果: PASS={PASS}  FAIL={FAIL}")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
