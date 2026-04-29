# fortress_logger.py
# RemitIQ 360 — Shared Firestore Logger
# Used by all agents + Fortress AI for audit trail

import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone
import uuid

# ── Firestore client (shared app instance) ───────────────────────────────────
def _get_db():
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
    return firestore.client()

# ── Core log writer ──────────────────────────────────────────────────────────
def log_event(
    agent_name: str,
    event_type: str,
    corridor: str = None,
    user_query: str = None,
    response_summary: str = None,
    metadata: dict = None,
    severity: str = "INFO"
) -> dict:
    """
    Write a structured log event to Firestore.

    Args:
        agent_name:       e.g. 'pakistan_agent', 'bangladesh_agent', 'fortress_ai'
        event_type:       e.g. 'rate_query', 'compliance_check', 'alert', 'error'
        corridor:         e.g. 'AED_PKR', 'SAR_BDT'
        user_query:       sanitized user input (no PII)
        response_summary: brief summary of agent response
        metadata:         any extra key-value pairs
        severity:         'INFO', 'WARNING', 'ERROR', 'CRITICAL'

    Returns:
        dict with log_id and status
    """
    try:
        db = _get_db()
        log_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        log_entry = {
            "log_id": log_id,
            "timestamp": timestamp,
            "agent_name": agent_name,
            "event_type": event_type,
            "severity": severity,
            "corridor": corridor or "general",
            "user_query": user_query or "",
            "response_summary": response_summary or "",
            "metadata": metadata or {},
        }

        db.collection("agent_logs").document(log_id).set(log_entry)

        return {"status": "success", "log_id": log_id}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Alert logger (for Fortress AI) ──────────────────────────────────────────
def log_alert(
    alert_type: str,
    corridor: str,
    details: str,
    severity: str = "WARNING",
    source_agent: str = "fortress_ai"
) -> dict:
    """
    Log a compliance or fraud alert from Fortress AI.

    Args:
        alert_type: e.g. 'rate_anomaly', 'suspicious_pattern', 'compliance_breach'
        corridor:   e.g. 'AED_PKR'
        details:    human-readable alert description
        severity:   'WARNING', 'ERROR', 'CRITICAL'
        source_agent: which agent raised the alert
    """
    try:
        db = _get_db()
        alert_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        alert_entry = {
            "alert_id": alert_id,
            "timestamp": timestamp,
            "alert_type": alert_type,
            "corridor": corridor,
            "details": details,
            "severity": severity,
            "source_agent": source_agent,
            "resolved": False,
        }

        db.collection("fortress_alerts").document(alert_id).set(alert_entry)

        return {"status": "success", "alert_id": alert_id}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Query log reader (for dashboard/audit) ───────────────────────────────────
def get_recent_logs(agent_name: str = None, limit: int = 20) -> dict:
    """
    Fetch recent log entries from Firestore.

    Args:
        agent_name: filter by agent (optional)
        limit:      number of records to return (default 20)
    """
    try:
        db = _get_db()
        ref = db.collection("agent_logs").order_by(
            "timestamp", direction=firestore.Query.DESCENDING
        ).limit(limit)

        if agent_name:
            ref = db.collection("agent_logs")\
                .where("agent_name", "==", agent_name)\
                .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                .limit(limit)

        docs = ref.stream()
        logs = [doc.to_dict() for doc in docs]

        return {"status": "success", "count": len(logs), "logs": logs}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Alert reader ─────────────────────────────────────────────────────────────
def get_active_alerts(corridor: str = None, limit: int = 10) -> dict:
    """
    Fetch unresolved Fortress AI alerts.

    Args:
        corridor: filter by corridor (optional)
        limit:    number of records to return
    """
    try:
        db = _get_db()
        ref = db.collection("fortress_alerts")\
            .where("resolved", "==", False)\
            .order_by("timestamp", direction=firestore.Query.DESCENDING)\
            .limit(limit)

        if corridor:
            ref = db.collection("fortress_alerts")\
                .where("corridor", "==", corridor)\
                .where("resolved", "==", False)\
                .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                .limit(limit)

        docs = ref.stream()
        alerts = [doc.to_dict() for doc in docs]

        return {"status": "success", "count": len(alerts), "alerts": alerts}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Convenience wrappers ─────────────────────────────────────────────────────
def log_rate_query(agent: str, corridor: str, query: str) -> dict:
    return log_event(agent, "rate_query", corridor=corridor, user_query=query)

def log_compliance_check(agent: str, corridor: str, result: str) -> dict:
    return log_event(agent, "compliance_check", corridor=corridor, response_summary=result)

def log_error(agent: str, error_msg: str, corridor: str = None) -> dict:
    return log_event(agent, "error", corridor=corridor,
                     response_summary=error_msg, severity="ERROR")
