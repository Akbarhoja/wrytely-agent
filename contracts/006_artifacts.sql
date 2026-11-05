CREATE TABLE wrytely_agent.artifacts (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  responsibility_id uuid NOT NULL,
  task_id uuid NOT NULL REFERENCES wrytely_agent.tasks(id),
  request_key text NOT NULL,
  memory_revision integer NOT NULL,
  draft jsonb NOT NULL,
  state text NOT NULL DEFAULT 'review' CHECK(state IN ('review','ready','needs_revision')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(task_id,request_key),
  FOREIGN KEY(agent_id,responsibility_id) REFERENCES wrytely_agent.responsibilities(agent_id,id)
);
CREATE TABLE wrytely_agent.artifact_checks (
  id uuid PRIMARY KEY,
  artifact_id uuid NOT NULL REFERENCES wrytely_agent.artifacts(id),
  memory_revision integer NOT NULL,
  passed boolean NOT NULL,
  report jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
