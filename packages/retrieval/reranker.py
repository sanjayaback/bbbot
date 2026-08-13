import re


def heuristic_rerank(question: str, chunks: list[dict], limit: int = 8) -> list[dict]:
    terms = {t for t in re.findall(r"[\w\u0900-\u097F]+", question.lower()) if len(t) > 2}
    for item in chunks:
        content = item.get("content", "").lower()
        lexical = sum(1 for t in terms if t in content) / max(1, len(terms))
        item["rerank_score"] = float(item.get("score", 0)) * 0.8 + lexical * 0.2
    return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:limit]
