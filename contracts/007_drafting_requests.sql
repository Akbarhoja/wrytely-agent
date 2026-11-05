CREATE TABLE wrytely_agent.drafting_requests (
  task_id uuid PRIMARY KEY REFERENCES wrytely_agent.tasks(id),
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  specification jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
