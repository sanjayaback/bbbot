# DocuQuery Production Deployment

## Target topology

- GitHub: source of truth
- Render Web Service: `docuquery-api`
- Render Background Worker: `docuquery-worker`
- Render Key Value: `docuquery-redis`
- Supabase: Auth, PostgreSQL + pgvector, private Storage
- Gemini: `gemini-3.6-flash` + `gemini-embedding-2`

The root `render.yaml` defines the Render topology. Secrets remain `sync: false` and must be entered in Render.

## Required production environment values

Set these on the API:

- `APP_ENV=production`
- `APP_BASE_URL=https://YOUR_API_DOMAIN`
- `CORS_ORIGINS=https://YOUR_FRONTEND_DOMAIN`
- `AUTH_MODE=supabase`
- `AI_MODE=gemini`
- `STORAGE_BACKEND=supabase`
- `DATABASE_URL` — Supabase/Supavisor connection URL using the password URL-encoded if necessary
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_JWKS_URL`
- `STORAGE_BUCKET=docuquery-documents`
- `CREDENTIAL_ENCRYPTION_KEY`

`REDIS_URL` is wired from Render Key Value by the Blueprint.

Set the same DB, Redis, Storage, encryption and AI configuration on the worker. The worker does not need browser/public configuration.

## Supabase Auth URLs

Set Supabase Authentication Site URL to the real application URL. Remove localhost redirect URLs from the production project unless deliberately required for development.

## Database schema

Apply `db/schema.sql` to the production Supabase database before opening the app to users. Confirm `vector` and `pgcrypto` extensions and all DocuQuery tables exist.

Do not use the local Docker bootstrap SQL against production; `db/local_bootstrap.sql` is only for the local development PostgreSQL container.

## Storage

Create a private bucket named `docuquery-documents` (or set `STORAGE_BUCKET` to the actual private bucket). The Supabase secret key must exist only on the API/worker, never in frontend JavaScript.

## Local release gate

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=200 api
docker compose logs --tail=200 worker
docker compose logs --tail=200 redis
python scripts/smoke_test.py http://localhost:8000
```

Then verify the full flow:

1. login
2. create workspace
3. create knowledge base
4. save Gemini key
5. upload a TXT test document
6. worker changes the document to `ready`
7. ask a known question
8. verify answer and citation
9. test an unsupported question and verify DocuQuery refuses to guess
10. repeat with PDF and DOCX

## Production smoke test

```bash
python scripts/smoke_test.py https://YOUR_API_DOMAIN
```

To verify authenticated workspace bootstrap too:

```bash
DOCUQUERY_ACCESS_TOKEN="<temporary test access token>" \
python scripts/smoke_test.py https://YOUR_API_DOMAIN
```

Never commit or paste production tokens into source control.

## Release blockers

Do not declare production ready when any of these are true:

- `/ready` is not HTTP 200
- database or Redis is unavailable
- RQ worker is not consuming `docuquery`
- document processing remains stuck in `queued`, `extracting`, `chunking`, or `embedding`
- cross-workspace resource IDs can be accessed
- Owner can be removed/demoted through normal member management
- Gemini credential is returned unencrypted
- browser produces `workspace_id=null` requests
- browser displays `[object Object]`
- citation source does not match the retrieved chunk

## GitHub Actions note

If Actions jobs show failed/cancelled while exposing zero executed steps, treat that as a GitHub Actions runner/account execution issue rather than a passing/failing application test. Resolve the Actions execution issue separately; do not claim CI passed until jobs actually run.
