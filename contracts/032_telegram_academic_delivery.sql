-- Extend the original one-attempt Telegram outbox, not a parallel delivery queue.
ALTER TABLE wrytely_agent.telegram_outbound
 ADD COLUMN offer_id uuid REFERENCES wrytely_agent.course_offers(id),
 ADD COLUMN artifact_file_id uuid,
 ADD COLUMN command_update_id bigint,
 ADD CONSTRAINT telegram_artifact_owner FOREIGN KEY(agent_id,artifact_file_id)
 REFERENCES wrytely_agent.artifact_delivery_files(agent_id,id),
 ADD CONSTRAINT telegram_command_receipt FOREIGN KEY(bot_id,command_update_id)
 REFERENCES wrytely_agent.telegram_inbound(bot_id,update_id);
ALTER TABLE wrytely_agent.telegram_outbound DROP CONSTRAINT telegram_outbound_kind_check;
ALTER TABLE wrytely_agent.telegram_outbound DROP CONSTRAINT telegram_outbound_check;
ALTER TABLE wrytely_agent.telegram_outbound ADD CONSTRAINT telegram_delivery_kind
 CHECK(kind IN ('reply','preparation','offer','artifact','command'));
ALTER TABLE wrytely_agent.telegram_outbound ADD CONSTRAINT telegram_delivery_target
 CHECK(
 (kind='reply' AND task_id IS NOT NULL AND
 num_nonnulls(supervision_id,preparation_id,offer_id,artifact_file_id,command_update_id)=0)
 OR (kind='preparation' AND supervision_id IS NOT NULL AND preparation_id IS NOT NULL AND
 num_nonnulls(task_id,offer_id,artifact_file_id,command_update_id)=0)
 OR (kind='offer' AND supervision_id IS NOT NULL AND offer_id IS NOT NULL AND
 num_nonnulls(task_id,preparation_id,artifact_file_id,command_update_id)=0)
 OR (kind='artifact' AND artifact_file_id IS NOT NULL AND
 num_nonnulls(task_id,supervision_id,preparation_id,offer_id,command_update_id)=0)
 OR (kind='command' AND command_update_id IS NOT NULL AND
 num_nonnulls(task_id,supervision_id,preparation_id,offer_id,artifact_file_id)=0));
CREATE INDEX telegram_offer_history ON wrytely_agent.telegram_outbound(agent_id,offer_id)
 WHERE offer_id IS NOT NULL;
CREATE INDEX telegram_file_history ON wrytely_agent.telegram_outbound(agent_id,artifact_file_id)
 WHERE artifact_file_id IS NOT NULL;
