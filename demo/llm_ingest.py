"""用真 LLM 提炼 L1，并按 quote 回到原文定位。

与 tb.extract()（规则版）的差别，正是这两天争论的那几条：
  · 摘要必须「结论——因为依据」
  · 链首要交代前因（context）
  · 一条决策不被拆成几条
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import api_client  # noqa: E402
import tb  # noqa: E402

SYSTEM = "你是记忆提炼器。只输出 JSON，不要解释。"

PROMPT = """下面是一段项目记录。把它提炼成若干条"值得记住"的记忆。

要求：
1. 只提取决策、偏好、结论、任务、知识；不要复述会议过程，不要提取寒暄和过渡句。
2. l1_summary 必须写成「做了什么——因为什么」。依据里只保留能改变判断的部分（价格、次数、成本、时间），
   包装、口感、天气这类细节不要进摘要。
3. 如果这条是该话题下的第一条记忆，用 context 写一句"为什么会有这件事"（缘起/计划/约束）；否则 context 留空字符串。
4. category ∈ decision / task / knowledge / preference。
5. quote 必须是原文里**连续出现**的一句（用于回到原文定位），不要改写。
6. 不要编造原文没有的信息。

输出格式：
{{"items":[{{"category":"decision","l1_summary":"…——因为…","context":"","quote":"…","keywords":["…","…"],"confidence":"high","importance":0.8}}]}}

原文：
------
{chunk}
------
"""


def _parse(content: str) -> list[dict]:
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
    i, j = content.find("{"), content.rfind("}")
    if i >= 0 and j > i:
        content = content[i:j + 1]
    data = json.loads(content)
    return data.get("items", [])


def extract_llm(text: str, chunk: str, *, chunk_start: int = 0) -> tuple[list[dict], dict]:
    raw = api_client.chat(PROMPT.format(chunk=chunk), system=SYSTEM)
    items = _parse(raw)
    out = []
    for it in items:
        quote = (it.get("quote") or "").strip()
        pos = text.find(quote, chunk_start) if quote else -1
        if pos < 0:                                  # quote 找不到就用整块起点兜底
            pos, length = chunk_start, len(chunk)
        else:
            length = len(quote)
        topic = tb.find_topic(text, pos)
        # 关键词首词必须是话题：配对/挂靠都靠它判断"是不是同一件事"，
        # 规则版一直这么做，LLM 版漏了会直接导致冲突检不出来
        kws = [topic] + [k for k in (it.get("keywords") or []) if k and k != topic]
        out.append({
            "category": it.get("category", "knowledge"),
            "l1_summary": (it.get("l1_summary") or "").strip(),
            "context": (it.get("context") or "").strip(),
            "keywords": " ".join(kws),
            "offset": pos,
            "length": length,
            "confidence": it.get("confidence", "medium"),
            "importance": float(it.get("importance") or 0.5),
            "topic": topic,
            "quote_found": pos != chunk_start or bool(quote and text.find(quote, chunk_start) >= 0),
        })
    return out, {"items": len(out), "raw_len": len(raw)}


def ingest_llm(conn, text: str, *, title: str = "", user_id: str = "local") -> dict:
    doc_id = tb.put_document(conn, text, user_id=user_id, title=title, source="import")
    entries = []
    for start, end in tb.split_semantic(text):
        items, meta = extract_llm(text, text[start:end], chunk_start=start)
        for it in items:
            eid = tb.insert_memory(
                conn, user_id=user_id, summary=it["l1_summary"],
                doc_id=doc_id, offset=it["offset"], length=it["length"],
                category=it["category"], confidence=it["confidence"],
                keywords=it["keywords"], context=it["context"],
                importance=it["importance"])
            entries.append({**it, "entry_id": eid})
    return {"doc_id": doc_id, "entries": entries}


JUDGE_PROMPT = """判断两条记忆的关系。只输出 JSON。

旧：{old}
新：{new}

关系取值：
- override：新的一条明确改变了旧的那条决定
- duplicate：说的是同一件事，新的一条没有增加信息
- complement：新增了信息，但不推翻旧结论
- unrelated：不是同一件事

输出：{{"relation":"override","confidence":0.85,"reason":"一句话理由（不超过 30 字）"}}
"""


def judge_llm(new_sum: str, new_kw: str, old_sum: str, old_kw: str) -> tuple[str, float, str]:
    """让模型判关系。与规则版同签名，可直接替换。"""
    raw = api_client.chat(JUDGE_PROMPT.format(old=old_sum, new=new_sum),
                          system="你是记忆冲突判定器，只输出 JSON。", max_tokens=200)
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.S)
    i, j = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[i:j + 1]) if i >= 0 else {}
    rel = data.get("relation", "unrelated")
    if rel not in ("override", "duplicate", "complement", "unrelated"):
        rel = "unrelated"
    return rel, float(data.get("confidence") or 0.0), str(data.get("reason") or "")[:60]
