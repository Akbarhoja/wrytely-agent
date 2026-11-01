-- Additive private event detail; old rows stay explicitly unavailable (NULL).
ALTER TABLE wrytely_agent.canvas_evidence_observations
  ADD CONSTRAINT canvas_observation_object_identity UNIQUE(agent_id,object_id,id);
ALTER TABLE wrytely_agent.canvas_evidence_events
  ADD COLUMN previous_observation_id uuid,
  ADD COLUMN changes jsonb,
  ADD CONSTRAINT canvas_event_previous_object
    FOREIGN KEY(agent_id,object_id,previous_observation_id)
    REFERENCES wrytely_agent.canvas_evidence_observations(agent_id,object_id,id),
  ADD CONSTRAINT canvas_event_change_shape CHECK (
    changes IS NULL OR (
      jsonb_typeof(changes)='object'
      AND (changes->'schema_version'='1'::jsonb) IS TRUE
      AND octet_length(changes::text)<=8192
    )
  );
