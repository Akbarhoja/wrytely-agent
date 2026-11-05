-- Private unpublished staging only; no observation/source/model activation.
ALTER TABLE wrytely_agent.canvas_scans ADD CONSTRAINT canvas_document_scan_identity
  UNIQUE(connection_id,generation,id);
CREATE TABLE wrytely_agent.canvas_document_uploads (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  connection_id uuid NOT NULL,
  scan_id uuid NOT NULL,
  generation bigint NOT NULL CHECK (generation>=1),
  resource_key text NOT NULL,
  header jsonb NOT NULL CHECK (jsonb_typeof(header)='object'),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (expires_at<=created_at+interval '30 minutes'),
  UNIQUE(agent_id,connection_id,scan_id,id),
  FOREIGN KEY(connection_id,generation,scan_id)
    REFERENCES wrytely_agent.canvas_scans(connection_id,generation,id),
  FOREIGN KEY(agent_id,connection_id) REFERENCES wrytely_agent.source_connections(agent_id,id)
);
CREATE INDEX canvas_document_upload_expiry ON wrytely_agent.canvas_document_uploads(connection_id,expires_at);
CREATE TABLE wrytely_agent.canvas_document_upload_parts (
  upload_id uuid NOT NULL REFERENCES wrytely_agent.canvas_document_uploads(id),
  slot integer NOT NULL CHECK (slot BETWEEN 0 AND 511),
  text text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 24000),
  PRIMARY KEY(upload_id,slot)
);
CREATE TABLE wrytely_agent.canvas_document_upload_receipts (
  scan_id uuid NOT NULL REFERENCES wrytely_agent.canvas_scans(id),
  operation text NOT NULL CHECK (operation IN ('begin_document','put_document_parts')),
  request_key text NOT NULL,
  upload_id uuid NOT NULL REFERENCES wrytely_agent.canvas_document_uploads(id),
  digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
  response jsonb NOT NULL,
  PRIMARY KEY(scan_id,operation,request_key)
);
