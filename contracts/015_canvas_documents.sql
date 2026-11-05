-- Internal section storage only. Upload/publication wire and activation remain separate.
CREATE TABLE wrytely_agent.canvas_document_versions (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  object_id uuid NOT NULL,
  section_fingerprint text NOT NULL CHECK (section_fingerprint ~ '^[0-9a-f]{64}$'),
  format text NOT NULL CHECK (format IN ('text','html_text','pdf_text')),
  extractor_version text NOT NULL,
  total_characters integer NOT NULL CHECK (total_characters BETWEEN 0 AND 200000),
  total_pages integer CHECK (total_pages BETWEEN 1 AND 200),
  manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest)='array' AND jsonb_array_length(manifest)<=512),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK ((format='pdf_text' AND total_pages IS NOT NULL) OR
         (format<>'pdf_text' AND total_pages IS NULL)),
  UNIQUE(agent_id,object_id,id),
  UNIQUE(agent_id,object_id,section_fingerprint),
  FOREIGN KEY(agent_id,object_id) REFERENCES wrytely_agent.canvas_evidence_objects(agent_id,id)
);
CREATE TABLE wrytely_agent.canvas_document_sections (
  id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  object_id uuid NOT NULL,
  document_version_id uuid NOT NULL,
  slot integer NOT NULL CHECK (slot BETWEEN 0 AND 511),
  start_offset integer NOT NULL CHECK (start_offset>=0),
  end_offset integer NOT NULL CHECK (end_offset>start_offset AND end_offset<=200000),
  page integer CHECK (page BETWEEN 1 AND 200),
  text text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 24000),
  text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
  CHECK (char_length(text)=end_offset-start_offset),
  UNIQUE(document_version_id,slot),
  FOREIGN KEY(agent_id,object_id,document_version_id)
    REFERENCES wrytely_agent.canvas_document_versions(agent_id,object_id,id)
);
CREATE TABLE wrytely_agent.canvas_document_bindings (
  observation_id uuid PRIMARY KEY,
  agent_id uuid NOT NULL,
  object_id uuid NOT NULL,
  document_version_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  FOREIGN KEY(agent_id,object_id,observation_id)
    REFERENCES wrytely_agent.canvas_evidence_observations(agent_id,object_id,id),
  FOREIGN KEY(agent_id,object_id,document_version_id)
    REFERENCES wrytely_agent.canvas_document_versions(agent_id,object_id,id)
);
