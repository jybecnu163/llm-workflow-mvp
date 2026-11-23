from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional


class RunRequest(BaseModel):
    data: dict
    workflow: Optional[str] = None
    auto_route: bool = False


class ToolRunRequest(BaseModel):
    inputs: dict[str, Any]


class WorkflowSaveRequest(BaseModel):
    yaml: str


class PlanStep(BaseModel):
    """计划中的一个顺序执行步骤。with_ 使用别名 `with` 对接 LLM 输出。"""

    model_config = ConfigDict(populate_by_name=True)

    tool: str
    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    input_from: Optional[str] = None
    condition: Optional[str] = None
    reason: str = ""


class ExecutionPlan(BaseModel):
    """自然语言指令翻译出的可执行计划。"""

    intent: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    """生成计划的请求。"""

    instruction: str
    data: dict[str, Any] = Field(default_factory=dict)
    auto_execute: bool = False


class PlanExecuteRequest(BaseModel):
    """执行已确认计划的请求（UI 二次确认后调用）。"""

    workflow: dict[str, Any]
    data: dict[str, Any] = Field(default_factory=dict)
