-- Private short-lived read handles. No source promotion or provider credentials.
CREATE TABLE wrytely_agent.canvas_read_cursors (
  token_hash text PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  connection_id uuid NOT NULL,
  generation bigint NOT NULL,
  course_filter text,
  task_id uuid,
  anchor uuid NOT NULL,
  expires_at timestamptz NOT NULL DEFAULT clock_timestamp()+interval '15 minutes',
  FOREIGN KEY(agent_id,connection_id) REFERENCES wrytely_agent.source_connections(agent_id,id),
  FOREIGN KEY(agent_id,anchor) REFERENCES wrytely_agent.canvas_evidence_objects(agent_id,id)
);
CREATE INDEX canvas_read_cursor_owner_expiry
  ON wrytely_agent.canvas_read_cursors(agent_id,expires_at);
