# DocuQuery 1.1 — Secure Document Intelligence

DocuQuery is a multi-tenant document intelligence platform. Users authenticate with Supabase, work inside RBAC-protected workspaces, create knowledge bases, upload PDF/DOCX/TXT documents, process them asynchronously through Redis/RQ, index them in PostgreSQL/pgvector, retrieve evidence with hybrid search, and open verifiable citations.

The core retrieval system no longer needs a generative LLM. Local multilingual embeddings are the recommended default. Gemini and local LLMs are optional answer-generation providers.

## Verified core architecture

- FastAPI API + static vanilla HTML/CSS/JS frontend
- Supabase Auth with JWT verification
- Owner/Admin/Editor/Viewer workspace RBAC
- Supabase PostgreSQL + pgvector
- Supabase Storage or local storage backend
- Redis + RQ background document ingestion
- Page-aware PDF/DOCX/TXT parsing
- Smart paragraph/sentence-aware chunking
- Local multilingual embeddings or optional Gemini embeddings
- PostgreSQL FTS + pgvector hybrid retrieval
- Non-generative evidence-search mode
- Optional local OpenAI-compatible LLM
- Optional Gemini cloud LLM
- Server-owned real citations
- Persistent chat sessions/messages
- Usage quotas, rate limiting and audit logs
- Optional OCR and ClamAV scanning

## AI provider modes

### 1. Search-only — recommended default

No generative LLM is called.

```env
APP_MODE=search_only
EMBEDDING_PROVIDER=local
CHAT_PROVIDER=disabled
LOCAL_EMBED_MODEL=intfloat/multilingual-e5-base
EMBEDDING_DIMENSION=768
```

Flow:

```text
Document -> local embedding -> pgvector
Question -> local embedding -> hybrid search -> evidence + citations
```

Use the dedicated endpoint:

```text
GET /api/search?workspace_id=<uuid>&q=<question>
```

It returns structured evidence and citations without an LLM call.

### 2. Local LLM

```env
APP_MODE=local_llm
EMBEDDING_PROVIDER=local
CHAT_PROVIDER=local
LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
LOCAL_LLM_MODEL=qwen2.5:7b
```

The local chat adapter works with OpenAI-compatible Ollama, llama.cpp and vLLM endpoints.

### 3. Gemini cloud LLM

```env
APP_MODE=cloud_llm
EMBEDDING_PROVIDER=local
CHAT_PROVIDER=gemini
```

A workspace BYOK Gemini key or managed server key can be used for answer generation while document/query embeddings remain local.

Gemini embeddings remain supported if explicitly selected:

```env
EMBEDDING_PROVIDER=gemini
```

## Important: embedding migrations

Never compare vectors from different embedding models as though they share the same semantic space.

The existing schema is `vector(768)`, so the default local model is `intfloat/multilingual-e5-base`, which keeps the existing dimension.

After changing `EMBEDDING_PROVIDER` or `LOCAL_EMBED_MODEL`, reindex existing documents:

```text
POST /api/maintenance/documents/{document_id}/reindex
```

The worker deletes derived pages/chunks for that document version and rebuilds them with the selected embedding provider/model. Retrieval filters vectors by provider/model so stale Gemini vectors are not mixed with local vectors.

## Docker Desktop

Copy the environment file:

```bash
cp .env.example .env
```

Then start:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

The API and worker share a persistent Hugging Face/Sentence Transformers model cache volume so the local embedding model is not downloaded on every container restart.

`docker-compose.yml` respects `DATABASE_URL` from `.env`. This means the same Docker stack can use either the local PostgreSQL fallback or the configured real Supabase PostgreSQL connection.

## Real Supabase configuration

```env
APP_ENV=production
AUTH_MODE=supabase
STORAGE_BACKEND=supabase
DATABASE_URL=postgresql+asyncpg://...
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=...
SUPABASE_SECRET_KEY=...
SUPABASE_JWKS_URL=https://YOUR_PROJECT.supabase.co/auth/v1/.well-known/jwks.json
STORAGE_BUCKET=documents
REDIS_URL=redis://redis:6379/0
CREDENTIAL_ENCRYPTION_KEY=...
```

Never expose `DATABASE_URL`, `SUPABASE_SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY`, Redis credentials, or customer AI keys to browser JavaScript.

## Document ingestion

```text
Upload
 -> validate type/size/signature
 -> optional ClamAV scan
 -> Supabase Storage
 -> document/version/job rows
 -> Redis queue
 -> RQ worker
 -> page-aware parse
 -> smart chunks
 -> selected embedding provider
 -> pgvector
 -> ready
```

Observed job states:

```text
queued -> extracting -> chunking -> embedding -> ready
```

Failures are persisted as `failed` with an error message rather than being left silently queued.

## Search and citations

Hybrid retrieval combines PostgreSQL full-text search with cosine vector similarity. Retrieval is always workspace-scoped and can be narrowed to knowledge bases/documents.

Citation metadata comes from database chunk/document/page records, not from an LLM. A citation can therefore open the exact supporting chunk.

## OCR

OCR is optional. Install the Python OCR dependencies and Tesseract with the required language packs, then configure:

```env
OCR_ENABLED=true
TESSERACT_CMD=
```

Text-native PDF pages use PyMuPDF. Low-text pages can fall back to OCR when enabled.

## Malware scanning

ClamAV support is already wired into uploads. Start the security profile:

```bash
docker compose --profile security up --build
```

Then configure:

```env
MALWARE_SCAN_ENABLED=true
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
```

## Health and API docs

```text
GET /health
GET /ready
/api/docs
/api/openapi.json
```

`/ready` checks critical runtime dependencies such as PostgreSQL and Redis.

## Tests

```bash
python -m pytest -q
python -m compileall -q apps packages
node --check frontend/app.js
```

Before production deployment, also run an end-to-end test:

```text
Supabase login
 -> workspace/RBAC
 -> knowledge base
 -> upload
 -> Redis
 -> RQ worker
 -> parse
 -> local embedding
 -> pgvector
 -> /api/search
 -> evidence/citation
 -> optional local/Gemini chat
```

## Security boundaries

- Authentication comes from verified Supabase JWTs.
- Every resource is workspace-scoped server-side.
- RLS remains defense-in-depth on Supabase tables.
- Provider secrets are backend-only and workspace Gemini BYOK keys are encrypted.
- Uploaded files are validated before ingestion.
- Retrieved document text is untrusted evidence, never system instructions.
- Search-only works even with no generative LLM configured.
- Invalid AI provider combinations fail at application startup instead of silently selecting another provider.
