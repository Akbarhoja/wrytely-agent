CREATE TABLE wrytely_agent.private_draft_intents (
  responsibility_id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  memory_revision integer NOT NULL,
  max_revisions integer NOT NULL CHECK(max_revisions BETWEEN 0 AND 2),
  assessment jsonb,
  drafting_task_id uuid UNIQUE REFERENCES wrytely_agent.tasks(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY(agent_id,responsibility_id) REFERENCES wrytely_agent.responsibilities(agent_id,id)
);
