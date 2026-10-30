"""Private connection read model; verified caller identity, no transport side effects."""


class ConnectionStatusStore:
    def whatsapp_connection(self, user_id: str):
        with self.connection() as conn:
            # One statement snapshot keeps unlink/preferences and delivery views
            # mutually consistent. Never translate storage failure into disconnected.
            row = conn.execute(
                "SELECT a.id,l.phone,p.consent,p.timezone,p.quiet_start,p.quiet_end, "
                "d.state,d.hold_reason,d.retry_at FROM wrytely_agent.agents a "
                "LEFT JOIN wrytely_agent.channel_links l ON l.agent_id=a.id "
                "LEFT JOIN wrytely_agent.communication_preferences p ON p.agent_id=a.id "
                "LEFT JOIN LATERAL (SELECT state,hold_reason,retry_at "
                "FROM wrytely_agent.whatsapp_outbound WHERE agent_id=a.id "
                "ORDER BY created_at DESC,id DESC LIMIT 1) d ON true WHERE a.user_id=%s",
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            preferences = None
            if row["timezone"] is not None:
                preferences = {
                    key: row[key] for key in ("consent", "timezone", "quiet_start", "quiet_end")
                }
            latest = None
            if row["state"] is not None:
                latest = {
                    "state": row["state"],
                    "reason": row["hold_reason"],
                    "retry_at": row["retry_at"],
                }
            return {
                "linked": row["phone"] is not None,
                "phone_last4": row["phone"][-4:] if row["phone"] else None,
                "preferences": preferences,
                "latest_delivery": latest,
            }
