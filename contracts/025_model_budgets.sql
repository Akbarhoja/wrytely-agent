-- Operator-configured caps; no default grant, credit or release of historical usage.
CREATE TABLE wrytely_agent.model_budgets (
 id text PRIMARY KEY,
 ceiling_usd numeric(18,8) NOT NULL CHECK(ceiling_usd>=0),
 opening_liability_usd numeric(18,8) NOT NULL CHECK(opening_liability_usd>=0),
 enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE wrytely_agent.model_budget_grants (
 budget_id text NOT NULL REFERENCES wrytely_agent.model_budgets(id),
 agent_id uuid NOT NULL REFERENCES wrytely_agent.agents(id),
 ceiling_usd numeric(18,8) NOT NULL CHECK(ceiling_usd>=0),
 PRIMARY KEY(budget_id,agent_id)
);
CREATE TABLE wrytely_agent.model_call_reservations (
 id uuid PRIMARY KEY,
 budget_id text NOT NULL,
 agent_id uuid NOT NULL,
 maximum_usd numeric(18,8) NOT NULL CHECK(maximum_usd>0),
 liability_usd numeric(18,8) NOT NULL CHECK(liability_usd>=0),
 state text NOT NULL CHECK(state IN ('reserved','settled','unknown','overrun')),
 input_tokens bigint,
 output_tokens bigint,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(budget_id,agent_id) REFERENCES wrytely_agent.model_budget_grants(budget_id,agent_id)
);
