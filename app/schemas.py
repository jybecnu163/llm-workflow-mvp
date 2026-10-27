from pydantic import BaseModel
from typing import Any, Optional


class RunRequest(BaseModel):
    data: dict
    workflow: Optional[str] = None
    auto_route: bool = False


class ToolRunRequest(BaseModel):
    inputs: dict[str, Any]

class WorkflowSaveRequest(BaseModel):
    yaml: str