# DocuQuery Local AI Modes

DocuQuery 1.1 decouples semantic retrieval from Gemini. The core document system can now run without any generative LLM.

## Recommended default: SEARCH_ONLY

```env
APP_MODE=search_only
EMBEDDING_PROVIDER=local
CHAT_PROVIDER=disabled
LOCAL_EMBED_MODEL=intfloat/multilingual-e5-base
LOCAL_EMBED_DEVICE=cpu
EMBEDDING_DIMENSION=768
```

Flow:

```text
Upload -> Redis/RQ -> parse -> chunk -> local E5 embeddings -> pgvector
Question -> local E5 query embedding -> hybrid retrieval -> evidence snippets + DB citations
```

No Gemini/OpenAI/Claude/local generative LLM call is made in this mode.

## Optional local LLM mode

Run an OpenAI-compatible local endpoint such as Ollama, llama.cpp or vLLM and configure:

```env
APP_MODE=local_llm
EMBEDDING_PROVIDER=local
CHAT_PROVIDER=local
LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
LOCAL_LLM_API_KEY=ollama
LOCAL_LLM_MODEL=qwen2.5:7b
```

The local LLM receives only the retrieved evidence context and question. Citations remain server-generated from database metadata.

## Optional Gemini chat mode

```env
APP_MODE=cloud_llm
EMBEDDING_PROVIDER=local
CHAT_PROVIDER=gemini
```

A workspace Gemini BYOK credential or managed Gemini key is required only for answer generation. Document ingestion and semantic retrieval continue using local embeddings.

## Optional Gemini embedding mode

```env
EMBEDDING_PROVIDER=gemini
```

This preserves cloud embedding support but is no longer the default.

## Critical: embedding provider migrations require reindexing

Gemini vectors and E5 vectors must never be compared in the same semantic search even if both are 768-dimensional. They are different vector spaces.

Retrieval now filters `chunk_embeddings` by active `provider` and `model`.

After switching from Gemini embeddings to local embeddings, reindex existing documents once:

```http
POST /api/maintenance/documents/{document_id}/reindex
Authorization: Bearer <token>
```

Allowed roles: owner, admin, editor.

The worker deletes and regenerates derived pages/chunks/embeddings for the current document version and stores the active provider/model in `chunk_embeddings`.

## Docker model cache

`docker-compose.yml` includes a shared `model_cache` volume mounted into both the API and RQ worker. The first local embedding request downloads the model; later requests reuse the cache.

For air-gapped environments, pre-download the model into an internal image/cache and point `LOCAL_EMBED_MODEL` at that local model path.

## Production principle

Core DocuQuery features do not depend on a generative LLM:

- Auth
- workspace/RBAC
- Supabase Storage
- parsing
- chunking
- local embeddings
- pgvector
- hybrid retrieval
- evidence snippets
- citations
- chat/session history
- audit/usage

Gemini/local LLM generation is optional.
