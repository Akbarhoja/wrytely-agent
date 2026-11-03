"""Serialized cumulative model caps with conservative unknown-call liabilities.

Operator configuration methods are not public APIs. No implicit credits or grants.
"""

from decimal import ROUND_CEILING, Decimal, InvalidOperation
from uuid import uuid4


class ModelBudgetExceeded(RuntimeError):
    pass


def usd(value):
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Explicit decimal USD required")
    try:
        amount = Decimal(value)
        if not amount.is_finite() or not 0 <= amount <= 10000:
            raise ValueError("Invalid USD amount")
        return amount.quantize(Decimal("0.00000001"), rounding=ROUND_CEILING)
    except InvalidOperation:
        raise ValueError("Invalid USD amount") from None


class ModelBudgetStore:
    def configure_model_budget(self, key, *, ceiling_usd, opening_liability_usd):
        """Trusted operator only; opening liabilities cannot be reset on replay."""
        if not isinstance(key, str) or not 1 <= len(key) <= 100:
            raise ValueError("Invalid budget key")
        ceiling, opening = usd(ceiling_usd), usd(opening_liability_usd)
        if opening > ceiling:
            raise ValueError("Opening liabilities exceed budget")
        with self.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(20417359)")
            row = conn.execute(
                "SELECT * FROM wrytely_agent.model_budgets WHERE id=%s FOR UPDATE", (key,)
            ).fetchone()
            if row and row["opening_liability_usd"] != opening:
                raise ValueError("Historical liabilities cannot be reset")
            spent = conn.execute(
                "SELECT coalesce(sum(liability_usd),0) AS n FROM "
                "wrytely_agent.model_call_reservations WHERE budget_id=%s",
                (key,),
            ).fetchone()["n"]
            if opening + spent > ceiling:
                raise ValueError("Liabilities exceed requested ceiling")
            conn.execute(
                "INSERT INTO wrytely_agent.model_budgets(id,ceiling_usd,opening_liability_usd) "
                "VALUES (%s,%s,%s) ON CONFLICT(id) DO UPDATE SET ceiling_usd=excluded.ceiling_usd",
                (key, ceiling, opening),
            )

    def grant_model_budget(self, key, verified_user, *, ceiling_usd):
        """Operator sets a student share; increasing this requires actual allowance."""
        ceiling = usd(ceiling_usd)
        with self.connection() as conn:
            agent, _ = self._read_identity(conn, verified_user, None)
            budget = conn.execute(
                "SELECT id FROM wrytely_agent.model_budgets WHERE id=%s FOR UPDATE", (key,)
            ).fetchone()
            if not budget:
                raise LookupError("Budget not configured")
            conn.execute(
                "INSERT INTO wrytely_agent.model_budget_grants(budget_id,agent_id,ceiling_usd) "
                "VALUES (%s,%s,%s) ON CONFLICT(budget_id,agent_id) DO UPDATE "
                "SET ceiling_usd=excluded.ceiling_usd",
                (key, agent, ceiling),
            )

    def reserve_model_call(self, verified_user, budget_key, maximum_usd):
        maximum = usd(maximum_usd)
        if maximum <= 0:
            raise ValueError("Positive reservation required")
        with self.connection() as conn:
            agent, _ = self._read_identity(conn, verified_user, None)
            if conn.execute(
                "SELECT paused FROM wrytely_agent.agents WHERE id=%s", (agent,)
            ).fetchone()["paused"]:
                raise ModelBudgetExceeded("Agent paused")
            budget = conn.execute(
                "SELECT * FROM wrytely_agent.model_budgets WHERE id=%s FOR UPDATE", (budget_key,)
            ).fetchone()
            grant = conn.execute(
                "SELECT * FROM wrytely_agent.model_budget_grants "
                "WHERE budget_id=%s AND agent_id=%s",
                (budget_key, agent),
            ).fetchone()
            if not budget or not budget["enabled"] or not grant:
                raise ModelBudgetExceeded("Budget not enabled or granted")
            usage = conn.execute(
                "SELECT coalesce(sum(liability_usd),0) AS total, "
                "coalesce(sum(liability_usd) FILTER (WHERE agent_id=%s),0) AS student "
                "FROM wrytely_agent.model_call_reservations WHERE budget_id=%s",
                (agent, budget_key),
            ).fetchone()
            if (
                budget["opening_liability_usd"] + usage["total"] + maximum > budget["ceiling_usd"]
                or usage["student"] + maximum > grant["ceiling_usd"]
            ):
                raise ModelBudgetExceeded("Model allowance exhausted")
            identifier = uuid4()
            conn.execute(
                "INSERT INTO wrytely_agent.model_call_reservations "
                "(id,budget_id,agent_id,maximum_usd,liability_usd,state) "
                "VALUES (%s,%s,%s,%s,%s,'reserved')",
                (identifier, budget_key, agent, maximum, maximum),
            )
            return identifier

    def settle_model_call(
        self,
        verified_user,
        reservation_id,
        *,
        actual_usd=None,
        input_tokens=None,
        output_tokens=None,
    ):
        from shared.canvas_reads import _uuid

        actual = usd(actual_usd) if actual_usd is not None else None
        if actual is not None and any(
            type(n) is not int or n < 0 for n in (input_tokens, output_tokens)
        ):
            raise ValueError("Known token usage required")
        with self.connection() as conn:
            agent, _ = self._read_identity(conn, verified_user, None)
            row = conn.execute(
                "SELECT * FROM wrytely_agent.model_call_reservations WHERE agent_id=%s AND id=%s",
                (agent, _uuid(reservation_id)),
            ).fetchone()
            if not row:
                raise LookupError("Not found")
            conn.execute(
                "SELECT id FROM wrytely_agent.model_budgets WHERE id=%s FOR UPDATE",
                (row["budget_id"],),
            )
            row = conn.execute(
                "SELECT * FROM wrytely_agent.model_call_reservations WHERE id=%s FOR UPDATE",
                (row["id"],),
            ).fetchone()
            if row["state"] != "reserved":
                raise ValueError("Reservation already settled")
            overrun = actual is not None and actual > row["maximum_usd"]
            state = "unknown" if actual is None else "overrun" if overrun else "settled"
            conn.execute(
                "UPDATE wrytely_agent.model_call_reservations SET state=%s,liability_usd=%s,"
                "input_tokens=%s,output_tokens=%s WHERE id=%s",
                (
                    state,
                    row["maximum_usd"] if actual is None else actual,
                    input_tokens,
                    output_tokens,
                    row["id"],
                ),
            )
            if overrun:
                conn.execute(
                    "UPDATE wrytely_agent.model_budgets SET enabled=false WHERE id=%s",
                    (row["budget_id"],),
                )
            return state
