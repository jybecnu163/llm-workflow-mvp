"""自然语言规划器离线测试：mock LLM 验证生成 / 校验 / 转换 / 执行全链路。"""
import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# 离线环境可能未安装 RAG / Web 框架依赖。规划器测试不依赖真实向量库与 HTTP 服务，
# 这里注入最小替身仅用于让模块可导入，不改变被测逻辑。
def _ensure_module(name: str, **attrs):
    try:
        __import__(name)
    except ImportError:
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[name] = mod


class _FakeFastAPI:
    def __init__(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        return lambda fn: fn

    post = put = delete = get


class _FakeHTTPException(Exception):
    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


_ensure_module("chromadb", PersistentClient=object)
_ensure_module("pypdf", PdfReader=object)
_ensure_module("fastapi", FastAPI=_FakeFastAPI, HTTPException=_FakeHTTPException)

from app import planner, tools
from app.engine import execute_workflow
from app.planner import generate_plan, plan_to_workflow, validate_plan
from app.schemas import ExecutionPlan, PlanStep

PASS = 0
FAIL = 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


LLM_PLAN = json.dumps(
    {
        "intent": "润色并加标签",
        "steps": [
            {"tool": "polish_copy", "with": {"style": "小红书风"}, "reason": "先润色"},
            {"tool": "hashtag_generator", "with": {"platform": "xhs"}, "reason": "再加标签"},
        ],
    },
    ensure_ascii=False,
)

LLM_HALLUCINATION = json.dumps(
    {"intent": "幻觉测试", "steps": [{"tool": "fake_tool", "with": {}, "reason": "不存在"}]},
    ensure_ascii=False,
)


async def fake_planner_chat(prompt, system="", **kwargs):
    return LLM_PLAN


async def fake_hallucination_chat(prompt, system="", **kwargs):
    return LLM_HALLUCINATION


async def fake_tool_chat(prompt, system="", **kwargs):
    combined = prompt + " " + (system or "")
    if "文案润色专家" in combined:
        return json.dumps({"polished": "润色结果", "tips": []}, ensure_ascii=False)
    if "话题标签助手" in combined:
        return json.dumps({"hashtags": ["#测试"], "count": 1}, ensure_ascii=False)
    return "{}"


async def test_schemas_and_validation():
    print("\n=== 1. 数据结构与校验器 ===")
    step = PlanStep(tool="polish_copy", with_={"style": "小红书风"}, reason="润色")
    ok("with 别名解析", step.with_ == {"style": "小红书风"}, str(step.with_))

    plan = ExecutionPlan(intent="测试", steps=[step])
    ok("ExecutionPlan 构造", len(plan.steps) == 1 and plan.intent == "测试")
    ok("合法计划无告警", validate_plan(plan) == [], str(validate_plan(plan)))

    w = validate_plan(ExecutionPlan(steps=[PlanStep(tool="no_such_tool")]))
    ok("幻觉工具名告警", any("不存在" in x for x in w), str(w))

    w = validate_plan(ExecutionPlan(steps=[PlanStep(tool="polish_copy", with_={"bogus": 1})]))
    ok("非法参数告警", any("不接受参数" in x for x in w), str(w))

    w = validate_plan(
        ExecutionPlan(steps=[PlanStep(tool="polish_copy", condition="score <")])
    )
    ok("condition 语法错误告警", any("语法错误" in x for x in w), str(w))

    w = validate_plan(
        ExecutionPlan(
            steps=[PlanStep(tool="polish_copy", condition="__import__('os').system('ls')")]
        )
    )
    ok("condition 危险节点告警", any("condition" in x for x in w), str(w))

    ok("空步骤告警", bool(validate_plan(ExecutionPlan())), str(validate_plan(ExecutionPlan())))


async def test_generate_plan():
    print("\n=== 2. generate_plan 计划生成 ===")
    with patch.object(planner, "chat", new=fake_planner_chat):
        plan = await generate_plan("润色并加标签")
    ok("intent 解析", plan.intent == "润色并加标签", plan.intent)
    ok("步骤顺序正确", [s.tool for s in plan.steps] == ["polish_copy", "hashtag_generator"],
       str([s.tool for s in plan.steps]))
    ok("with 参数解析", plan.steps[0].with_.get("style") == "小红书风")
    ok("合法计划无告警", not plan.warnings, str(plan.warnings))

    with patch.object(planner, "chat", new=fake_hallucination_chat):
        bad = await generate_plan("幻觉测试")
    ok("generate_plan 填充幻觉告警", any("不存在" in x for x in bad.warnings),
       str(bad.warnings))


async def test_plan_to_workflow():
    print("\n=== 3. plan_to_workflow 转换 ===")
    plan = ExecutionPlan(
        intent="测试计划",
        steps=[
            PlanStep(tool="polish_copy", with_={"style": "小红书风"}, condition="score < 6"),
        ],
    )
    wf = plan_to_workflow(plan)
    ok("workflow 名称", wf["name"] == "generated_plan", str(wf))
    ok("workflow 描述", wf["description"] == "测试计划")
    ok("step 工具名", wf["steps"][0]["tool"] == "polish_copy")
    ok("step with", wf["steps"][0]["with"] == {"style": "小红书风"})
    ok("step condition", wf["steps"][0]["condition"] == "score < 6")

    p2 = ExecutionPlan(steps=[PlanStep(tool="markdown_table", input_from="tables")])
    wf2 = plan_to_workflow(p2)
    ok("input_from 合并进 with", wf2["steps"][0]["with"].get("input_from") == "tables",
       str(wf2))


async def test_end_to_end():
    print("\n=== 4. plan -> workflow -> execute 端到端 ===")
    wf = plan_to_workflow(
        ExecutionPlan(
            intent="润色并加标签",
            steps=[
                PlanStep(tool="polish_copy", with_={"style": "小红书风"}),
                PlanStep(tool="hashtag_generator", with_={"platform": "xhs"}),
            ],
        )
    )
    with patch.object(tools, "chat", new=fake_tool_chat):
        result = await execute_workflow(wf, {"text": "原文"})
    errors = [s for s in result["steps"] if s.get("error")]
    ok("执行无错误", not errors, str(errors))
    ok("上下文含润色结果", result["context"].get("polished") == "润色结果")
    ok("上下文含标签", bool(result["context"].get("hashtags")))
    ok("步骤数正确", len(result["steps"]) == 2)


async def test_api():
    print("\n=== 5. API 端点（直接调用端点函数） ===")
    from app.main import api_plan, api_plan_execute, api_plan_run
    from app.schemas import PlanExecuteRequest, PlanRequest

    with patch.object(planner, "chat", new=fake_planner_chat), \
         patch.object(tools, "chat", new=fake_tool_chat):
        resp = await api_plan(PlanRequest(instruction="润色并加标签"))
        ok("api_plan 返回计划", resp["plan"]["intent"] == "润色并加标签", str(resp)[:200])
        ok("api_plan 返回 workflow", len(resp["workflow"]["steps"]) == 2)

        resp = await api_plan_run(
            PlanRequest(instruction="润色并加标签", data={"text": "原文"})
        )
        ok("api_plan_run 返回 result", "result" in resp, str(resp)[:200])
        ok("api_plan_run 执行无错误",
           not [s for s in resp["result"]["steps"] if s.get("error")])

        wf = plan_to_workflow(
            ExecutionPlan(steps=[PlanStep(tool="polish_copy", with_={"style": "小红书风"})])
        )
        resp = await api_plan_execute(
            PlanExecuteRequest(workflow=wf, data={"text": "原文"})
        )
        steps = resp["result"]["steps"]
        ok("api_plan_execute 执行无错误", not [s for s in steps if s.get("error")], str(steps))


async def main():
    print("=" * 60)
    print("自然语言规划器离线测试（mock LLM）")
    print("=" * 60)
    await test_schemas_and_validation()
    await test_generate_plan()
    await test_plan_to_workflow()
    await test_end_to_end()
    await test_api()
    print("\n" + "=" * 60)
    print(f"测试结果: PASS={PASS}  FAIL={FAIL}")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
