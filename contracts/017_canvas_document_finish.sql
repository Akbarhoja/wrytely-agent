-- Ready protocol roots reuse private015 sections; no evidence publication here.
ALTER TABLE wrytely_agent.canvas_document_versions
  ADD COLUMN protocol_payload jsonb,
  ADD CONSTRAINT canvas_protocol_payload_shape CHECK (
    protocol_payload IS NULL OR (
      jsonb_typeof(protocol_payload)='object' AND
      (protocol_payload->>'kind'='document') IS TRUE
    )
  );
ALTER TABLE wrytely_agent.canvas_document_uploads
  ADD COLUMN object_id uuid,
  ADD COLUMN document_version_id uuid,
  ADD CONSTRAINT canvas_ready_root_pair CHECK ((object_id IS NULL)=(document_version_id IS NULL)),
  ADD CONSTRAINT canvas_ready_root_owner FOREIGN KEY(agent_id,object_id,document_version_id)
    REFERENCES wrytely_agent.canvas_document_versions(agent_id,object_id,id);
ALTER TABLE wrytely_agent.canvas_document_upload_receipts
  DROP CONSTRAINT canvas_document_upload_receipts_operation_check,
  ADD CONSTRAINT canvas_document_upload_receipts_operation_check
    CHECK(operation IN ('begin_document','put_document_parts','finish_document'));
