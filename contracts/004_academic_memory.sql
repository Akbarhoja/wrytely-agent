CREATE TABLE wrytely_agent.academic_sources (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  source_key text NOT NULL,
  latest_version_id uuid,
  UNIQUE(agent_id,source_key),
  UNIQUE(agent_id,id)
);
CREATE TABLE wrytely_agent.source_versions (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  source_id uuid NOT NULL,
  external_revision text NOT NULL,
  title text NOT NULL,
  reference text NOT NULL,
  coverage text NOT NULL CHECK (coverage IN ('snapshot','api','feed','group')),
  content text NOT NULL,
  retrieved_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(source_id,external_revision),
  UNIQUE(agent_id,id),
  FOREIGN KEY(agent_id,source_id) REFERENCES wrytely_agent.academic_sources(agent_id,id)
);
ALTER TABLE wrytely_agent.academic_sources ADD CONSTRAINT source_latest_scope
  FOREIGN KEY(agent_id,latest_version_id) REFERENCES wrytely_agent.source_versions(agent_id,id);
CREATE TABLE wrytely_agent.responsibility_sources (
  agent_id uuid NOT NULL,
  responsibility_id uuid NOT NULL,
  source_id uuid NOT NULL,
  PRIMARY KEY(responsibility_id,source_id),
  FOREIGN KEY(agent_id,responsibility_id) REFERENCES wrytely_agent.responsibilities(agent_id,id),
  FOREIGN KEY(agent_id,source_id) REFERENCES wrytely_agent.academic_sources(agent_id,id)
);
CREATE TABLE wrytely_agent.source_facts (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  responsibility_id uuid NOT NULL,
  version_id uuid NOT NULL,
  fact_hash text NOT NULL,
  claim text NOT NULL,
  quote text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(responsibility_id,version_id,fact_hash),
  FOREIGN KEY(agent_id,responsibility_id) REFERENCES wrytely_agent.responsibilities(agent_id,id),
  FOREIGN KEY(agent_id,version_id) REFERENCES wrytely_agent.source_versions(agent_id,id)
);
ALTER TABLE wrytely_agent.responsibilities ADD COLUMN memory_revision integer NOT NULL DEFAULT 0;
ALTER TABLE wrytely_agent.tasks ADD COLUMN memory_revision integer;
