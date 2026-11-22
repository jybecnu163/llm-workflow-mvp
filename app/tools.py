import json
import os
from pathlib import Path
from typing import Any, Callable, Dict

import pandas as pd

from app import rag
from app.config import EXCEL_PREVIEW_ROWS, EXCEL_WORKDIR
from app.ollama_client import chat

TOOLS: Dict[str, Dict[str, Any]] = {}


def register(name: str, description: str, input_schema: dict, output_schema: dict):
    def wrapper(fn: Callable):
        TOOLS[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "func": fn,
        }
        return fn

    return wrapper


def get_tool(name: str):
    return TOOLS.get(name)


def list_tools():
    return [
        {k: v for k, v in t.items() if k != "func"}
        for t in TOOLS.values()
    ]


def _safe_json(raw: str, fallback: dict) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        return {**fallback, "_raw": raw}


# ---------- 分类类工具 ----------

@register(
    name="classify_email",
    description="将邮件分类为 spam / normal / phishing / support",
    input_schema={"subject": "string", "body": "string"},
    output_schema={"category": "string", "confidence": "number", "reason": "string"},
)
async def classify_email(inputs: dict) -> dict:
    subject = inputs.get("subject", "")
    body = inputs.get("body") or inputs.get("text") or ""
    prompt = f"""将以下邮件分类为: spam, normal, phishing, support
只输出 JSON: {{"category":"...","confidence":0.0,"reason":"..."}}

主题: {subject}
正文: {body[:3000]}"""
    raw = await chat(prompt, system="你是邮件分类助手，只输出 JSON。", json_mode=True)
    return _safe_json(raw, {"category": "normal", "confidence": 0.0, "reason": ""})


@register(
    name="classify_news",
    description="将新闻分类为 finance / tech / sports / entertainment / other",
    input_schema={"text": "string"},
    output_schema={"category": "string", "confidence": "number"},
)
async def classify_news(inputs: dict) -> dict:
    text = inputs.get("text", "")[:3000]
    prompt = f"""将以下新闻分类为: finance, tech, sports, entertainment, other
只输出 JSON: {{"category":"...","confidence":0.0}}

新闻: {text}"""
    raw = await chat(prompt, system="你是新闻分类助手，只输出 JSON。", json_mode=True)
    return _safe_json(raw, {"category": "other", "confidence": 0.0})


@register(
    name="sentiment_aspect",
    description="对商品评价做情感 + 方面抽取",
    input_schema={"text": "string"},
    output_schema={"sentiment": "string", "aspects": "array", "summary": "string"},
)
async def sentiment_aspect(inputs: dict) -> dict:
    text = inputs.get("text", "")[:3000]
    prompt = f"""分析以下商品评价，输出 JSON:
{{"sentiment":"positive|negative|neutral",
  "aspects":[{{"aspect":"物流|质量|客服|价格|功能","sentiment":"positive|negative|neutral"}}],
  "summary":"一句话总结"}}

评价: {text}"""
    raw = await chat(prompt, system="你是评价分析助手，只输出 JSON。", json_mode=True)
    return _safe_json(raw, {"sentiment": "neutral", "aspects": [], "summary": ""})


# ---------- 摘要 / 抽取类工具 ----------

@register(
    name="summarize_text",
    description="将文本总结为一句话",
    input_schema={"text": "string"},
    output_schema={"summary": "string"},
)
async def summarize_text(inputs: dict) -> dict:
    text = inputs.get("text", "")[:4000]
    prompt = f"用一句话总结以下文本，只输出总结内容：\n\n{text}"
    summary = await chat(prompt)
    return {"summary": summary.strip()}


@register(
    name="extract_entities",
    description="抽取人名、公司、时间、金额、地点",
    input_schema={"text": "string"},
    output_schema={"entities": "object"},
)
async def extract_entities(inputs: dict) -> dict:
    text = inputs.get("text", "")[:3000]
    prompt = f"""从文本中抽取实体，输出 JSON:
{{"persons":[],"orgs":[],"times":[],"amounts":[],"locations":[]}}

文本: {text}"""
    raw = await chat(prompt, system="你是实体抽取助手，只输出 JSON。", json_mode=True)
    return _safe_json(raw, {"persons": [], "orgs": [], "times": [], "amounts": [], "locations": []})


@register(
    name="extract_ticket",
    description="从客服文本中抽取工单信息",
    input_schema={"text": "string"},
    output_schema={"order_id": "string", "issue_type": "string", "urgency": "string"},
)
async def extract_ticket(inputs: dict) -> dict:
    text = inputs.get("text", "")[:3000]
    prompt = f"""从客服消息中抽取工单信息，输出 JSON:
{{"order_id":"...","issue_type":"退款|物流|质量|账号|其他","urgency":"high|medium|low"}}

消息: {text}"""
    raw = await chat(prompt, system="你是工单抽取助手，只输出 JSON。", json_mode=True)
    return _safe_json(raw, {"order_id": "", "issue_type": "其他", "urgency": "medium"})


# ---------- 生成类工具 ----------

@register(
    name="draft_reply",
    description="基于上下文生成客服回复草稿",
    input_schema={"text": "string", "summary": "string"},
    output_schema={"reply": "string"},
)
async def draft_reply(inputs: dict) -> dict:
    text = inputs.get("text", "")[:2000]
    summary = inputs.get("summary", "")
    prompt = f"""你是客服。请针对用户消息，生成一段礼貌、专业的中文回复草稿。
用户消息: {text}
摘要: {summary}
回复:"""
    reply = await chat(prompt)
    return {"reply": reply.strip()}


# ---------- IO / 副作用类工具（示例） ----------

@register(
    name="write_db",
    description="模拟写库（打印日志）",
    input_schema={"text": "string"},
    output_schema={"saved": "boolean"},
)
async def write_db(inputs: dict) -> dict:
    print("[write_db] 保存数据:", str(inputs)[:200])
    return {"saved": True}


@register(
    name="alert_ops",
    description="模拟告警（打印日志）",
    input_schema={"summary": "string"},
    output_schema={"alerted": "boolean"},
)
async def alert_ops(inputs: dict) -> dict:
    print("[alert_ops] 告警:", inputs.get("summary", ""))
    return {"alerted": True}


# ---------- 翻译类工具 ----------

@register(
    name="translate_text",
    description="将文本翻译为目标语言（支持中/英/日/韩/法/德/西等）",
    input_schema={
        "text": "string",
        "target_lang": "string 例如 中文 / 英文 / 日文",
        "source_lang": "string 可选，默认自动检测",
        "style": "string 可选，formal / casual / literal，默认 formal",
    },
    output_schema={
        "translation": "string",
        "source_lang": "string",
        "target_lang": "string",
    },
)
async def translate_text(inputs: dict) -> dict:
    text = (inputs.get("text") or "").strip()
    if not text:
        return {"translation": "", "source_lang": "", "target_lang": ""}

    target_lang = inputs.get("target_lang") or "中文"
    source_lang = inputs.get("source_lang") or "自动检测"
    style = inputs.get("style") or "formal"

    prompt = f"""你是专业翻译。请将下面的文本翻译成 {target_lang}。
源语言: {source_lang}
风格: {style}

要求:
1. 只输出译文，不要解释、不要引号、不要额外说明。
2. 保留原文的段落、标点和数字。
3. 专有名词如无通用译名，保留原文并加括号标注。
4. 如果原文已经是 {target_lang}，原样返回。

原文:
{text[:4000]}"""

    translation = await chat(
        prompt,
        system="你是专业翻译，只输出译文本身。",
        temperature=0.2,
    )
    return {
        "translation": translation.strip(),
        "source_lang": source_lang,
        "target_lang": target_lang,
    }


@register(
    name="summarize_and_translate",
    description="先总结，再翻译成目标语言",
    input_schema={"text": "string", "target_lang": "string"},
    output_schema={"summary": "string", "translation": "string"},
)
async def summarize_and_translate(inputs: dict) -> dict:
    text = inputs.get("text", "")
    target_lang = inputs.get("target_lang", "英文")

    # 复用已有工具
    summary_result = await summarize_text({"text": text})
    summary = summary_result.get("summary", "")

    trans_result = await translate_text(
        {"text": summary, "target_lang": target_lang}
    )
    return {
        "summary": summary,
        "translation": trans_result.get("translation", ""),
    }


# ---------- 旅游标签 ----------

TRAVEL_TAG_TAXONOMY = {
    "theme": ["亲子", "蜜月", "探险", "文化", "美食", "购物", "摄影",
              "自然风光", "历史古迹", "海岛", "温泉", "邮轮"],
    "pace": ["轻松", "适中", "紧凑", "深度游", "自由行", "跟团"],
    "audience": ["家庭", "情侣", "老人", "独自", "闺蜜", "商务", "学生"],
    "season": ["春季", "夏季", "秋季", "冬季", "樱花季", "红叶季",
               "避暑", "春节", "国庆"],
    "experience": ["潜水", "滑雪", "徒步", "热气球", "和服体验",
                   "野生动物", "露营", "自驾"],
    "budget": ["经济", "舒适", "轻奢", "高端"],
    "marketing": ["爆款", "小众", "性价比", "网红打卡", "新上线"],
    "risk": ["高原", "需签证", "极限运动", "长途飞行", "需疫苗"],
}


def _taxonomy_text() -> str:
    return "\n".join(f"- {k}: {', '.join(v)}" for k, v in TRAVEL_TAG_TAXONOMY.items())


@register(
    name="extract_itinerary_fields",
    description="从旅游行程文本中抽取结构化字段",
    input_schema={"text": "string"},
    output_schema={
        "destination": "string",
        "days": "number",
        "depart_city": "string",
        "price": "number",
        "transport": "string",
        "hotel_level": "string",
        "months": "array",
    },
)
async def extract_itinerary_fields(inputs: dict) -> dict:
    text = (inputs.get("text") or "")[:4000]
    prompt = f"""从以下旅游行程中抽取字段，只输出 JSON：
{{"destination":"","days":0,"depart_city":"","price":0,
  "transport":"","hotel_level":"","months":[]}}
无法确定的字段留空或 0。

行程：
{text}"""
    raw = await chat(prompt, system="你是旅游信息抽取助手，只输出 JSON。", json_mode=True)
    return _safe_json(raw, {
        "destination": "", "days": 0, "depart_city": "",
        "price": 0, "transport": "", "hotel_level": "", "months": [],
    })


@register(
    name="generate_travel_tags",
    description="为旅游产品/行程生成受控标签",
    input_schema={"text": "string"},
    output_schema={
        "theme": "array", "pace": "array", "audience": "array",
        "season": "array", "experience": "array", "budget": "array",
        "marketing": "array", "risk": "array", "extra_tags": "array",
    },
)
async def generate_travel_tags(inputs: dict) -> dict:
    text = (inputs.get("text") or "")[:4000]
    taxonomy = _taxonomy_text()
    prompt = f"""你是旅游产品标签专家。请根据行程信息生成标签。

【受控词表】只能从以下标签中选择，不要发明新标签：
{taxonomy}

【任务】
1. 每个维度选择 0-3 个最贴切的标签。
2. 每个标签给出 0-1 的置信度和原文证据片段。
3. 不适用则返回空数组。
4. extra_tags 放词表外你认为重要但词表没有的词，最多 5 个。
5. 只输出 JSON，不要解释。

【输出格式】
{{"theme":[{{"tag":"","confidence":0.0,"evidence":""}}],
 "pace":[],"audience":[],"season":[],"experience":[],
 "budget":[],"marketing":[],"risk":[],"extra_tags":[]}}

【行程信息】
{text}"""

    raw = await chat(
        prompt,
        system="你是旅游标签专家，只输出 JSON。",
        json_mode=True,
        temperature=0.1,
    )
    empty = {k: [] for k in [
        "theme", "pace", "audience", "season", "experience",
        "budget", "marketing", "risk", "extra_tags",
    ]}
    return _safe_json(raw, empty)


@register(
    name="normalize_tags",
    description="将标签归一化到受控词表，丢弃词表外标签",
    input_schema={},
    output_schema={"normalized": "object", "dropped": "array"},
)
async def normalize_tags(inputs: dict) -> dict:
    valid = {t for v in TRAVEL_TAG_TAXONOMY.values() for t in v}
    normalized: dict[str, list] = {}
    dropped: list[str] = []

    for dim in TRAVEL_TAG_TAXONOMY:
        items = inputs.get(dim) or []
        kept = []
        for it in items:
            tag = it.get("tag") if isinstance(it, dict) else it
            if tag in valid:
                kept.append(it)
            elif tag:
                dropped.append(tag)
        if kept:
            normalized[dim] = kept

    for tag in inputs.get("extra_tags") or []:
        if tag not in valid:
            dropped.append(tag)

    return {"normalized": normalized, "dropped": dropped}


@register(
    name="render_tag_summary",
    description="把归一化标签渲染成一行可读文本",
    input_schema={},
    output_schema={"tag_line": "string"},
)
async def render_tag_summary(inputs: dict) -> dict:
    tags = inputs.get("normalized") or {}
    parts = []
    for dim, items in tags.items():
        names = [it.get("tag") if isinstance(it, dict) else str(it) for it in items]
        names = [n for n in names if n]
        if names:
            parts.append(f"{dim}:{'/'.join(names)}")
    return {"tag_line": " | ".join(parts)}


@register(
    name="merge_tags",
    description="合并多个标签结果（按置信度投票）",
    input_schema={"tag_chunks": "array"},
    output_schema={"merged": "object"},
)
async def merge_tags(inputs: dict) -> dict:
    from collections import defaultdict
    scores: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for chunk in inputs.get("tag_chunks") or []:
        for dim, items in (chunk or {}).items():
            for it in items or []:
                if isinstance(it, dict):
                    scores[dim][it.get("tag", "")] += it.get("confidence", 0.5)
                else:
                    scores[dim][str(it)] += 0.5
    merged = {
        dim: [{"tag": t, "confidence": round(min(s, 1.0), 2)}
              for t, s in sorted(v.items(), key=lambda x: -x[1])[:3]]
        for dim, v in scores.items()
    }
    return {"merged": merged}


# ---------- 文本纠错 ----------

@register(
    name="correct_text",
    description="对文本进行错别字/语法/标点纠错，输出 diff",
    input_schema={
        "text": "string",
        "strict": "boolean 可选，true 时只改错别字不改标点",
    },
    output_schema={
        "corrected": "string",
        "changes": "array",
        "confidence": "number",
        "no_change": "boolean",
    },
)
async def correct_text(inputs: dict) -> dict:
    text = (inputs.get("text") or "")[:4000]
    if not text.strip():
        return {"corrected": "", "changes": [], "confidence": 1.0, "no_change": True}

    strict = inputs.get("strict", False)
    extra_rule = "8. strict 模式：只改错别字，标点和语法都不要动。" if strict else ""

    prompt = f"""你是中文文本纠错助手，修改最少的字数达到全句通顺。请只修正以下错误，不要改写。

【只修正这些】
1. 错别字、同音字、同型字，尤其是在整个句子中不通顺时的谐音字
2. 语法错误（语序、助词、量词）
3. 标点符号
4. 英文拼写错误
5. 明显的重复词
6. 着重检测专有名词中的错别字
7. 检测文本开头时的地名等专有名词的错误

【绝对不要做】
1. 不要改变原意
2. 不要把口语改成书面语
3. 不要同义替换
4. 不要修改专有名词、品牌名、人名、地名
5. 不要改数字、日期、金额
6. 不要删减或增加信息
7. 不要加解释、不要加引号
{extra_rule}

【输出】只输出 JSON：
{{"corrected":"纠错后全文",
 "changes":[{{"original":"","corrected":"","type":"错别字|语法|标点|拼写|重复","reason":""}}],
 "confidence":0.0,
 "no_change":false}}

无错误时 corrected 等于原文，changes 为空，no_change 为 true。

【原文】
{text}"""

    raw = await chat(
        prompt,
        system="你是文本纠错助手，只输出 JSON。",
        json_mode=True,
        temperature=0.0,
    )
    result = _safe_json(raw, {
        "corrected": text, "changes": [], "confidence": 0.0, "no_change": True,
    })

    # 兜底：如果模型没返回 corrected，回退原文
    if not result.get("corrected"):
        result["corrected"] = text
    return result


@register(
    name="verify_correction",
    description="校验纠错结果：相似度过低时回退原文，防止过度纠正",
    input_schema={"text": "string", "corrected": "string"},
    output_schema={"final": "string", "similarity": "number", "reverted": "boolean"},
)
async def verify_correction(inputs: dict) -> dict:
    import difflib
    original = inputs.get("text", "")
    corrected = inputs.get("corrected", "") or original

    ratio = difflib.SequenceMatcher(None, original, corrected).ratio()
    # 相似度低于 0.85 视为改动过大，回退原文
    if ratio < 0.85:
        return {"final": original, "similarity": round(ratio, 3), "reverted": True}
    return {"final": corrected, "similarity": round(ratio, 3), "reverted": False}


@register(
    name="correct_text_by_sentence",
    description="按句切分后逐句纠错，再合并",
    input_schema={"text": "string"},
    output_schema={"corrected": "string", "changes": "array"},
)
async def correct_text_by_sentence(inputs: dict) -> dict:
    import re
    text = inputs.get("text", "")
    # 简单按中英文句末标点切分
    sentences = re.split(r"(?<=[。！？!?；;])", text)
    sentences = [s for s in sentences if s.strip()]

    all_changes = []
    corrected_parts = []
    for s in sentences:
        r = await correct_text({"text": s})
        corrected_parts.append(r.get("corrected", s))
        for c in r.get("changes", []):
            c["sentence"] = s.strip()[:50]
            all_changes.append(c)

    return {"corrected": "".join(corrected_parts), "changes": all_changes}


PROTECTED_TERMS = ["京东", "京东京", "俺们"]


@register(
    name="protect_terms",
    description="把受保护术语强制还原为原文",
    input_schema={"text": "string", "corrected": "string"},
    output_schema={"final": "string"},
)
async def protect_terms(inputs: dict) -> dict:
    corrected = inputs.get("corrected", "")
    # 简化示例：这里可以做成 fuzzy 匹配
    # 实际场景建议用分词 + 位置比对
    return {"final": corrected}


# ---------- Excel 自然语言操作 ----------

def _safe_excel_path(name: str) -> Path:
    base = EXCEL_WORKDIR.resolve()
    p = (base / name).resolve() if not os.path.isabs(name) else Path(name).resolve()
    if not str(p).startswith(str(base)):
        raise ValueError(f"路径必须位于 {base} 内")
    if p.suffix.lower() not in (".xlsx", ".xls", ".csv"):
        raise ValueError("只支持 .xlsx / .xls / .csv")
    if not p.exists():
        raise FileNotFoundError(str(p))
    return p


def _load_df(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path, engine="openpyxl")


def _df_records(df: pd.DataFrame, n: int) -> list[dict]:
    sub = df.head(n).copy().astype(object)
    sub = sub.where(pd.notna(sub), None)
    return sub.to_dict(orient="records")


def _apply_operations(df: pd.DataFrame, ops: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    errors: list[dict] = []
    for i, op in enumerate(ops):
        t = (op.get("type") or "").lower()
        try:
            if t == "filter":
                col, o, v = op.get("column"), op.get("op"), op.get("value")
                if col not in df.columns:
                    errors.append({"step": i, "error": f"列不存在: {col}"});
                    continue
                s = df[col]
                if o == "==":
                    df = df[s == v]
                elif o == "!=":
                    df = df[s != v]
                elif o == ">":
                    df = df[s > v]
                elif o == ">=":
                    df = df[s >= v]
                elif o == "<":
                    df = df[s < v]
                elif o == "<=":
                    df = df[s <= v]
                elif o == "contains":
                    df = df[s.astype(str).str.contains(str(v), na=False)]
                elif o == "in":
                    df = df[s.isin(v if isinstance(v, list) else [v])]
            elif t == "sort":
                col = op.get("column")
                if col in df.columns:
                    df = df.sort_values(by=col, ascending=bool(op.get("ascending", True)))
            elif t == "select":
                cols = [c for c in (op.get("columns") or []) if c in df.columns]
                if cols: df = df[cols]
            elif t == "groupby":
                by = op.get("by")
                agg = op.get("agg") or {}
                if not by or not agg:
                    errors.append({"step": i, "error": "groupby 缺少 by 或 agg"})
                    continue

                by_cols = by if isinstance(by, list) else [by]
                by_cols = [c for c in by_cols if c in df.columns]
                valid_agg = {
                    k: v for k, v in agg.items()
                    if k in df.columns and k not in by_cols
                }

                if not by_cols:
                    errors.append({"step": i, "error": f"groupby 列不存在: {by}"})
                elif not valid_agg:
                    errors.append({"step": i, "error": f"agg 列不存在: {agg}"})
                else:
                    df = df.groupby(by_cols, as_index=False).agg(valid_agg)
            elif t == "top_n":
                n = int(op.get("n", 10))
                by = op.get("by")
                if by and by in df.columns:
                    asc = bool(op.get("ascending", False))
                    df = df.sort_values(by=by, ascending=asc).head(n)
                else:
                    df = df.head(n)
            elif t == "dedupe":
                subset = [c for c in (op.get("subset") or []) if c in df.columns] or None
                df = df.drop_duplicates(subset=subset)
            elif t == "fillna":
                col = op.get("column")
                if col in df.columns:
                    df[col] = df[col].fillna(op.get("value"))
            elif t == "rename":
                mapping = {k: v for k, v in (op.get("mapping") or {}).items() if k in df.columns}
                if mapping: df = df.rename(columns=mapping)
            elif t == "head":
                df = df.head(int(op.get("n", 10)))
            elif t == "substr":
                col = op.get("column")
                start = int(op.get("start", 0))
                end = op.get("end")
                to = op.get("to") or col
                if col not in df.columns:
                    errors.append({"step": i, "error": f"列不存在: {col}"})
                    continue
                s = df[col].astype(str)
                df[to] = s.str.slice(start, end) if end is not None else s.str.slice(start)
            elif t == "extract":
                col = op.get("column")
                pattern = op.get("pattern")
                to = op.get("to")
                if col not in df.columns or not pattern or not to:
                    errors.append({"step": i, "error": "extract 参数不完整"})
                    continue
                df[to] = df[col].astype(str).str.extract(pattern, expand=False)
            elif t == "date_part":
                col = op.get("column")
                part = (op.get("part") or "").lower()
                to = op.get("to") or f"{col}_{part}"
                if col not in df.columns:
                    errors.append({"step": i, "error": f"列不存在: {col}"})
                    continue
                s = pd.to_datetime(df[col], errors="coerce")
                if part == "year":
                    df[to] = s.dt.year
                elif part == "month":
                    df[to] = s.dt.month
                elif part == "quarter":
                    df[to] = s.dt.quarter
                elif part == "year_quarter":
                    df[to] = s.dt.year.astype(str) + "-Q" + s.dt.quarter.astype(str)
                elif part == "year_month":
                    df[to] = s.dt.strftime("%Y-%m")
                elif part == "day":
                    df[to] = s.dt.day
                elif part == "weekday":
                    df[to] = s.dt.weekday
                else:
                    errors.append({"step": i, "error": f"不支持的 date_part: {part}"})
            else:
                errors.append({"step": i, "error": f"不支持的操作: {t}"})
        except Exception as e:
            errors.append({"step": i, "error": str(e)})
    return df, errors


@register(
    name="excel_describe",
    description="读取 Excel/CSV，返回列名、类型、行数和样本数据",
    input_schema={"path": "string 相对 data/excel/ 的文件名"},
    output_schema={"columns": "array", "rows": "number", "schema": "array", "preview": "array"},
)
async def excel_describe(inputs: dict) -> dict:
    path = _safe_excel_path(inputs["path"])
    df = _load_df(path)
    schema = [
        {"column": c, "dtype": str(df[c].dtype),
         "sample": [str(x) for x in df[c].dropna().head(3).tolist()]}
        for c in df.columns
    ]
    return {
        "path": str(path),
        "rows": int(len(df)),
        "columns": list(df.columns),
        "schema": schema,
        "preview": _df_records(df, 5),
    }


@register(
    name="excel_plan",
    description="把自然语言需求转成 Excel 操作计划 JSON",
    input_schema={"question": "string", "columns": "array", "schema": "array", "preview": "array"},
    output_schema={"operations": "array", "answer_hint": "string"},
)
async def excel_plan(inputs: dict) -> dict:
    question = inputs.get("question", "")
    columns = inputs.get("columns") or []
    schema = inputs.get("schema") or []
    preview = inputs.get("preview") or []

    schema_str = json.dumps(schema, ensure_ascii=False)
    preview_str = json.dumps(preview, ensure_ascii=False)

    prompt = f"""你是 Excel 操作计划生成器。请把用户需求翻译成 JSON 操作序列。

    【可用操作】
    - {{"type":"filter","column":"","op":"==|!=|>|>=|<|<=|contains|in","value":""}}
    - {{"type":"sort","column":"","ascending":true}}
    - {{"type":"select","columns":[""]}}
    - {{"type":"substr","column":"","start":0,"end":7,"to":"新列名"}}
    - {{"type":"extract","column":"","pattern":"正则","to":"新列名"}}
    - {{"type":"date_part","column":"","part":"year|month|quarter|year_quarter|year_month|day|weekday","to":"新列名"}}
    - {{"type":"groupby","by":"列名或数组","agg":{{"列":"sum|mean|count|max|min"}}}}
    - {{"type":"top_n","n":10,"by":"","ascending":false}}
    - {{"type":"dedupe","subset":[""]}}
    - {{"type":"fillna","column":"","value":""}}
    - {{"type":"rename","mapping":{{"旧":"新"}}}}
    - {{"type":"head","n":10}}

    【规则】
    1. 只能使用上面的列名，不要发明列名。
    2. 只输出 JSON，格式：{{"operations":[...],"answer_hint":"一句话说明"}}
    3. 不要输出 Python 代码、SQL 或解释。
    4. 按多个维度分组时，by 用数组；单维度用字符串。
    5. 聚合函数只能用 sum / mean / count / max / min。
    6. **日期维度一律用 date_part，不要用 rename 或 substr 假装**：
       - 按月份 → {{"type":"date_part","column":"日期","part":"year_month","to":"month"}}
       - 按季度 → {{"type":"date_part","column":"日期","part":"year_quarter","to":"quarter"}}
       - 按年份 → {{"type":"date_part","column":"日期","part":"year","to":"year"}}
    7. rename 只改列名不改值，不能用于提取时间维度。
    8. 季度定义：Q1=1-3月，Q2=4-6月，Q3=7-9月，Q4=10-12月。

    【示例】
    用户：按季度统计销售额
    输出：{{"operations":[
      {{"type":"date_part","column":"日期","part":"year_quarter","to":"quarter"}},
      {{"type":"groupby","by":"quarter","agg":{{"销售额":"sum"}}}}
    ],"answer_hint":"按年-季度汇总销售额"}}

    用户：按月份统计销售额
    输出：{{"operations":[
      {{"type":"date_part","column":"日期","part":"year_month","to":"month"}},
      {{"type":"groupby","by":"month","agg":{{"销售额":"sum"}}}}
    ],"answer_hint":"按年-月份汇总销售额"}}

    【表结构】
    列名: {columns}
    详细类型: {schema_str}
    样本数据: {preview_str}

    【用户需求】
    {question}"""

    raw = await chat(
        prompt,
        system="你是 Excel 操作计划生成器，只输出 JSON。",
        json_mode=True,
        temperature=0.1,
    )
    return _safe_json(raw, {"operations": [], "answer_hint": ""})


@register(
    name="excel_execute",
    description="执行 Excel 操作计划，返回结果预览",
    input_schema={"path": "string", "operations": "array"},
    output_schema={"result_rows": "number", "result_columns": "array",
                   "result_preview": "array", "errors": "array", "warnings": "array"},
)
async def excel_execute(inputs: dict) -> dict:
    path = _safe_excel_path(inputs["path"])
    df = _load_df(path)
    original_rows = len(df)
    ops = inputs.get("operations") or []
    result_df, errors = _apply_operations(df, ops)

    warnings = []
    has_groupby = any((op.get("type") or "").lower() == "groupby" for op in ops)
    if has_groupby and len(result_df) == original_rows and original_rows > 0:
        warnings.append(
            f"执行了 groupby，但结果行数仍为 {original_rows}，"
            f"分组键可能包含唯一值（例如直接按具体日期分组）。"
            f"如果用户要按月/年统计，应先用 substr 截取日期。"
        )

    return {
        "result_rows": int(len(result_df)),
        "result_columns": list(result_df.columns),
        "result_preview": _df_records(result_df, EXCEL_PREVIEW_ROWS),
        "errors": errors,
        "warnings": warnings,
    }


@register(
    name="excel_answer",
    description="根据操作结果用自然语言回答用户",
    input_schema={"question": "string", "result_rows": "number",
                  "result_preview": "array", "operations": "array",
                  "errors": "array", "warnings": "array"},
    output_schema={"answer": "string"},
)
async def excel_answer(inputs: dict) -> dict:
    question = inputs.get("question", "")
    rows = inputs.get("result_rows", 0)
    preview = inputs.get("result_preview") or []
    ops = inputs.get("operations") or []
    errors = inputs.get("errors") or []
    warnings = inputs.get("warnings") or []

    if errors:
        err_str = "；".join(
            f"第 {e.get('step', '?')} 步: {e.get('error', '')}" for e in errors
        )
        return {"answer": f"执行出错，无法给出准确结果：{err_str}。请检查列名或操作计划。"}

    if rows == 0:
        return {"answer": "按你的条件没有筛选到数据，请检查条件或列名。"}

    warn_str = "；".join(warnings) if warnings else "无"
    preview_str = json.dumps(preview, ensure_ascii=False)
    ops_str = json.dumps(ops, ensure_ascii=False)

    prompt = f"""你是数据分析助手。请根据执行结果，用简洁中文回答用户问题。

【用户问题】
{question}

【执行的操作】
{ops_str}

【结果行数】{rows}

【结果预览（最多 {EXCEL_PREVIEW_ROWS} 行）】
{preview_str}

【警告】{warn_str}

【硬性要求】
1. **禁止自己计算、求和、心算**。所有数字必须直接来自上面的结果预览。
2. 如果结果预览里已经是分组后的数据，直接引用，不要再聚合。
3. 如果警告不为"无"，必须如实告知用户数据可能不准确。
4. 如果结果行数 > {EXCEL_PREVIEW_ROWS}，只展示前 {EXCEL_PREVIEW_ROWS} 行的关键结论，并说明总行数。
5. 不要编造预览里没有的数据。
6. 如果结果预览里的季度/月份字段只有一个，不要自行扩展到 Q2/Q3/Q4；如实说明"数据仅包含 XX 季度"。
7. 不要给结果加"注"或"说明"来解释数据不完整，除非预览里确实只有部分维度。

回答："""

    answer = await chat(prompt, temperature=0.1)
    return {"answer": answer.strip()}


# ---------- 文档 RAG 问答 ----------

@register(
    name="rag_ingest",
    description="将 PDF/TXT/MD 文档切分并入库到本地向量库",
    input_schema={"path": "string 相对 data/rag_docs/ 的文件名"},
    output_schema={
        "file": "string",
        "pages": "number",
        "chunks_added": "number",
        "collection_size": "number",
    },
)
async def rag_ingest(inputs: dict) -> dict:
    path = inputs.get("path") or inputs.get("file")
    if not path:
        raise ValueError("缺少 path 参数")
    return await rag.ingest_document(path)


@register(
    name="rag_search",
    description="在本地知识库中检索相关片段",
    input_schema={
        "question": "string",
        "top_k": "number 可选，默认 5",
        "source_filter": "string 可选，限定文件名",
    },
    output_schema={"chunks": "array", "count": "number"},
)
async def rag_search(inputs: dict) -> dict:
    question = inputs.get("question") or inputs.get("text") or ""
    top_k = int(inputs.get("top_k", 5))
    source = inputs.get("source_filter") or None
    chunks = await rag.search(question, top_k=top_k, source_filter=source)
    return {"chunks": chunks, "count": len(chunks)}


@register(
    name="rag_answer",
    description="基于本地知识库回答问题，返回答案与来源",
    input_schema={"question": "string", "top_k": "number 可选，默认 5"},
    output_schema={"answer": "string", "sources": "array", "chunks_used": "number"},
)
async def rag_answer(inputs: dict) -> dict:
    question = inputs.get("question") or inputs.get("text") or ""
    top_k = int(inputs.get("top_k", 5))
    return await rag.answer_question(question, top_k=top_k)


@register(
    name="rag_ingest_chapter_dir",
    description="按目录批量入库已分回的小说文件（文件名格式：第XXX回_标题.txt）",
    input_schema={"dir": "string 相对 data/rag_docs/ 的子目录名，例如 sanguo"},
    output_schema={
        "dir": "string",
        "files": "number",
        "chunks_added": "number",
        "collection_size": "number",
    },
)
async def rag_ingest_chapter_dir(inputs: dict) -> dict:
    dir_name = inputs.get("dir") or "sanguo"
    return await rag.ingest_chapter_files(dir_name)


@register(
    name="rag_rewrite_query",
    description="把口语化/现代视角的问题改写成原文可能出现的表达，提升检索命中率",
    input_schema={"question": "string"},
    output_schema={"rewritten": "array", "keywords": "array"},
)
async def rag_rewrite_query(inputs: dict) -> dict:
    question = inputs.get("question", "")
    prompt = f"""你要在《三国演义》原文中检索答案。请把用户问题改写成 3 条不同的检索查询，
尽量使用原文可能出现的人物名、地名、事件名，而不是现代概括词。

用户问题：{question}

只输出 JSON：
{{"rewritten":["...","...","..."],"keywords":["诸葛亮","祁山","街亭"]}}"""

    raw = await chat(prompt, system="你是检索查询改写助手，只输出 JSON。",
                     json_mode=True, temperature=0.2)
    return _safe_json(raw, {"rewritten": [question], "keywords": []})


@register(
    name="rag_answer_v2",
    description="RAG 问答 v2：查询改写 + 多路检索 + 合并",
    input_schema={"question": "string", "top_k": "number 可选"},
    output_schema={"answer": "string", "sources": "array", "rewritten": "array"},
)
async def rag_answer_v2(inputs: dict) -> dict:
    question = inputs.get("question") or inputs.get("text") or ""
    top_k = int(inputs.get("top_k", 5))

    rw = await rag_rewrite_query({"question": question})
    queries = rw.get("rewritten") or [question]
    queries = [question] + queries[:2]  # 原问 + 2 条改写

    all_chunks = []
    seen = set()
    for q in queries:
        chunks = await rag.search(q, top_k=top_k)
        for c in chunks:
            key = (c.get("source"), c.get("chapter"), c.get("chunk_index"))
            if key not in seen:
                seen.add(key)
                all_chunks.append(c)

    # 按 score 排序取前 top_k*2
    all_chunks.sort(key=lambda x: -x["score"])
    picked = all_chunks[: top_k * 2]

    return await rag._answer_with_chunks(question, picked, extra={"rewritten": queries})


# =====================================================================
# 以下为 TASKS.md 扩展工具（阶段一：内容创作类）
# =====================================================================

def _tool_text(inputs, *default_keys, limit=4000):
    """通用输入解析：优先 with 指定的 input_from，否则按 default_keys 取首个非空值。
    自动解包：字符串数组取首项、dict 取常见文本字段、chunks(list[dict]) 拼接全部 text。
    """
    src = inputs.get("input_from")
    keys = (src,) + default_keys if src else default_keys
    for k in keys:
        v = inputs.get(k)
        if not v:
            continue
        if isinstance(v, list) and v and all(isinstance(x, dict) and "text" in x for x in v):
            v = "\n\n".join(str(x.get("text") or "") for x in v)
        for _ in range(3):
            if isinstance(v, list):
                v = v[0] if v else ""
            elif isinstance(v, dict):
                v = (v.get("text") or v.get("summary") or v.get("content")
                     or v.get("answer") or v.get("corrected") or v.get("polished")
                     or v.get("expanded") or v.get("rewritten") or v.get("explanation")
                     or "")
            else:
                break
        if isinstance(v, (str, int, float)) and str(v).strip():
            return str(v).strip()[:limit]
    return ""


@register(
    name="polish_copy",
    description="文案润色大师：把平淡文本润色成指定风格（小红书/公文/朋友圈/商务）",
    input_schema={"text": "string", "style": "string 可选，默认小红书风"},
    output_schema={"polished": "string", "style": "string", "tips": "array"},
)
async def polish_copy(inputs: dict) -> dict:
    text = _tool_text(inputs, "text")
    if not text:
        return {"polished": "", "style": "", "tips": []}
    style = inputs.get("style") or "小红书风"
    prompt = f"""你是文案润色专家。请把下面的文本润色成「{style}」。
要求：保留原意与全部事实，不编造、不改动数字与专名；只优化表达；输出 JSON。
{{"polished":"润色后的文本","tips":["可选改进建议"]}}

原文：
{text}"""
    raw = await chat(prompt, system="你是文案润色专家，只输出 JSON。", json_mode=True, temperature=0.4)
    data = _safe_json(raw, {"polished": text, "tips": []})
    return {
        "polished": data.get("polished") or text,
        "style": style,
        "tips": data.get("tips") or [],
    }


@register(
    name="generate_hooks",
    description="爆款标题生成器：为文章/摘要生成多个吸引眼球的标题",
    input_schema={"text": "string", "count": "number 可选，默认5", "tone": "string 可选 悬念|干货|情绪"},
    output_schema={"hooks": "array", "count": "number"},
)
async def generate_hooks(inputs: dict) -> dict:
    text = _tool_text(inputs, "text")
    if not text:
        return {"hooks": [], "count": 0}
    try:
        count = max(1, min(10, int(inputs.get("count", 5))))
    except (TypeError, ValueError):
        count = 5
    tone = inputs.get("tone") or "干货"
    prompt = f"""你是标题创作专家。为下面内容生成 {count} 个「{tone}」风格标题。
要求：每个不超过20字、角度互不相同；不用"震惊/速看"等低俗词；不夸大事实。
只输出 JSON: {{"hooks":["标题1","标题2"]}}

内容：
{text}"""
    raw = await chat(prompt, system="你是标题创作助手，只输出 JSON。", json_mode=True, temperature=0.6)
    data = _safe_json(raw, {"hooks": []})
    hooks = [h for h in (data.get("hooks") or []) if isinstance(h, str) and h.strip()][:count]
    return {"hooks": hooks, "count": len(hooks)}


@register(
    name="rewrite_style",
    description="风格迁移器：用指定风格改写文本（鲁迅风/莎士比亚风/说给5岁小孩听等）",
    input_schema={"text": "string", "style": "string 可选，默认鲁迅风"},
    output_schema={"rewritten": "string"},
)
async def rewrite_style(inputs: dict) -> dict:
    text = _tool_text(inputs, "text")
    if not text:
        return {"rewritten": ""}
    style = inputs.get("style") or "鲁迅风"
    prompt = f"""你是文字风格大师。把下面的文本改写成「{style}」。
要求：保留全部核心信息与事实，只改表达方式；不加解释、不加引号。
只输出 JSON: {{"rewritten":"改写后的文本"}}

原文：
{text}"""
    raw = await chat(prompt, system="你是风格改写助手，只输出 JSON。", json_mode=True, temperature=0.5)
    data = _safe_json(raw, {"rewritten": text})
    return {"rewritten": data.get("rewritten") or text}


@register(
    name="expand_article",
    description="内容扩写器：把一句话/要点扩写成完整段落或文章大纲",
    input_schema={"text": "string", "target_length": "number 可选，默认300", "format": "string paragraph|outline"},
    output_schema={"expanded": "string"},
)
async def expand_article(inputs: dict) -> dict:
    text = _tool_text(inputs, "text")
    if not text:
        return {"expanded": ""}
    try:
        target = max(50, min(2000, int(inputs.get("target_length", 300))))
    except (TypeError, ValueError):
        target = 300
    fmt = inputs.get("format") or "paragraph"
    shape = "分层的Markdown大纲" if fmt == "outline" else "连贯完整的段落"
    prompt = f"""你是内容扩写专家。把下面要点扩写成约 {target} 字的{shape}。
要求：围绕原要点合理展开，不编造事实数据；结构清晰，不灌水不重复。
只输出 JSON: {{"expanded":"扩写后的内容"}}

要点：
{text}"""
    raw = await chat(prompt, system="你是内容扩写助手，只输出 JSON。", json_mode=True, temperature=0.5)
    data = _safe_json(raw, {"expanded": text})
    return {"expanded": data.get("expanded") or text}


# ---------------------------------------------------------------------
# 阶段二：办公效率类工具
# ---------------------------------------------------------------------

@register(
    name="meeting_notes",
    description="会议纪要结构化：从聊天记录/会议转录提取待办、决策、风险、责任人",
    input_schema={"text": "string"},
    output_schema={"todos": "array", "decisions": "array", "risks": "array", "owners": "array"},
)
async def meeting_notes(inputs: dict) -> dict:
    text = _tool_text(inputs, "text")
    if not text:
        return {"todos": [], "decisions": [], "risks": [], "owners": []}
    prompt = f"""你是会议纪要助手。从下面的会议记录中提取结构化信息。
- todos: [{{"task":"任务","owner":"责任人","deadline":"截止时间","priority":"high|medium|low"}}]
- decisions: [{{"decision":"决策内容","owner":"决策人"}}]
- risks: [{{"risk":"风险描述","level":"high|medium|low"}}]
- owners: ["姓名1","姓名2"]（去重）
无法确定的字段留空字符串。只输出 JSON:
{{"todos":[],"decisions":[],"risks":[],"owners":[]}}

会议记录：
{text}"""
    raw = await chat(prompt, system="你是会议纪要助手，只输出 JSON。", json_mode=True, temperature=0.1)
    data = _safe_json(raw, {"todos": [], "decisions": [], "risks": [], "owners": []})
    return {
        "todos": data.get("todos") or [],
        "decisions": data.get("decisions") or [],
        "risks": data.get("risks") or [],
        "owners": data.get("owners") or [],
    }


@register(
    name="task_extractor",
    description="待办提取器：从任意文本提取带优先级的任务清单",
    input_schema={"text": "string"},
    output_schema={"tasks": "array", "count": "number"},
)
async def task_extractor(inputs: dict) -> dict:
    text = _tool_text(inputs, "text", "todos")
    if not text:
        return {"tasks": [], "count": 0}
    prompt = f"""你是任务提取助手。从下面文本中提取可执行任务。
每项格式: {{"task":"任务描述","priority":"high|medium|low","due":"截止时间或空"}}
无法确定字段留空。只输出 JSON: {{"tasks":[]}}

文本：
{text}"""
    raw = await chat(prompt, system="你是任务提取助手，只输出 JSON。", json_mode=True, temperature=0.1)
    data = _safe_json(raw, {"tasks": []})
    tasks = data.get("tasks") or []
    return {"tasks": tasks, "count": len(tasks)}


@register(
    name="email_compose",
    description="智能邮件撰写：根据要点生成完整邮件（正式/简洁/委婉）",
    input_schema={"points": "string", "tone": "string 可选，默认正式", "recipient": "string 可选"},
    output_schema={"subject": "string", "body": "string"},
)
async def email_compose(inputs: dict) -> dict:
    points = inputs.get("points") or ""
    # 工作流场景：若上游是 meeting_notes，自动把 todos 拼成要点
    if not points and inputs.get("todos"):
        points = "\n".join(
            f"- {t.get('task', '')}（负责人:{t.get('owner', '')} 截止:{t.get('deadline', '')}）"
            for t in inputs["todos"] if isinstance(t, dict)
        )
    if not points:
        points = _tool_text(inputs, "text", "summary")
    if not points:
        return {"subject": "", "body": ""}
    tone = inputs.get("tone") or "正式"
    recipient = inputs.get("recipient") or ""
    prompt = f"""你是商务邮件撰写助手。请根据要点写一封「{tone}」语气的邮件。
收件人: {recipient or '（未指定）'}
要求：主题简洁明确；正文结构完整（称呼/正文/结尾）；不编造事实。
只输出 JSON: {{"subject":"邮件主题","body":"邮件正文"}}

要点：
{points}"""
    raw = await chat(prompt, system="你是邮件撰写助手，只输出 JSON。", json_mode=True, temperature=0.3)
    data = _safe_json(raw, {"subject": "", "body": ""})
    return {"subject": data.get("subject") or "", "body": data.get("body") or ""}


@register(
    name="slide_outline",
    description="PPT大纲生成：把文档/文本转成每页标题+要点的PPT大纲",
    input_schema={"text": "string", "pages": "number 可选，默认5"},
    output_schema={"slides": "array", "total_pages": "number"},
)
async def slide_outline(inputs: dict) -> dict:
    text = _tool_text(inputs, "text", limit=6000)
    if not text:
        return {"slides": [], "total_pages": 0}
    try:
        pages = max(1, min(20, int(inputs.get("pages", 5))))
    except (TypeError, ValueError):
        pages = 5
    prompt = f"""你是演示文稿设计专家。把下面的内容组织成 {pages} 页 PPT 大纲。
每页格式: {{"title":"页面标题","bullets":["要点1","要点2","要点3"]}}
要求：每页 3-5 个要点；逻辑递进；基于原文不编造。
只输出 JSON: {{"slides":[]}}

内容：
{text}"""
    raw = await chat(prompt, system="你是PPT大纲助手，只输出 JSON。", json_mode=True, temperature=0.3)
    data = _safe_json(raw, {"slides": []})
    slides = data.get("slides") or []
    return {"slides": slides, "total_pages": len(slides)}


# ---------------------------------------------------------------------
# 阶段三：学习/知识类工具
# ---------------------------------------------------------------------

@register(
    name="feynman_explain",
    description="费曼讲解器：用大白话+比喻解释复杂概念，可指定受众",
    input_schema={"concept": "string", "audience": "string 可选，默认外行", "text": "string 可选 参考材料"},
    output_schema={"explanation": "string", "analogy": "string", "key_points": "array"},
)
async def feynman_explain(inputs: dict) -> dict:
    # concept 取原始问题，不受 input_from（用于指定参考材料来源）影响
    concept = (inputs.get("concept") or inputs.get("question")
               or str(inputs.get("text") or "")[:200])
    if not concept:
        return {"explanation": "", "analogy": "", "key_points": []}
    material = _tool_text(inputs, "chunks", "text", limit=6000)
    material_hint = f"\n参考材料：\n{material}" if material else ""
    audience = inputs.get("audience") or "外行"
    prompt = f"""你是费曼讲解大师。请用「{audience}」能听懂的方式解释概念「{concept}」。
要求：
1. 用一个生活中的比喻贯穿始终。
2. 语言口语化，避免术语堆砌；必要术语要解释。
3. 给出 3-5 个关键点。{material_hint}
只输出 JSON: {{"explanation":"通俗解释","analogy":"核心比喻","key_points":["要点1","要点2"]}}"""
    raw = await chat(prompt, system="你是讲解助手，只输出 JSON。", json_mode=True, temperature=0.5)
    data = _safe_json(raw, {"explanation": "", "analogy": "", "key_points": []})
    return {
        "explanation": data.get("explanation") or "",
        "analogy": data.get("analogy") or "",
        "key_points": data.get("key_points") or [],
    }


@register(
    name="mindmap_outline",
    description="思维导图大纲：把文本转成Markdown层级大纲",
    input_schema={"text": "string", "max_depth": "number 可选，默认3"},
    output_schema={"outline": "string"},
)
async def mindmap_outline(inputs: dict) -> dict:
    text = _tool_text(inputs, "text", limit=6000)
    if not text:
        return {"outline": ""}
    try:
        depth = max(1, min(5, int(inputs.get("max_depth", 3))))
    except (TypeError, ValueError):
        depth = 3
    prompt = f"""你是结构化专家。把下面的文本组织成 Markdown 层级大纲（思维导图结构）。
要求：最多 {depth} 层；用 "- " 表示层级，每级缩进2个空格；覆盖主要内容。
只输出 JSON: {{"outline":"- 主题\\n  - 分支1\\n    - 子项"}}

文本：
{text}"""
    raw = await chat(prompt, system="你是大纲生成助手，只输出 JSON。", json_mode=True, temperature=0.3)
    data = _safe_json(raw, {"outline": ""})
    return {"outline": data.get("outline") or ""}


@register(
    name="generate_quiz",
    description="智能出题器：根据文本/检索结果生成选择题（含答案与解析）",
    input_schema={"text": "string", "count": "number 可选，默认5", "difficulty": "string easy|medium|hard"},
    output_schema={"questions": "array", "count": "number"},
)
async def generate_quiz(inputs: dict) -> dict:
    text = _tool_text(inputs, "text", limit=6000)
    if not text:
        return {"questions": [], "count": 0}
    try:
        count = max(1, min(20, int(inputs.get("count", 5))))
    except (TypeError, ValueError):
        count = 5
    difficulty = inputs.get("difficulty") or "medium"
    prompt = f"""你是出题老师。根据下面材料出 {count} 道 {difficulty} 难度单选题。
每题格式: {{"q":"题干","options":["A.选项1","B.选项2","C.选项3","D.选项4"],"answer":"A","explanation":"解析"}}
要求：答案唯一且在选项中；解析引用材料内容；不超出材料范围。
只输出 JSON: {{"questions":[]}}

材料：
{text}"""
    raw = await chat(prompt, system="你是出题助手，只输出 JSON。", json_mode=True, temperature=0.3)
    data = _safe_json(raw, {"questions": []})
    questions = data.get("questions") or []
    return {"questions": questions, "count": len(questions)}


@register(
    name="flashcards",
    description="记忆卡片生成：把知识转成Anki格式Q/A卡片",
    input_schema={"text": "string", "count": "number 可选，默认10"},
    output_schema={"cards": "array", "count": "number"},
)
async def flashcards(inputs: dict) -> dict:
    text = _tool_text(inputs, "text", limit=6000)
    if not text:
        return {"cards": [], "count": 0}
    try:
        count = max(1, min(30, int(inputs.get("count", 10))))
    except (TypeError, ValueError):
        count = 10
    prompt = f"""你是记忆卡片专家。根据下面材料制作 {count} 张 Anki 记忆卡片。
每张格式: {{"front":"问题/提示","back":"答案/解释","tags":["标签1"]}}
要求：一卡一知识点；front 简洁明确；back 准确完整；不编造材料外内容。
只输出 JSON: {{"cards":[]}}

材料：
{text}"""
    raw = await chat(prompt, system="你是记忆卡片助手，只输出 JSON。", json_mode=True, temperature=0.3)
    data = _safe_json(raw, {"cards": []})
    cards = data.get("cards") or []
    return {"cards": cards, "count": len(cards)}


# ---------------------------------------------------------------------
# 阶段四：系统增强类工具（元工具）
# ---------------------------------------------------------------------

@register(
    name="prompt_doctor",
    description="Prompt医生：诊断并优化用户的prompt（清晰性、约束、格式）",
    input_schema={"prompt": "string", "goal": "string 可选 期望达成目标"},
    output_schema={"diagnosis": "string", "optimized": "string", "suggestions": "array"},
)
async def prompt_doctor(inputs: dict) -> dict:
    prompt_text = inputs.get("prompt") or _tool_text(inputs, "text", limit=4000)
    if not prompt_text:
        return {"diagnosis": "", "optimized": "", "suggestions": []}
    goal = inputs.get("goal") or ""
    goal_hint = f"\n用户期望目标：{goal}" if goal else ""
    review_prompt = f"""你是提示工程专家。请诊断并优化下面的 prompt。
诊断维度：角色设定、任务清晰度、输出格式约束、避免歧义、长度控制。{goal_hint}
只输出 JSON:
{{"diagnosis":"问题诊断","optimized":"优化后的prompt","suggestions":["建议1","建议2"]}}

待诊断的 prompt：
{prompt_text}"""
    raw = await chat(review_prompt, system="你是提示工程专家，只输出 JSON。", json_mode=True, temperature=0.2)
    data = _safe_json(raw, {"diagnosis": "", "optimized": prompt_text, "suggestions": []})
    return {
        "diagnosis": data.get("diagnosis") or "",
        "optimized": data.get("optimized") or prompt_text,
        "suggestions": data.get("suggestions") or [],
    }


@register(
    name="tool_matchmaker",
    description="工具匹配器：用自然语言描述需求→推荐工具组合",
    input_schema={"requirement": "string"},
    output_schema={"tools": "array", "reason": "string", "suggested_workflow": "string"},
)
async def tool_matchmaker(inputs: dict) -> dict:
    requirement = inputs.get("requirement") or _tool_text(inputs, "text", limit=2000)
    if not requirement:
        return {"tools": [], "reason": "", "suggested_workflow": ""}
    catalog = "\n".join(f"- {t['name']}: {t['description']}" for t in list_tools())
    prompt = f"""你是工具编排顾问。根据用户需求，从下面的工具清单中推荐合适的工具组合（按顺序）。
工具清单：
{catalog}

用户需求：{requirement}

只输出 JSON:
{{"tools":["工具名1","工具名2"],"reason":"推荐理由","suggested_workflow":"建议的工作流名"}}
注意：tools 中的名字必须来自上面的清单，不要发明。"""
    raw = await chat(prompt, system="你是工具推荐助手，只输出 JSON。", json_mode=True, temperature=0.2)
    data = _safe_json(raw, {"tools": [], "reason": "", "suggested_workflow": ""})
    valid = set(TOOLS.keys())
    tools = [t for t in (data.get("tools") or []) if t in valid]
    return {
        "tools": tools,
        "reason": data.get("reason") or "",
        "suggested_workflow": data.get("suggested_workflow") or "",
    }


@register(
    name="workflow_advisor",
    description="工作流诊断师：读取指定工作流的YAML并给出优化建议",
    input_schema={"name": "string"},
    output_schema={"current": "string", "issues": "array", "suggestions": "array"},
)
async def workflow_advisor(inputs: dict) -> dict:
    from app.engine import load_workflow_raw  # 延迟导入，避免与 engine 循环依赖

    name = inputs.get("name") or inputs.get("workflow") or _tool_text(inputs, "text", limit=100)
    if not name:
        return {"current": "", "issues": [], "suggestions": []}
    try:
        current = load_workflow_raw(name)
    except (FileNotFoundError, ValueError) as e:
        return {"current": "", "issues": [f"无法加载工作流: {e}"], "suggestions": []}
    prompt = f"""你是工作流架构师。请审查下面的 YAML 工作流定义并给出优化建议。
审查维度：步骤顺序、条件分支有效性、with 参数使用、冗余步骤、潜在错误。
只输出 JSON:
{{"issues":["发现的问题1"],"suggestions":["优化建议1"]}}

工作流 {name} 的 YAML：
{current}"""
    raw = await chat(prompt, system="你是工作流诊断助手，只输出 JSON。", json_mode=True, temperature=0.2)
    data = _safe_json(raw, {"issues": [], "suggestions": []})
    return {
        "current": current,
        "issues": data.get("issues") or [],
        "suggestions": data.get("suggestions") or [],
    }


@register(
    name="result_critic",
    description="结果评审员：对工作流输出打分并给出改进建议（可作质量关卡）",
    input_schema={"content": "string", "criteria": "string 可选 评判标准"},
    output_schema={"score": "number", "strengths": "array", "weaknesses": "array", "suggestions": "array"},
)
async def result_critic(inputs: dict) -> dict:
    content = _tool_text(inputs, "content", limit=6000)
    if not content:
        return {"score": 0, "strengths": [], "weaknesses": [], "suggestions": []}
    criteria = inputs.get("criteria") or "准确性、完整性、表达清晰度"
    prompt = f"""你是质量评审专家。请按以下标准评审下面的内容并打分（0-10分）。
评判标准：{criteria}
只输出 JSON:
{{"score":7.5,"strengths":["优点1"],"weaknesses":["不足1"],"suggestions":["改进建议1"]}}

待评审内容：
{content}"""
    raw = await chat(prompt, system="你是质量评审助手，只输出 JSON。", json_mode=True, temperature=0.2)
    data = _safe_json(raw, {"score": 0, "strengths": [], "weaknesses": [], "suggestions": []})
    try:
        score = max(0.0, min(10.0, float(data.get("score", 0))))
    except (TypeError, ValueError):
        score = 0.0
    return {
        "score": score,
        "strengths": data.get("strengths") or [],
        "weaknesses": data.get("weaknesses") or [],
        "suggestions": data.get("suggestions") or [],
    }
