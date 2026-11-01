-- Internal immutable draft provenance; existing external DraftArtifact is unchanged.
ALTER TABLE wrytely_agent.artifacts
    ADD COLUMN document_citations jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(document_citations) = 'array'
           AND jsonb_array_length(document_citations) <= 30);
