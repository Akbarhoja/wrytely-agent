CREATE SCHEMA IF NOT EXISTS wrytely_agent;
CREATE TABLE IF NOT EXISTS wrytely_agent.migrations (
  version text PRIMARY KEY,
  checksum text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE wrytely_agent.students (
  user_id text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE wrytely_agent.agents (
  id uuid PRIMARY KEY,
  user_id text NOT NULL UNIQUE REFERENCES wrytely_agent.students(user_id),
  paused boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE wrytely_agent.messages (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  role text NOT NULL CHECK (role IN ('user','assistant')),
  content text NOT NULL,
  request_key text,
  source_task_id uuid UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (agent_id, request_key),
  UNIQUE (agent_id, id)
);
CREATE TABLE wrytely_agent.tasks (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  message_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','running','done','blocked')),
  attempts integer NOT NULL DEFAULT 0,
  lease_token uuid,
  lease_until timestamptz,
  available_at timestamptz NOT NULL DEFAULT now(),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (agent_id, message_id),
  FOREIGN KEY (agent_id, message_id) REFERENCES wrytely_agent.messages(agent_id, id)
);
CREATE INDEX tasks_ready ON wrytely_agent.tasks (available_at, created_at)
  WHERE status IN ('ready','running');
CREATE TABLE wrytely_agent.episode_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  task_id uuid NOT NULL REFERENCES wrytely_agent.tasks(id),
  attempt integer NOT NULL,
  kind text NOT NULL,
  data jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
