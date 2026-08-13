# DocuQuery 1.0 — End-to-End Document Intelligence

DocuQuery is a multi-tenant document intelligence application: users authenticate, enter a workspace, create knowledge bases, upload PDF/DOCX/TXT files, process them asynchronously, retrieve evidence with hybrid vector + full-text search, and ask grounded questions with verifiable source citations.

## What is included

- FastAPI API and static SPA frontend
- Supabase Auth production mode plus a local development auth mode
- Workspace tenancy and Owner/Admin/Editor/Viewer roles
- Knowledge-base CRUD and workspace member management
- Version-aware document model and secure upload validation
- Local storage and Supabase Storage backends
- Redis + RQ durable ingestion worker with progress and retry state
- PDF/DOCX/TXT extraction and optional OCR fallback for scanned PDFs
- Optional ClamAV upload scanning hook
- Smart chunking, Gemini embeddings, pgvector HNSW and PostgreSQL FTS
- Hybrid retrieval plus a replaceable reranking stage
- Gemini managed-key or encrypted workspace BYOK credentials
- Grounded generation with document prompt-injection defenses
- SSE streaming answers, persisted messages and server-owned citations
- Clickable citation source viewer
- Monthly question quota, storage quota and per-user request rate limiting
- Usage events and workspace audit log
- Dashboard, Knowledge, Chat, Activity and Settings interfaces
- Docker Compose for PostgreSQL/pgvector, Redis, API and worker

## Fastest local end-to-end run

1. Copy the environment file:

```bash
cp .env.example .env
```

The example deliberately uses:

```text
AUTH_MODE=dev
AI_MODE=mock
STORAGE_BACKEND=local
```

This lets the complete upload → worker → indexing → chat → citation flow run without Supabase or Gemini credentials. `AI_MODE=mock` is development/test-only and must not be used as a production AI provider.

2. Start the stack:

```bash
docker compose up --build
```

3. Open:

```text
http://localhost:8000
```

4. Create a workspace → create a knowledge base → upload a PDF/DOCX/TXT → wait for `ready` → start a chat → ask a question → open a citation.

## Production Supabase setup

Create a Supabase project, then run `db/schema.sql` in the SQL editor. Do **not** run `db/local_bootstrap.sql` against Supabase; it only emulates the auth schema for local Docker.

Create a private Storage bucket named `documents` (or change `STORAGE_BUCKET`). Configure the production environment:

```text
APP_ENV=production
AUTH_MODE=supabase
STORAGE_BACKEND=supabase
SUPABASE_URL=...
SUPABASE_PUBLISHABLE_KEY=...
SUPABASE_SECRET_KEY=...
SUPABASE_JWKS_URL=.../auth/v1/.well-known/jwks.json
AI_MODE=gemini
GEMINI_API_KEY=...
CREDENTIAL_ENCRYPTION_KEY=...
```

The Supabase secret/service credential is backend-only. Never expose it in frontend JavaScript.

### Database connection

The API/worker need a trusted server-side PostgreSQL connection in `DATABASE_URL`. The API performs workspace authorization itself and RLS remains defense-in-depth for browser/client access through Supabase.

## Gemini and BYOK

There are two supported modes:

- Managed: configure `GEMINI_API_KEY` on the server.
- BYOK: workspace owner/admin enters a Gemini key in Settings. It is encrypted with Fernet before storage and only a key hint is returned.

Generate the Fernet key with:

```bash
python scripts/generate_fernet_key.py
```

Never commit that key or customer provider keys.

## OCR

Enable only when Tesseract is installed:

```bash
pip install -e '.[ocr]'
```

Install Tesseract with English and Nepali language packs, then set:

```text
OCR_ENABLED=true
```

Text-native PDF pages use PyMuPDF. Pages with very little extractable text fall back to OCR.

## Malware scanning

Start ClamAV with:

```bash
docker compose --profile security up --build
```

Then enable:

```text
MALWARE_SCAN_ENABLED=true
CLAMAV_HOST=clamav
```

Uploads are rejected when ClamAV reports malware.

## API documentation

When running:

```text
/api/docs
/api/openapi.json
```

## Tests and checks

```bash
python -m pytest -q
python -m compileall -q apps packages
node --check frontend/app.js
python scripts/smoke_test.py
```

## Security boundaries

- Browser receives only the Supabase publishable key; server secrets stay server-side.
- Every resource is workspace-scoped in backend authorization.
- RLS is enabled across user-visible tables.
- Customer Gemini keys are encrypted and never returned raw.
- File extension, MIME, magic signature, size and optional malware checks run before ingestion.
- Retrieved document content is treated as untrusted evidence, not model instructions.
- Chat quotas and rate limits reduce provider abuse.
- Audit logs record workspace-sensitive changes without storing provider secrets.

## Production deployment checklist

Before a real customer launch: use Supabase auth/storage, use Gemini rather than mock mode, enable HTTPS, set a real encryption key, use managed Redis/Postgres, configure backups/PITR, configure log/metric collection, run tenant-isolation security tests, run load tests, test restoration, and enable OCR/malware scanning if your threat model requires them.

See `docs/ARCHITECTURE.md` and `docs/BUILD_STATUS.md` for implementation details.
