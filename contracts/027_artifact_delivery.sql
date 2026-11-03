-- Immutable checked files use the original dispatch and signed-receipt ledger.
ALTER TABLE wrytely_agent.artifacts ADD UNIQUE(agent_id,id);
ALTER TABLE wrytely_agent.artifact_checks ADD UNIQUE(id,artifact_id);
CREATE TABLE wrytely_agent.artifact_delivery_files (
 id uuid PRIMARY KEY,
 agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
 artifact_id uuid NOT NULL,
 check_id uuid NOT NULL,
 filename text NOT NULL,
 media_type text NOT NULL,
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 byte_length integer NOT NULL CHECK(byte_length BETWEEN 1 AND 10485760),
 content bytea NOT NULL CHECK(octet_length(content)=byte_length),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(agent_id,id),
 UNIQUE(agent_id,artifact_id),
 FOREIGN KEY(agent_id,artifact_id) REFERENCES wrytely_agent.artifacts(agent_id,id),
 FOREIGN KEY(check_id,artifact_id) REFERENCES wrytely_agent.artifact_checks(id,artifact_id)
);
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN artifact_file_id uuid UNIQUE;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD CONSTRAINT artifact_delivery_owner
 FOREIGN KEY(agent_id,artifact_file_id) REFERENCES wrytely_agent.artifact_delivery_files(agent_id,id);
ALTER TABLE wrytely_agent.whatsapp_outbound DROP CONSTRAINT whatsapp_action_kind;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD CONSTRAINT whatsapp_action_kind
 CHECK(num_nonnulls(task_id,course_offer_id,artifact_file_id)=1);
