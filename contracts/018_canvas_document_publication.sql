ALTER TABLE wrytely_agent.canvas_resources
  ADD COLUMN content_mode text CHECK(content_mode IN ('inline','documents'));
ALTER TABLE wrytely_agent.canvas_document_uploads ADD COLUMN published_at timestamptz;
