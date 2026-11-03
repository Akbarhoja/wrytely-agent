-- Private persisted supervision; no automatic enrollment or worker activation.
CREATE TABLE wrytely_agent.course_supervisions (
 id uuid PRIMARY KEY,
 agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
 connection_id uuid NOT NULL REFERENCES wrytely_agent.source_connections(id),
 course_id text NOT NULL,
 generation bigint NOT NULL,
 scope_revision bigint NOT NULL,
 state text NOT NULL DEFAULT 'ready' CHECK(state IN ('ready','running','paused','blocked')),
 next_check_at timestamptz NOT NULL DEFAULT now(),
 lease_token uuid,
 lease_until timestamptz,
 calls_reserved integer NOT NULL DEFAULT 0,
 call_limit integer NOT NULL CHECK(call_limit BETWEEN 1 AND 20),
 snapshot_digest text,
 inspections jsonb NOT NULL DEFAULT '{}'::jsonb,
 last_decision jsonb,
 reason text,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(agent_id,connection_id,course_id),
 UNIQUE(agent_id,id)
);
CREATE TABLE wrytely_agent.course_offers (
 id uuid PRIMARY KEY,
 agent_id uuid NOT NULL,
 supervision_id uuid NOT NULL,
 object_id uuid NOT NULL,
 version_id uuid NOT NULL,
 message text NOT NULL,
 reason text NOT NULL,
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','accepted','declined','stale')),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(supervision_id,object_id,version_id),
 FOREIGN KEY(agent_id,supervision_id) REFERENCES wrytely_agent.course_supervisions(agent_id,id),
 FOREIGN KEY(agent_id,object_id) REFERENCES wrytely_agent.canvas_evidence_objects(agent_id,id)
);
