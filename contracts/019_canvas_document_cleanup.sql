-- Explicit bounded staging maintenance only. Published/historical evidence is retained.
ALTER TABLE wrytely_agent.canvas_document_uploads ADD COLUMN cleaned_at timestamptz;
CREATE INDEX canvas_upload_ready_pointer ON wrytely_agent.canvas_document_uploads(document_version_id)
  WHERE document_version_id IS NOT NULL;
CREATE INDEX canvas_document_binding_root ON wrytely_agent.canvas_document_bindings(document_version_id);
CREATE INDEX canvas_protocol_root_age ON wrytely_agent.canvas_document_versions(created_at,id)
  WHERE protocol_payload IS NOT NULL;
