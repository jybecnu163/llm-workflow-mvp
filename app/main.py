from fastapi import FastAPI, HTTPException

from app.engine import (
    load_workflows,
    execute_workflow,
    load_workflow_raw,
    save_workflow_raw,
    delete_workflow,
)
from app.router import classify_data
from app.schemas import RunRequest, ToolRunRequest, WorkflowSaveRequest
from app.tools import list_tools, get_tool

app = FastAPI(title="LLM Workflow MVP")


def _pick_workflow(route: dict, workflows: dict) -> str:
    dt = route.get("data_type")
    cat = route.get("category")
    if dt and cat and f"{dt}_{cat}" in workflows:
        return f"{dt}_{cat}"
    if dt and dt in workflows:
        return dt
    return "default"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tools")
def api_list_tools():
    return list_tools()


@app.post("/tools/{name}/run")
async def api_run_tool(name: str, req: ToolRunRequest):
    tool = get_tool(name)
    print(name)
    print(tool)
    print(req.inputs)
    if not tool:
        raise HTTPException(404, f"tool not found: {name}")
    result = await tool["func"](req.inputs)
    return {"tool": name, "output": result}


@app.get("/workflows")
def api_list_workflows():
    wfs = load_workflows()
    return {
        name: {
            "description": wf.get("description", ""),
            "steps": [s.get("tool") for s in wf.get("steps", [])],
        }
        for name, wf in wfs.items()
    }


@app.get("/workflows/{name}/raw")
def api_get_workflow_raw(name: str):
    try:
        content = load_workflow_raw(name)
    except FileNotFoundError:
        raise HTTPException(404, f"workflow not found: {name}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"name": name, "yaml": content}


@app.put("/workflows/{name}")
def api_save_workflow(name: str, req: WorkflowSaveRequest):
    try:
        save_workflow_raw(name, req.yaml)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"saved": True, "name": name}


@app.delete("/workflows/{name}")
def api_delete_workflow(name: str):
    try:
        ok = delete_workflow(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, f"workflow not found: {name}")
    return {"deleted": True, "name": name}


@app.post("/classify")
async def api_classify(data: dict):
    return await classify_data(data)


@app.post("/run")
async def api_run(req: RunRequest):
    wfs = load_workflows()
    route = None

    if req.auto_route:
        route = await classify_data(req.data)
        workflow_name = _pick_workflow(route, wfs)
    else:
        workflow_name = req.workflow or "default"

    if workflow_name not in wfs:
        raise HTTPException(404, f"workflow not found: {workflow_name}")

    result = await execute_workflow(wfs[workflow_name], req.data)
    return {
        "workflow": workflow_name,
        "route": route,
        "result": result,
    }
