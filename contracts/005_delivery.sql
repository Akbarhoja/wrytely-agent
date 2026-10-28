ALTER TABLE wrytely_agent.channel_links ADD COLUMN generation uuid;
UPDATE wrytely_agent.channel_links SET generation=agent_id;
ALTER TABLE wrytely_agent.channel_links ALTER COLUMN generation SET NOT NULL;
ALTER TABLE wrytely_agent.channel_links ADD COLUMN last_event_at timestamptz;
CREATE TABLE wrytely_agent.communication_preferences (
  agent_id uuid PRIMARY KEY REFERENCES wrytely_agent.agents(id),
  consent boolean NOT NULL,
  timezone text NOT NULL,
  quiet_start integer NOT NULL CHECK (quiet_start BETWEEN 0 AND 23),
  quiet_end integer NOT NULL CHECK (quiet_end BETWEEN 0 AND 23)
);
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN link_generation uuid;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN worker_id text;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN attempt_token uuid;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN lease_until timestamptz;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN dispatch_at timestamptz;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN hold_reason text;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN retry_at timestamptz;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN business_id text;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN phone_number_id text;
-- Historical replies have no proven link generation or consent: do not backfill permission.
CREATE UNIQUE INDEX whatsapp_provider_reference ON wrytely_agent.whatsapp_outbound(provider_ref)
  WHERE provider_ref IS NOT NULL;
CREATE TABLE wrytely_agent.whatsapp_status_events (
  event_hash text PRIMARY KEY,
  business_id text NOT NULL,
  phone_number_id text NOT NULL,
  provider_ref text NOT NULL,
  recipient text NOT NULL,
  status text NOT NULL CHECK(status IN ('sent','delivered','read','failed')),
  event_at timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  action_id uuid REFERENCES wrytely_agent.whatsapp_outbound(id)
);
CREATE INDEX whatsapp_unmatched_status ON wrytely_agent.whatsapp_status_events(provider_ref)
  WHERE action_id IS NULL;
