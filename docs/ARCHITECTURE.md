# DocuQuery Architecture

## Request plane

Browser → FastAPI → workspace authorization → PostgreSQL/pgvector, Redis and Storage.

Production browser authentication is Supabase Auth. The browser sends only a bearer access token to FastAPI. FastAPI verifies it against the Supabase JWKS endpoint. Local development can use a fixed development principal so the full product can be exercised without a hosted auth service.

## Ingestion plane

Upload → validation → optional malware scan → quota check → storage → document/version/job rows → RQ → worker → parser/OCR → pages → chunks → embeddings → HNSW index → READY.

The original object is kept separately from extracted pages, retrieval chunks and embeddings. This permits later parser/chunker/embedding migrations without asking users to re-upload the original file.

## Retrieval plane

Question → query embedding → vector similarity + PostgreSQL `simple` FTS → score fusion → reranking → context builder → grounded generation → server-managed citations.

Document text is explicitly treated as untrusted evidence. Instructions inside retrieved documents are not application/system instructions.

## Tenant boundary

Every workspace-owned resource is scoped by `workspace_id` directly or through an owning relation. FastAPI checks workspace membership and role before operations. Supabase RLS is enabled as defense-in-depth for client-side database access.

## AI provider boundary

`packages/ai/factory.py` chooses a development mock provider or Gemini. The application does not require AI-specific code in document/chat routers beyond the provider interface. Workspace BYOK keys are encrypted before persistence.

## Storage boundary

`packages/storage/factory.py` chooses local filesystem or private Supabase Storage. Storage paths are generated server-side from workspace/document/version IDs and local paths are traversal-checked.
