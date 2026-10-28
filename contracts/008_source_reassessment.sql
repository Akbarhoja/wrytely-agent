ALTER TABLE wrytely_agent.responsibilities ADD COLUMN reassess_source_changes boolean NOT NULL DEFAULT false;
DROP INDEX wrytely_agent.responsibility_step_unique;
CREATE UNIQUE INDEX responsibility_step_unique
  ON wrytely_agent.tasks(responsibility_id,memory_revision,step_key) WHERE step_key IS NOT NULL;
