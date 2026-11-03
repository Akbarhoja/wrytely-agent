-- New evidence can wake an opted-in monitor before its model-selected next check.
ALTER TABLE wrytely_agent.course_supervisions
 ADD COLUMN last_source_event_at timestamptz;
