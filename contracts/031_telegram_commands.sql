-- Original authenticated inbound receipt owns the atomic command result.
ALTER TABLE wrytely_agent.telegram_inbound ADD COLUMN command_result jsonb
 CHECK (command_result IS NULL OR jsonb_typeof(command_result)='object');
