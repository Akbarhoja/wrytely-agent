-- Typed proactive offers reuse the original durable dispatch/receipt queue.
ALTER TABLE wrytely_agent.course_supervisions
 ADD COLUMN notification_consent boolean NOT NULL DEFAULT false;
ALTER TABLE wrytely_agent.course_offers ADD UNIQUE(agent_id,id);
ALTER TABLE wrytely_agent.whatsapp_outbound ALTER COLUMN task_id DROP NOT NULL;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN course_offer_id uuid UNIQUE;
ALTER TABLE wrytely_agent.whatsapp_outbound ADD CONSTRAINT course_offer_delivery_owner
 FOREIGN KEY(agent_id,course_offer_id) REFERENCES wrytely_agent.course_offers(agent_id,id);
ALTER TABLE wrytely_agent.whatsapp_outbound ADD CONSTRAINT whatsapp_action_kind
 CHECK ((task_id IS NOT NULL AND course_offer_id IS NULL) OR
        (task_id IS NULL AND course_offer_id IS NOT NULL));
ALTER TABLE wrytely_agent.whatsapp_outbound ADD COLUMN dispatch_payload jsonb;
