CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS profiles (
 id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
 email text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workspaces (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, created_by uuid NOT NULL REFERENCES auth.users(id),
 plan text NOT NULL DEFAULT 'free', monthly_question_limit int NOT NULL DEFAULT 1000,
 storage_limit_bytes bigint NOT NULL DEFAULT 2147483648,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workspace_members (
 workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
 role text NOT NULL CHECK(role IN('owner','admin','editor','viewer')),
 status text NOT NULL DEFAULT 'active' CHECK(status IN('active','inactive')),
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(workspace_id,user_id)
);
CREATE TABLE IF NOT EXISTS knowledge_bases (
 id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 name text NOT NULL, description text, created_by uuid NOT NULL REFERENCES auth.users(id),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS documents (
 id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 knowledge_base_id uuid NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
 name text NOT NULL, created_by uuid NOT NULL REFERENCES auth.users(id),
 created_at timestamptz NOT NULL DEFAULT now(), archived_at timestamptz
);
CREATE TABLE IF NOT EXISTS document_versions (
 id uuid PRIMARY KEY, document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE, version_no int NOT NULL,
 storage_path text NOT NULL, sha256 text NOT NULL, mime_type text, file_size bigint NOT NULL,
 status text NOT NULL DEFAULT 'queued', parser_version text NOT NULL DEFAULT 'v2', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(document_id,version_no)
);
CREATE TABLE IF NOT EXISTS document_pages (
 id uuid PRIMARY KEY, document_version_id uuid NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 page_number int, section_title text, raw_text text NOT NULL, cleaned_text text NOT NULL,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS chunks (
 id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 document_version_id uuid NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 page_id uuid REFERENCES document_pages(id) ON DELETE CASCADE,
 chunk_index int NOT NULL, content text NOT NULL, token_count int,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chunk_embeddings (
 id uuid PRIMARY KEY, chunk_id uuid NOT NULL UNIQUE REFERENCES chunks(id) ON DELETE CASCADE,
 provider text NOT NULL, model text NOT NULL, dimension int NOT NULL, embedding_version int NOT NULL,
 embedding vector(768) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chunks_workspace_idx ON chunks(workspace_id);
CREATE INDEX IF NOT EXISTS documents_workspace_idx ON documents(workspace_id,knowledge_base_id) WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS versions_document_idx ON document_versions(document_id,version_no DESC);
CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin(to_tsvector('simple',content));
CREATE INDEX IF NOT EXISTS chunk_embeddings_hnsw_idx ON chunk_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS document_jobs (
 id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 document_version_id uuid NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 job_type text NOT NULL, status text NOT NULL, progress int NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
 attempt int NOT NULL DEFAULT 0, max_attempts int NOT NULL DEFAULT 3, error_message text,
 started_at timestamptz, finished_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chat_sessions (
 id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES auth.users(id), title text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chat_session_sources (
 id uuid PRIMARY KEY, session_id uuid NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
 source_type text NOT NULL CHECK(source_type IN('knowledge_base','document')), source_id uuid NOT NULL,
 UNIQUE(session_id,source_type,source_id)
);
CREATE TABLE IF NOT EXISTS messages (
 id uuid PRIMARY KEY, session_id uuid NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES auth.users(id), role text NOT NULL CHECK(role IN('user','assistant')),
 content text NOT NULL, status text NOT NULL DEFAULT 'completed' CHECK(status IN('generating','completed','failed','cancelled')),
 created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS message_citations (
 id uuid PRIMARY KEY, message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
 chunk_id uuid NOT NULL REFERENCES chunks(id) ON DELETE CASCADE, citation_order int NOT NULL,
 UNIQUE(message_id,citation_order)
);
CREATE TABLE IF NOT EXISTS api_credentials (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 provider text NOT NULL, encrypted_secret text NOT NULL, key_hint text, created_by uuid NOT NULL REFERENCES auth.users(id),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(workspace_id,provider)
);
CREATE TABLE IF NOT EXISTS usage_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 user_id uuid REFERENCES auth.users(id), operation text NOT NULL, provider text, model text,
 input_tokens bigint DEFAULT 0, output_tokens bigint DEFAULT 0, storage_bytes bigint DEFAULT 0,
 estimated_cost numeric(14,6) DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS usage_workspace_month_idx ON usage_events(workspace_id,created_at DESC);
CREATE TABLE IF NOT EXISTS audit_logs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), workspace_id uuid REFERENCES workspaces(id) ON DELETE SET NULL,
 actor_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL, action text NOT NULL, resource_type text, resource_id uuid,
 request_id text, ip inet, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_workspace_created_idx ON audit_logs(workspace_id,created_at DESC);

CREATE OR REPLACE FUNCTION is_workspace_member(w uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public AS $$
 SELECT EXISTS(SELECT 1 FROM workspace_members wm WHERE wm.workspace_id=w AND wm.user_id=auth.uid() AND wm.status='active');
$$;

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_bases ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunk_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_session_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS profiles_self ON profiles;
CREATE POLICY profiles_self ON profiles FOR SELECT USING(id=auth.uid());
DROP POLICY IF EXISTS workspaces_member ON workspaces;
CREATE POLICY workspaces_member ON workspaces FOR SELECT USING(is_workspace_member(id));
DROP POLICY IF EXISTS workspace_members_member ON workspace_members;
CREATE POLICY workspace_members_member ON workspace_members FOR SELECT USING(is_workspace_member(workspace_id));
DROP POLICY IF EXISTS knowledge_bases_member ON knowledge_bases;
CREATE POLICY knowledge_bases_member ON knowledge_bases FOR SELECT USING(is_workspace_member(workspace_id));
DROP POLICY IF EXISTS documents_member ON documents;
CREATE POLICY documents_member ON documents FOR SELECT USING(is_workspace_member(workspace_id));
DROP POLICY IF EXISTS versions_member ON document_versions;
CREATE POLICY versions_member ON document_versions FOR SELECT USING(EXISTS(SELECT 1 FROM documents d WHERE d.id=document_versions.document_id AND is_workspace_member(d.workspace_id)));
DROP POLICY IF EXISTS pages_member ON document_pages;
CREATE POLICY pages_member ON document_pages FOR SELECT USING(EXISTS(SELECT 1 FROM document_versions v JOIN documents d ON d.id=v.document_id WHERE v.id=document_pages.document_version_id AND is_workspace_member(d.workspace_id)));
DROP POLICY IF EXISTS chunks_member ON chunks;
CREATE POLICY chunks_member ON chunks FOR SELECT USING(is_workspace_member(workspace_id));
DROP POLICY IF EXISTS embeddings_member ON chunk_embeddings;
CREATE POLICY embeddings_member ON chunk_embeddings FOR SELECT USING(EXISTS(SELECT 1 FROM chunks c WHERE c.id=chunk_embeddings.chunk_id AND is_workspace_member(c.workspace_id)));
DROP POLICY IF EXISTS jobs_member ON document_jobs;
CREATE POLICY jobs_member ON document_jobs FOR SELECT USING(is_workspace_member(workspace_id));
DROP POLICY IF EXISTS chat_sessions_owner ON chat_sessions;
CREATE POLICY chat_sessions_owner ON chat_sessions FOR SELECT USING(user_id=auth.uid() AND is_workspace_member(workspace_id));
DROP POLICY IF EXISTS chat_sources_owner ON chat_session_sources;
CREATE POLICY chat_sources_owner ON chat_session_sources FOR SELECT USING(EXISTS(SELECT 1 FROM chat_sessions s WHERE s.id=chat_session_sources.session_id AND s.user_id=auth.uid() AND is_workspace_member(s.workspace_id)));
DROP POLICY IF EXISTS messages_owner ON messages;
CREATE POLICY messages_owner ON messages FOR SELECT USING(user_id=auth.uid());
DROP POLICY IF EXISTS citations_owner ON message_citations;
CREATE POLICY citations_owner ON message_citations FOR SELECT USING(EXISTS(SELECT 1 FROM messages m WHERE m.id=message_citations.message_id AND m.user_id=auth.uid()));
DROP POLICY IF EXISTS credentials_admin_read ON api_credentials;
CREATE POLICY credentials_admin_read ON api_credentials FOR SELECT USING(false);
DROP POLICY IF EXISTS usage_member ON usage_events;
CREATE POLICY usage_member ON usage_events FOR SELECT USING(is_workspace_member(workspace_id));
DROP POLICY IF EXISTS audit_member ON audit_logs;
CREATE POLICY audit_member ON audit_logs FOR SELECT USING(workspace_id IS NOT NULL AND is_workspace_member(workspace_id));

-- Application writes use a trusted server-side database connection. Never expose that credential to browsers.
