CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
  id uuid PRIMARY KEY,
  email text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('request.jwt.claim.sub', true),'')::uuid;
$$;
INSERT INTO auth.users(id,email) VALUES('00000000-0000-0000-0000-000000000001','dev@docuquery.local') ON CONFLICT DO NOTHING;
