from http.client import HTTPException

import httpx

from app.config import OLLAMA_URL, DEFAULT_MODEL, REQUEST_TIMEOUT


async def chat(
        prompt: str,
        system: str = "",
        model: str = DEFAULT_MODEL,
        json_mode: bool = False,
        temperature: float = 0.2,
) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(OLLAMA_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"]


from app.config import EMBED_MODEL, EMBED_URL


async def embed(text, model: str = EMBED_MODEL):
    """
    调用 Ollama embedding。
    - text 为 str：返回 list[float]
    - text 为 list[str]：返回 list[list[float]]
    """
    is_batch = isinstance(text, (list, tuple))
    payload_input = list(text) if is_batch else text

    try:
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            r = await client.post(
                EMBED_URL,
                json={"model": model, "input": payload_input},
            )
            r.raise_for_status()
            data = r.json()
            embs = data.get("embeddings")
            if not embs:
                raise ValueError(f"embedding 返回为空: {data}")
            return embs if is_batch else embs[0]
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=f"无法连接 Ollama embedding ({EMBED_URL})，请确认 ollama serve 已启动且已 pull {model}。错误: {e}",
        )
