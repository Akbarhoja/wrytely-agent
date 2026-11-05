-- Original authenticated inbound receipt owns the atomic command result.
ALTER TABLE wrytely_agent.telegram_inbound ADD COLUMN command_result jsonb
 CHECK (command_result IS NULL OR jsonb_typeof(command_result)='object');

CREATE INDEX telegram_latest_command ON wrytely_agent.telegram_inbound
 (agent_id,bot_id,generation,received_at DESC,update_id DESC)
 WHERE command_result IS NOT NULL;
