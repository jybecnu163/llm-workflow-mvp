import json

from app.ollama_client import chat

SYSTEM = "你是数据路由助手，只输出 JSON。"


async def classify_data(data: dict) -> dict:
    text = (
                   data.get("text")
                   or data.get("body")
                   or data.get("content")
                   or json.dumps(data, ensure_ascii=False)
           )[:2000]

    prompt = f"""判断以下数据的类型和类别。

可选类型:
- email:   类别 spam / normal / phishing / support
- review:  类别 positive / negative / neutral
- news:    类别 finance / tech / sports / entertainment / other
- other

只输出 JSON: {{"data_type":"...","category":"...","confidence":0.0}}

文本:
{text}"""

    raw = await chat(prompt, system=SYSTEM, json_mode=True)
    try:
        return json.loads(raw)
    except Exception:
        return {"data_type": "other", "category": "unknown", "confidence": 0.0}
