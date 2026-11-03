-- Original authenticated inbound record owns command replay; no second task queue.
ALTER TABLE wrytely_agent.whatsapp_inbound
 ADD COLUMN command_body jsonb,
 ADD COLUMN command_digest text,
 ADD COLUMN command_link_generation uuid,
 ADD COLUMN command_result jsonb;
ALTER TABLE wrytely_agent.whatsapp_inbound ADD CONSTRAINT whatsapp_command_shape
 CHECK (num_nonnulls(command_body,command_digest,command_link_generation,command_result)=0 OR
        (num_nonnulls(command_body,command_digest,command_link_generation,command_result)=4 AND
         command_digest ~ '^[0-9a-f]{64}$' AND task_id IS NULL));
