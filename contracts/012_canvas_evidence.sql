ALTER TABLE wrytely_agent.canvas_resources
  ADD COLUMN next_cursor text,
  ADD COLUMN incomplete_count integer NOT NULL DEFAULT 0 CHECK (incomplete_count>=0);
UPDATE wrytely_agent.canvas_resources r
  SET next_cursor=s.checkpoint->>'next_cursor'
  FROM wrytely_agent.canvas_scans s
  WHERE s.id=r.scan_id AND s.checkpoint->>'resource'=r.resource_key;

CREATE TABLE wrytely_agent.canvas_evidence_objects (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  connection_id uuid NOT NULL,
  subject_digest text NOT NULL,
  course_id text NOT NULL,
  kind text NOT NULL,
  provider_id text NOT NULL,
  source_id uuid,
  latest_observation_id uuid,
  complete_version_id uuid,
  last_observed_at timestamptz,
  last_successful_check_at timestamptz,
  missing_pending_confirmation boolean NOT NULL DEFAULT false,
  UNIQUE(agent_id,id),
  UNIQUE(connection_id,subject_digest,course_id,kind,provider_id),
  FOREIGN KEY(agent_id,connection_id) REFERENCES wrytely_agent.source_connections(agent_id,id),
  FOREIGN KEY(agent_id,source_id) REFERENCES wrytely_agent.academic_sources(agent_id,id),
  FOREIGN KEY(agent_id,complete_version_id) REFERENCES wrytely_agent.source_versions(agent_id,id)
);
CREATE TABLE wrytely_agent.canvas_evidence_observations (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  object_id uuid NOT NULL,
  scan_id uuid NOT NULL REFERENCES wrytely_agent.canvas_scans(id),
  generation bigint NOT NULL,
  resource_key text NOT NULL,
  observed_at timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  provider_updated_at timestamptz,
  reference text NOT NULL,
  coverage text NOT NULL CHECK (coverage IN ('complete','partial','restricted','unsupported')),
  content_digest text NOT NULL,
  payload jsonb NOT NULL,
  version_id uuid,
  historical boolean NOT NULL,
  UNIQUE(agent_id,id),
  FOREIGN KEY(agent_id,object_id) REFERENCES wrytely_agent.canvas_evidence_objects(agent_id,id),
  FOREIGN KEY(agent_id,version_id) REFERENCES wrytely_agent.source_versions(agent_id,id)
);
ALTER TABLE wrytely_agent.canvas_evidence_objects ADD CONSTRAINT canvas_latest_observation_owner
  FOREIGN KEY(agent_id,latest_observation_id)
  REFERENCES wrytely_agent.canvas_evidence_observations(agent_id,id);

CREATE TABLE wrytely_agent.canvas_evidence_payloads (
  agent_id uuid NOT NULL,
  version_id uuid PRIMARY KEY,
  content_digest text NOT NULL,
  payload jsonb NOT NULL,
  FOREIGN KEY(agent_id,version_id) REFERENCES wrytely_agent.source_versions(agent_id,id)
);
CREATE TABLE wrytely_agent.canvas_evidence_events (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  object_id uuid NOT NULL,
  observation_id uuid NOT NULL UNIQUE,
  kind text NOT NULL CHECK (kind IN ('source_observed','source_changed','coverage_changed')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY(agent_id,object_id) REFERENCES wrytely_agent.canvas_evidence_objects(agent_id,id),
  FOREIGN KEY(agent_id,observation_id)
    REFERENCES wrytely_agent.canvas_evidence_observations(agent_id,id)
);
CREATE TABLE wrytely_agent.canvas_resource_items (
  scan_id uuid NOT NULL,
  resource_key text NOT NULL,
  kind text NOT NULL,
  provider_id text NOT NULL,
  agent_id uuid NOT NULL,
  object_id uuid NOT NULL,
  observation_id uuid NOT NULL,
  content_digest text NOT NULL,
  complete boolean NOT NULL,
  PRIMARY KEY(scan_id,resource_key,kind,provider_id),
  FOREIGN KEY(scan_id,resource_key) REFERENCES wrytely_agent.canvas_resources(scan_id,resource_key),
  FOREIGN KEY(agent_id,object_id) REFERENCES wrytely_agent.canvas_evidence_objects(agent_id,id),
  FOREIGN KEY(agent_id,observation_id)
    REFERENCES wrytely_agent.canvas_evidence_observations(agent_id,id)
);
