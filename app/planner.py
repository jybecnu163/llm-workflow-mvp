"""自然语言命令规划器：NL -> Plan -> Validate -> Workflow。

设计原则：
- LLM 只负责把用户指令翻译成结构化计划；
- 规则校验器拦截幻觉工具名、非法参数、非法 condition；
- 生成的计划转成 workflow dict 后复用现有 execute_workflow 执行。
"""
import ast
import json

from app.ollama_client import chat
from app.schemas import ExecutionPlan
from app.tools import get_tool, list_tools

SYSTEM = "你是命令规划助手，只输出 JSON。"

# with 中允许出现的特殊键（引擎级参数，不属于任何具体工具的 input_schema）
SPECIAL_KEYS = {"input_from"}

# 禁止出现在 condition 中的 AST 节点，避免执行任意代码
_FORBIDDEN_NODES = (
    ast.Call,
    ast.Attribute,
    ast.Subscript,
    ast.Lambda,
    ast.IfExp,
    ast.Assign,
    ast.NamedExpr,
)

_FEWSHOT = """示例 1
指令: 把这段文字润色成小红书风，再加话题标签
输出: {"intent":"润色文案并生成话题标签","steps":[{"tool":"polish_copy","with":{"style":"小红书风"},"reason":"先润色表达"},{"tool":"hashtag_generator","with":{"platform":"xhs"},"reason":"再生成平台标签"}]}

示例 2
指令: 从这段文本里抽取表格，再转成 Markdown
输出: {"intent":"抽取表格并美化输出","steps":[{"tool":"extract_table","with":{},"reason":"抽取表格结构"},{"tool":"markdown_table","with":{"input_from":"tables"},"reason":"取上游 tables 渲染表格"}]}

示例 3
指令: 整理会议记录，提取任务排优先级，最后写封通知邮件
输出: {"intent":"会议纪要升级并通知","steps":[{"tool":"meeting_notes","with":{},"reason":"结构化会议纪要"},{"tool":"task_extractor","with":{},"reason":"提取待办任务"},{"tool":"priority_matrix","with":{"input_from":"tasks"},"reason":"按四象限排优先级"},{"tool":"email_compose","with":{"tone":"正式"},"reason":"生成通知邮件"}]}"""


def _tool_catalog() -> str:
    """动态拼装当前已注册工具清单，注入到 prompt。"""
    lines = []
    for t in list_tools():
        schema = json.dumps(t["input_schema"], ensure_ascii=False)
        lines.append(
            f"- {t['name']}: {t['description']} | 输入字段: {schema}"
        )
    return "\n".join(lines)


def _parse_plan_json(raw: str) -> dict:
    """解析 LLM 输出，兼容包裹在 ```json 或散文本中的 JSON。"""
    try:
        data = json.loads(raw)
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
            except Exception:
                data = {}
        else:
            data = {}
    return data if isinstance(data, dict) else {}


def _check_condition(expr: str) -> str | None:
    """校验 condition 表达式：语法合法且不含危险节点。返回错误描述或 None。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return f"语法错误: {e.msg}"
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_NODES):
            return f"不允许的表达式节点: {type(node).__name__}"
    return None


def validate_plan(plan: ExecutionPlan) -> list[str]:
    """软校验计划，返回告警列表（不抛异常）。"""
    warnings: list[str] = []
    if not plan.steps:
        warnings.append("计划没有任何步骤")

    for i, step in enumerate(plan.steps, 1):
        tool = get_tool(step.tool)
        if tool is None:
            warnings.append(f"步骤 {i}: 工具 '{step.tool}' 不存在")
            continue

        allowed = set(tool["input_schema"].keys()) | SPECIAL_KEYS
        for key in (step.with_ or {}):
            if key not in allowed:
                warnings.append(
                    f"步骤 {i}: 工具 '{step.tool}' 不接受参数 '{key}'"
                )
        if step.condition:
            err = _check_condition(step.condition)
            if err:
                warnings.append(f"步骤 {i}: condition 表达式非法 - {err}")
    return warnings


async def generate_plan(instruction: str) -> ExecutionPlan:
    """自然语言指令 -> 结构化计划。"""
    prompt = f"""把用户的自然语言指令翻译成可依次执行的工具调用计划。

【可用工具】
{_tool_catalog()}

【输出格式】
只输出 JSON: {{"intent":"...","steps":[{{"tool":"...","with":{{...}},"input_from":"...","condition":"...","reason":"..."}}]}}

【示例】
{_FEWSHOT}

【规则】
1. 只能使用上面列出的工具名，禁止编造。
2. with 的键必须是该工具输入 Schema 中的字段；引擎级参数 input_from 除外。
3. 步骤按执行顺序排列，前一步的输出会合并进上下文供后续步骤使用。
4. 需要指定上游输出字段时，填写 input_from（输出键名，如 tables、tasks）。
5. 需要条件执行时，condition 写简单 Python 表达式，例如 "score < 6"，禁止函数调用。
6. 用中文写 intent 和 reason；没有合适工具时给出空 steps。
7. 不要输出 Markdown 代码块，只输出纯 JSON。

【用户指令】
{instruction}"""

    raw = await chat(prompt, system=SYSTEM, json_mode=True, temperature=0.1)
    data = _parse_plan_json(raw)
    try:
        plan = ExecutionPlan(**data)
    except Exception:
        plan = ExecutionPlan(intent=instruction[:100], steps=[])

    plan.warnings = validate_plan(plan)
    return plan


def plan_to_workflow(plan: ExecutionPlan) -> dict:
    """ExecutionPlan -> 引擎可执行的 workflow dict。"""
    steps = []
    for step in plan.steps:
        item: dict = {"tool": step.tool}
        params = dict(step.with_ or {})
        if step.input_from:
            params["input_from"] = step.input_from
        if params:
            item["with"] = params
        if step.condition:
            item["condition"] = step.condition
        steps.append(item)

    return {
        "name": "generated_plan",
        "description": plan.intent or "自然语言生成的计划",
        "steps": steps,
    }
