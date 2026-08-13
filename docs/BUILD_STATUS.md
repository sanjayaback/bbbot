# DocuQuery 1.0 — Build Status

## Implemented end to end

- Dev and Supabase authentication modes
- Profile bootstrap, workspace tenancy and role checks
- Knowledge-base CRUD
- Workspace member list/upsert/removal
- PDF/DOCX/TXT upload validation
- Local and Supabase Storage adapters
- Optional ClamAV scan hook
- Storage quotas and upload usage accounting
- Redis/RQ ingestion queue
- Job status/progress/retry lifecycle
- PDF page extraction, DOCX section extraction and TXT parsing
- Optional scanned-PDF OCR fallback through Tesseract
- Sentence/paragraph aware chunking
- Development mock embeddings/LLM
- Gemini embedding and generation provider
- HNSW pgvector index and language-neutral PostgreSQL FTS
- Hybrid retrieval and replaceable reranking stage
- Grounded prompt with document prompt-injection boundary
- Chat session source scoping
- SSE answer streaming
- Persisted messages and server-owned citation links
- Citation source viewer endpoint/UI
- Encrypted Gemini BYOK settings
- Question quotas and Redis rate limiting
- Usage accounting and audit trail
- Dashboard / Knowledge / Chat / Activity / Settings SPA
- API + worker + Postgres/pgvector + Redis Docker Compose topology
- Local database bootstrap that emulates the Supabase auth table only for development

## Production integrations that are environment-dependent

These features are implemented but require external services/credentials to exercise in a real deployment:

- Supabase Auth project and asymmetric JWT/JWKS configuration
- Supabase private Storage bucket
- Gemini production API credentials
- Tesseract runtime and language packs when OCR is enabled
- ClamAV runtime when malware scanning is enabled
- Production PostgreSQL/Redis, TLS, backups and monitoring

## Validation completed in the build workspace

- Python source compilation
- Frontend JavaScript syntax check with Node
- Unit test suite
- Static review of Docker Compose and SQL bootstrap wiring

The build workspace did not expose Docker/PostgreSQL daemons and did not allow package downloads, so a live `docker compose up`/database migration was not executed here. The repository is structured for that final environment smoke test on a host with Docker available.
