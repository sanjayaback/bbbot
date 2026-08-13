def build_context(chunks: list[dict]):
    context_parts: list[str] = []
    citations: list[dict] = []
    seen: set[tuple] = set()

    for i, chunk in enumerate(chunks, 1):
        location = (
            f"Page {chunk['page_number']}"
            if chunk.get("page_number")
            else (chunk.get("section_title") or "Section")
        )
        context_parts.append(
            f"--- SOURCE {i}: {chunk['document_name']} | {location} ---\n{chunk['content']}"
        )

        key = (
            chunk["document_id"],
            chunk.get("page_number"),
            chunk.get("section_title"),
        )
        if key not in seen:
            citations.append(
                {
                    "chunk_id": str(chunk["chunk_id"]),
                    "document_id": str(chunk["document_id"]),
                    "document": chunk["document_name"],
                    "page": chunk.get("page_number"),
                    "section": chunk.get("section_title"),
                }
            )
            seen.add(key)

    return "\n\n".join(context_parts), citations
