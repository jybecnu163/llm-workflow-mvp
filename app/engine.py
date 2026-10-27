import re
from pathlib import Path
from typing import Any

import yaml

from app.tools import get_tool, TOOLS

WORKFLOW_DIR = Path(__file__).parent / "workflows"
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


# ---------------- 读取 ----------------

def load_workflows() -> dict:
    """加载所有工作流。兼容两种格式：
    1) 单工作流文件：name / description / steps
    2) 多工作流文件：workflows: { name: {...} }
    """
    workflows: dict[str, Any] = {}
    for f in sorted(WORKFLOW_DIR.glob("*.yaml")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
        except Exception:
            continue

        if isinstance(data.get("workflows"), dict):
            for name, wf in data["workflows"].items():
                workflows[name] = wf
        elif "name" in data and "steps" in data:
            workflows[data["name"]] = {
                "description": data.get("description", ""),
                "steps": data.get("steps", []),
            }
    return workflows


def load_workflow_raw(name: str) -> str:
    """返回工作流的原始 YAML 文本，用于页面编辑。"""
    _check_name(name)

    # 优先独立文件
    path = WORKFLOW_DIR / f"{name}.yaml"
    if path.exists():
        return path.read_text(encoding="utf-8")

    # 回退：从多工作流文件里抽出来
    for f in WORKFLOW_DIR.glob("*.yaml"):
        with open(f, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
        if isinstance(data.get("workflows"), dict) and name in data["workflows"]:
            wf = {"name": name, **data["workflows"][name]}
            return yaml.safe_dump(wf, allow_unicode=True, sort_keys=False)

    raise FileNotFoundError(name)


# ---------------- 写入 ----------------

def _check_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValueError("工作流名称只允许字母、数字、下划线和短横线")


def _validate_yaml(name: str, content: str) -> dict:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析失败: {e}")

    if not isinstance(data, dict):
        raise ValueError("YAML 根节点必须是字典")

    if "name" not in data:
        data["name"] = name
    if data["name"] != name:
        raise ValueError(f"YAML 中的 name ({data['name']}) 必须等于工作流名 ({name})")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps 必须是非空列表")

    valid_tools = set(TOOLS.keys())
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict):
            raise ValueError(f"第 {i} 步必须是字典")
        tool = s.get("tool")
        if not tool:
            raise ValueError(f"第 {i} 步缺少 tool 字段")
        if tool not in valid_tools:
            raise ValueError(
                f"第 {i} 步的工具 '{tool}' 不存在。可用工具: {sorted(valid_tools)}"
            )
    return data


def save_workflow_raw(name: str, content: str) -> None:
    """保存工作流：始终写入独立文件 {name}.yaml，并从多工作流文件中移除同名条目。"""
    _check_name(name)
    _validate_yaml(name, content)  # 会抛 ValueError

    # 从多工作流文件（如 default.yaml）中剔除同名工作流，避免重复
    for f in WORKFLOW_DIR.glob("*.yaml"):
        if f.name == f"{name}.yaml":
            continue
        try:
            with open(f, "r", encoding="utf-8") as fp:
                d = yaml.safe_load(fp) or {}
        except Exception:
            continue
        if isinstance(d.get("workflows"), dict) and name in d["workflows"]:
            del d["workflows"][name]
            with open(f, "w", encoding="utf-8") as fp:
                yaml.safe_dump(d, fp, allow_unicode=True, sort_keys=False)

    # 若内容没写 name 行，补一行，保留用户注释
    lines = content.splitlines()
    has_name = any(l.strip().startswith("name:") for l in lines[:5])
    if not has_name:
        content = f"name: {name}\n" + content

    path = WORKFLOW_DIR / f"{name}.yaml"
    path.write_text(content, encoding="utf-8")


def delete_workflow(name: str) -> bool:
    _check_name(name)
    path = WORKFLOW_DIR / f"{name}.yaml"
    if path.exists():
        path.unlink()
        return True

    for f in WORKFLOW_DIR.glob("*.yaml"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                d = yaml.safe_load(fp) or {}
        except Exception:
            continue
        if isinstance(d.get("workflows"), dict) and name in d["workflows"]:
            del d["workflows"][name]
            with open(f, "w", encoding="utf-8") as fp:
                yaml.safe_dump(d, fp, allow_unicode=True, sort_keys=False)
            return True
    return False


# ---------------- 执行 ----------------

def _eval_condition(expr: str, context: dict) -> bool:
    try:
        return bool(eval(expr, {"__builtins__": {}}, context))
    except Exception:
        return True


async def execute_workflow(workflow: dict, input_data: dict) -> dict:
    context: dict[str, Any] = {}
    context.update(input_data)
    steps_log: list[dict] = []

    for step in workflow.get("steps", []):
        tool_name = step.get("tool")
        condition = step.get("condition")
        with_params = step.get("with") or {}

        if condition and not _eval_condition(condition, context):
            steps_log.append({"tool": tool_name, "skipped": True, "condition": condition})
            continue

        tool = get_tool(tool_name)
        if not tool:
            steps_log.append({"tool": tool_name, "error": "tool not found"})
            break

        step_inputs = {**context, **with_params}
        try:
            result = await tool["func"](step_inputs)
            if isinstance(result, dict):
                context.update(result)
            steps_log.append({"tool": tool_name, "output": result})
        except Exception as e:
            steps_log.append({"tool": tool_name, "error": str(e)})
            break

    return {"context": context, "steps": steps_log}
