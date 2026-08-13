import re


def _sentences(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    parts = re.split(r"(?<=[.!?।])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def smart_chunks(text: str, max_chars: int = 1200, overlap_chars: int = 180) -> list[str]:
    sentences = _sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    size = 0

    for sentence in sentences:
        if current and size + len(sentence) + 1 > max_chars:
            chunk = " ".join(current).strip()
            chunks.append(chunk)

            overlap: list[str] = []
            overlap_size = 0
            for old in reversed(current):
                if overlap_size + len(old) > overlap_chars:
                    break
                overlap.insert(0, old)
                overlap_size += len(old) + 1
            current = overlap
            size = sum(len(x) + 1 for x in current)

        if len(sentence) > max_chars:
            if current:
                chunks.append(" ".join(current).strip())
                current = []
                size = 0
            step = max(1, max_chars - overlap_chars)
            for i in range(0, len(sentence), step):
                chunks.append(sentence[i : i + max_chars])
        else:
            current.append(sentence)
            size += len(sentence) + 1

    if current:
        last = " ".join(current).strip()
        if not chunks or last != chunks[-1]:
            chunks.append(last)
    return chunks
