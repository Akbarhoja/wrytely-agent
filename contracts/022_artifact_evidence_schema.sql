-- Internal v2 drafts share artifact/check/recovery machinery; old consumer DTOs stay v1.
ALTER TABLE wrytely_agent.artifacts
    ADD COLUMN evidence_schema integer NOT NULL DEFAULT 1 CHECK(evidence_schema IN (1,2));
