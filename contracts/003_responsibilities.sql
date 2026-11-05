CREATE TABLE wrytely_agent.responsibilities (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  request_key text NOT NULL,
  objective text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','blocked','done')),
  status_reason text,
  steps_created integer NOT NULL DEFAULT 0,
  max_steps integer NOT NULL CHECK (max_steps BETWEEN 1 AND 12),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (agent_id,request_key),
  UNIQUE (agent_id,id)
);
ALTER TABLE wrytely_agent.tasks ADD COLUMN responsibility_id uuid;
ALTER TABLE wrytely_agent.tasks ADD COLUMN kind text NOT NULL DEFAULT 'reply'
  CHECK (kind IN ('reply','plan','academic'));
ALTER TABLE wrytely_agent.tasks ADD COLUMN step_key text;
ALTER TABLE wrytely_agent.tasks ADD CONSTRAINT task_responsibility_scope
  FOREIGN KEY(agent_id,responsibility_id) REFERENCES wrytely_agent.responsibilities(agent_id,id);
CREATE UNIQUE INDEX responsibility_step_unique
  ON wrytely_agent.tasks(responsibility_id,step_key) WHERE step_key IS NOT NULL;

ALTER TABLE wrytely_agent.messages DROP CONSTRAINT messages_role_check;
ALTER TABLE wrytely_agent.messages ADD CONSTRAINT messages_role_check
  CHECK (role IN ('user','assistant','internal'));
