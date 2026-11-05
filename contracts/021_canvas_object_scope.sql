-- Explicit responsibility scope for published Canvas objects, including document-only roots.
ALTER TABLE wrytely_agent.canvas_evidence_objects
    ADD CONSTRAINT canvas_object_connection_owner UNIQUE(agent_id,id,connection_id);
CREATE TABLE wrytely_agent.responsibility_canvas_objects (
    agent_id uuid NOT NULL,
    responsibility_id uuid NOT NULL,
    object_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    connection_generation bigint NOT NULL CHECK(connection_generation>0),
    PRIMARY KEY(agent_id,responsibility_id,object_id),
    FOREIGN KEY(agent_id,responsibility_id)
        REFERENCES wrytely_agent.responsibilities(agent_id,id),
    FOREIGN KEY(agent_id,object_id,connection_id)
        REFERENCES wrytely_agent.canvas_evidence_objects(agent_id,id,connection_id),
    FOREIGN KEY(agent_id,connection_id)
        REFERENCES wrytely_agent.source_connections(agent_id,id)
);
CREATE INDEX responsibility_canvas_connection
    ON wrytely_agent.responsibility_canvas_objects(connection_id);
