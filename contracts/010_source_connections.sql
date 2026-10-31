-- Canvas pairing/lifecycle only. No source ingestion, OAuth secrets or scan tables yet.
CREATE TABLE wrytely_agent.source_pairings (
  agent_id uuid PRIMARY KEY REFERENCES wrytely_agent.agents(id),
  origin text NOT NULL,
  code_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  window_started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  issued_count integer NOT NULL DEFAULT 1 CHECK (issued_count BETWEEN 1 AND 5)
);
CREATE TABLE wrytely_agent.source_pairing_rates (
  bucket_key text PRIMARY KEY,
  window_started_at timestamptz NOT NULL,
  attempts integer NOT NULL CHECK (attempts > 0)
);
CREATE TABLE wrytely_agent.source_connections (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  provider text NOT NULL DEFAULT 'canvas_extension' CHECK (provider='canvas_extension'),
  origin text NOT NULL,
  device_public_id text NOT NULL CHECK (length(device_public_id) BETWEEN 1 AND 128),
  provider_subject text CHECK (length(provider_subject) BETWEEN 1 AND 1024),
  generation bigint NOT NULL DEFAULT 1 CHECK (generation > 0),
  state text NOT NULL CHECK (state IN
    ('pending_identity','connected','reconnect_required','disconnected')),
  credential_hash text UNIQUE,
  credential_expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (agent_id,origin,device_public_id),
  UNIQUE (agent_id,id),
  CHECK (state NOT IN ('pending_identity','connected') OR credential_hash IS NOT NULL),
  CHECK (state <> 'connected' OR provider_subject IS NOT NULL)
);
