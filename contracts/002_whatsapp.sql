CREATE TABLE wrytely_agent.channel_challenges (
  agent_id uuid PRIMARY KEY REFERENCES wrytely_agent.agents(id),
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL
);
CREATE TABLE wrytely_agent.channel_links (
  agent_id uuid PRIMARY KEY REFERENCES wrytely_agent.agents(id),
  phone text NOT NULL UNIQUE,
  linked_at timestamptz NOT NULL DEFAULT now(),
  last_inbound_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE wrytely_agent.whatsapp_inbound (
  provider_id text PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  task_id uuid UNIQUE REFERENCES wrytely_agent.tasks(id),
  received_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE wrytely_agent.whatsapp_outbound (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
  task_id uuid NOT NULL UNIQUE REFERENCES wrytely_agent.tasks(id),
  recipient text NOT NULL,
  content text NOT NULL,
  state text NOT NULL DEFAULT 'queued' CHECK (state IN
    ('queued','deferred','sending','accepted','delivered','unknown','failed','cancelled')),
  provider_ref text,
  created_at timestamptz NOT NULL DEFAULT now()
);
