-- A separate provider transport inside the original Store/task runtime.
CREATE TABLE wrytely_agent.telegram_challenges (
 agent_id uuid PRIMARY KEY REFERENCES wrytely_agent.agents(id),
 bot_id bigint NOT NULL CHECK(bot_id>0),
 token_hash text NOT NULL UNIQUE,
 expires_at timestamptz NOT NULL
);
CREATE TABLE wrytely_agent.telegram_links (
 agent_id uuid PRIMARY KEY REFERENCES wrytely_agent.agents(id),
 bot_id bigint NOT NULL CHECK(bot_id>0),
 chat_id bigint NOT NULL CHECK(chat_id>0),
 generation uuid NOT NULL UNIQUE,
 consent boolean NOT NULL DEFAULT false,
 notification_consent boolean NOT NULL DEFAULT false,
 timezone text NOT NULL DEFAULT 'UTC',
 quiet_start integer NOT NULL DEFAULT 22 CHECK(quiet_start BETWEEN 0 AND 23),
 quiet_end integer NOT NULL DEFAULT 8 CHECK(quiet_end BETWEEN 0 AND 23),
 linked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 linking_update_id bigint NOT NULL,
 UNIQUE(bot_id,chat_id)
);
CREATE TABLE wrytely_agent.telegram_inbound (
 bot_id bigint NOT NULL,
 update_id bigint NOT NULL CHECK(update_id>=0),
 agent_id uuid REFERENCES wrytely_agent.agents(id),
 generation uuid,
 digest text NOT NULL,
 outcome text NOT NULL,
 task_id uuid UNIQUE REFERENCES wrytely_agent.tasks(id),
 received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(bot_id,update_id)
);
CREATE TABLE wrytely_agent.telegram_outbound (
 id uuid PRIMARY KEY,
 agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
 bot_id bigint NOT NULL,
 chat_id bigint NOT NULL,
 generation uuid NOT NULL,
 intent_key text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('reply','preparation')),
 task_id uuid REFERENCES wrytely_agent.tasks(id),
 supervision_id uuid REFERENCES wrytely_agent.course_supervisions(id),
 preparation_id uuid,
 content text NOT NULL,
 state text NOT NULL DEFAULT 'queued' CHECK(state IN
  ('queued','claimed','sending','accepted','unknown','failed','cancelled')),
 attempt_token uuid,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
 lease_until timestamptz,
 dispatch_at timestamptz,
 available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 provider_ref text,
 reason text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(agent_id,intent_key),
 CHECK((kind='reply' AND task_id IS NOT NULL AND supervision_id IS NULL AND preparation_id IS NULL)
  OR(kind='preparation' AND task_id IS NULL AND supervision_id IS NOT NULL AND preparation_id IS NOT NULL))
);
CREATE INDEX telegram_ready ON wrytely_agent.telegram_outbound(bot_id,available_at)
 WHERE state IN ('queued','claimed','sending');
