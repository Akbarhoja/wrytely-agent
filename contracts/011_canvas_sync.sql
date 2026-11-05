ALTER TABLE wrytely_agent.source_connections
  ADD COLUMN scope_revision bigint NOT NULL DEFAULT 0 CHECK (scope_revision>=0),
  ADD COLUMN scope_mode text NOT NULL DEFAULT 'explicit_set'
    CHECK (scope_mode IN ('explicit_set','all_active')),
  ADD COLUMN selected_course_ids jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN resource_kinds jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN discovery_coverage text NOT NULL DEFAULT 'unknown'
    CHECK (discovery_coverage IN ('unknown','complete','partial','restricted','unsupported')),
  ADD COLUMN discovery_attempt_at timestamptz,
  ADD COLUMN discovery_complete_at timestamptz,
  ADD COLUMN scan_sequence bigint NOT NULL DEFAULT 0;

CREATE TABLE wrytely_agent.canvas_scans (
  id uuid PRIMARY KEY,
  connection_id uuid NOT NULL REFERENCES wrytely_agent.source_connections(id),
  generation bigint NOT NULL,
  scope_revision bigint NOT NULL,
  sequence bigint NOT NULL,
  begin_key text NOT NULL,
  begin_digest text NOT NULL,
  state text NOT NULL DEFAULT 'active' CHECK (state IN ('active','finished','expired','aborted')),
  reason text,
  lease_token uuid NOT NULL,
  lease_expires_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL DEFAULT clock_timestamp()+interval '24 hours',
  started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  checkpoint jsonb NOT NULL,
  UNIQUE(connection_id,begin_key),
  UNIQUE(connection_id,sequence)
);
CREATE UNIQUE INDEX canvas_one_active_scan ON wrytely_agent.canvas_scans(connection_id)
  WHERE state='active';

CREATE TABLE wrytely_agent.canvas_catalog (
  connection_id uuid NOT NULL REFERENCES wrytely_agent.source_connections(id),
  generation bigint NOT NULL,
  course_id text NOT NULL,
  payload jsonb NOT NULL,
  content_digest text NOT NULL,
  observed_at timestamptz NOT NULL,
  missing_pending_confirmation boolean NOT NULL DEFAULT false,
  PRIMARY KEY(connection_id,generation,course_id)
);
CREATE TABLE wrytely_agent.canvas_scan_courses (
  scan_id uuid NOT NULL REFERENCES wrytely_agent.canvas_scans(id),
  course_id text NOT NULL,
  content_digest text NOT NULL,
  PRIMARY KEY(scan_id,course_id)
);
CREATE TABLE wrytely_agent.canvas_resources (
  scan_id uuid NOT NULL REFERENCES wrytely_agent.canvas_scans(id),
  resource_key text NOT NULL,
  coverage text NOT NULL DEFAULT 'open'
    CHECK (coverage IN ('open','complete','partial','restricted','unsupported','aborted')),
  reason text,
  seen_count integer NOT NULL DEFAULT 0,
  page_count integer NOT NULL DEFAULT 0,
  last_page_coverage text,
  PRIMARY KEY(scan_id,resource_key)
);
CREATE TABLE wrytely_agent.canvas_sync_receipts (
  scan_id uuid NOT NULL REFERENCES wrytely_agent.canvas_scans(id),
  operation text NOT NULL CHECK (operation IN ('begin','resume','batch','resource','finish')),
  replay_key text NOT NULL,
  digest text NOT NULL,
  response jsonb NOT NULL,
  PRIMARY KEY(scan_id,operation,replay_key)
);
