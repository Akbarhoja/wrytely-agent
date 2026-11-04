-- Private non-submission checklists inside the original supervisor, not draft artifacts.
ALTER TABLE wrytely_agent.course_supervisions
 ADD COLUMN preparations jsonb NOT NULL DEFAULT '[]'::jsonb
 CHECK(jsonb_typeof(preparations)='array' AND jsonb_array_length(preparations)<=20);
