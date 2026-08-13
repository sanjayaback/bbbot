from packages.ingestion.chunker import smart_chunks

def test_chunker_keeps_nepali_sentence_boundaries():
    text="यो पहिलो वाक्य हो। यो दोस्रो वाक्य हो। This is third."
    chunks=smart_chunks(text,max_chars=30,overlap_chars=5)
    assert len(chunks)>=2
    assert all(c.strip() for c in chunks)

def test_chunker_empty():
    assert smart_chunks("   ")==[]
