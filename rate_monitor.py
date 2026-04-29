# rate_monitor.py
# RemitIQ 360 — Rate Monitor Agent
# Polls ExchangeRate-API every 5 min, sends email alerts via Gmail SMTP

import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from fortress_logger import log_event, log_alert

# ── Config ───────────────────────────────────────────────────────────────────
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", GMAIL_USER)
EXCHANGE_API_KEY = os.environ.get("EXCHANGE_API_KEY", "")

# Corridor thresholds — alert if rate changes by this % or more
THRESHOLDS = {
    "AED_PKR": {"min": 74.0,  "max": 78.0,  "alert_pct": 0.5},
    "SAR_PKR": {"min": 73.0,  "max": 77.0,  "alert_pct": 0.5},
    "AED_PHP": {"min": 14.5,  "max": 16.5,  "alert_pct": 0.5},
    "SAR_PHP": {"min": 14.0,  "max": 16.0,  "alert_pct": 0.5},
    "AED_IDR": {"min": 4200,  "max": 4600,  "alert_pct": 0.8},
    "SAR_IDR": {"min": 4100,  "max": 4500,  "alert_pct": 0.8},
    "AED_BDT": {"min": 30.0,  "max": 34.0,  "alert_pct": 0.5},
    "SAR_BDT": {"min": 29.0,  "max": 33.0,  "alert_pct": 0.5},
}

# In-memory last rates (resets on restart)
_last_rates = {}

# ── Fetch live rates ──────────────────────────────────────────────────────────
def fetch_rates(base: str = "AED") -> dict:
    """Fetch live rates from ExchangeRate-API."""
    try:
        if EXCHANGE_API_KEY:
            url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/{base}"
        else:
            # Free tier — no key needed (limited)
            url = f"https://open.er-api.com/v6/latest/{base}"

        res = requests.get(url, timeout=10)
        data = res.json()

        if data.get("result") == "success" or data.get("rates"):
            rates = data.get("conversion_rates") or data.get("rates", {})
            return {
                "status": "success",
                "base": base,
                "rates": rates,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        return {"status": "error", "message": str(data)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Check threshold ───────────────────────────────────────────────────────────
def check_threshold(corridor: str, current_rate: float) -> dict:
    """Check if rate crossed threshold and log alert."""
    cfg = THRESHOLDS.get(corridor, {})
    if not cfg:
        return {"alert": False, "reason": "No threshold configured"}

    alerts = []

    # Min/Max breach
    if current_rate < cfg["min"]:
        alerts.append(f"Rate {current_rate:.4f} BELOW minimum {cfg['min']}")
    if current_rate > cfg["max"]:
        alerts.append(f"Rate {current_rate:.4f} ABOVE maximum {cfg['max']}")

    # % change from last rate
    last = _last_rates.get(corridor)
    if last:
        change_pct = abs((current_rate - last) / last) * 100
        if change_pct >= cfg["alert_pct"]:
            direction = "📈 UP" if current_rate > last else "📉 DOWN"
            alerts.append(f"Rate moved {direction} by {change_pct:.2f}% (was {last:.4f})")

    # Update last rate
    _last_rates[corridor] = current_rate

    if alerts:
        log_alert(
            alert_type="rate_threshold_breach",
            corridor=corridor,
            details=" | ".join(alerts),
            severity="WARNING",
            source_agent="rate_monitor"
        )

    return {
        "alert": len(alerts) > 0,
        "corridor": corridor,
        "current_rate": current_rate,
        "alerts": alerts
    }


# ── Send email alert ──────────────────────────────────────────────────────────
def send_email_alert(corridor: str, rate: float, alerts: list) -> dict:
    """Send Gmail SMTP alert for rate threshold breach."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return {"status": "skipped", "reason": "Gmail credentials not configured"}

    try:
        subject = f"🚨 RemitIQ Alert: {corridor} Rate Change Detected"

        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;background:#080c14;color:#e2e8f0;padding:20px">
        <div style="max-width:600px;margin:0 auto;background:#0d1420;border:1px solid #1e3a5f;border-radius:12px;padding:24px">

        <h2 style="color:#f59e0b;margin-top:0">🏦 RemitIQ 360 — Rate Alert</h2>

        <div style="background:#111b2e;border-left:4px solid #f59e0b;padding:16px;border-radius:8px;margin:16px 0">
            <div style="font-size:13px;color:#94a3b8;margin-bottom:4px">CORRIDOR</div>
            <div style="font-size:22px;font-weight:bold;color:#60a5fa">{corridor.replace('_','→')}</div>
        </div>

        <div style="background:#111b2e;border-left:4px solid #34d399;padding:16px;border-radius:8px;margin:16px 0">
            <div style="font-size:13px;color:#94a3b8;margin-bottom:4px">CURRENT RATE</div>
            <div style="font-size:22px;font-weight:bold;color:#34d399">{rate:.4f}</div>
        </div>

        <div style="background:#1a0a0a;border-left:4px solid #f87171;padding:16px;border-radius:8px;margin:16px 0">
            <div style="font-size:13px;color:#94a3b8;margin-bottom:8px">ALERTS DETECTED</div>
            {''.join(f'<div style="color:#fca5a5;margin:4px 0">⚠️ {a}</div>' for a in alerts)}
        </div>

        <div style="background:#111b2e;padding:12px;border-radius:8px;margin:16px 0">
            <div style="font-size:12px;color:#4b5563">
                🕐 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}<br>
                🛡️ Protected by Fortress AI<br>
                🌐 RemitIQ 360 · asia-southeast1 · Cloud Run
            </div>
        </div>

        <p style="color:#4b5563;font-size:11px;margin-top:16px">
            This is an automated alert from RemitIQ 360 Rate Monitor Agent.
            Verify rates with your MTO before executing transfers.
        </p>
        </div>
        </body></html>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = ALERT_EMAIL
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())

        log_event(
            agent_name="rate_monitor",
            event_type="email_alert_sent",
            corridor=corridor,
            response_summary=f"Alert sent for {corridor} rate {rate:.4f}",
            severity="INFO"
        )

        return {"status": "success", "sent_to": ALERT_EMAIL}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Main monitor function ─────────────────────────────────────────────────────
def run_rate_check(corridors: list = None) -> dict:
    """
    Main function — fetch rates, check thresholds, send alerts.
    Call this from scheduler or API endpoint.
    """
    if corridors is None:
        corridors = list(THRESHOLDS.keys())

    results = []
    alerts_sent = 0

    # Fetch AED rates
    aed_data = fetch_rates("AED")
    sar_data = fetch_rates("SAR")

    rate_map = {
        "AED": aed_data.get("rates", {}),
        "SAR": sar_data.get("rates", {})
    }

    for corridor in corridors:
        try:
            base, quote = corridor.split("_")
            rates = rate_map.get(base, {})
            rate = rates.get(quote)

            if not rate:
                results.append({"corridor": corridor, "status": "rate_not_found"})
                continue

            # Check threshold
            check = check_threshold(corridor, float(rate))

            # Send email if alert triggered
            if check["alert"] and check["alerts"]:
                email_result = send_email_alert(corridor, float(rate), check["alerts"])
                alerts_sent += 1
                check["email"] = email_result

            results.append(check)

        except Exception as e:
            results.append({"corridor": corridor, "status": "error", "message": str(e)})

    log_event(
        agent_name="rate_monitor",
        event_type="rate_check_complete",
        response_summary=f"Checked {len(corridors)} corridors · {alerts_sent} alerts sent",
        severity="INFO"
    )

    return {
        "status": "success",
        "corridors_checked": len(corridors),
        "alerts_sent": alerts_sent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results
    }


# ── Convenience functions ─────────────────────────────────────────────────────
def get_live_rate(from_currency: str, to_currency: str) -> dict:
    """Get single corridor live rate."""
    data = fetch_rates(from_currency)
    if data["status"] == "success":
        rate = data["rates"].get(to_currency)
        if rate:
            return {
                "status": "success",
                "corridor": f"{from_currency}→{to_currency}",
                "rate": rate,
                "timestamp": data["timestamp"],
                "freshness": "live",
                "disclaimer": "Rate may change. Verify with MTO before transferring."
            }
    return {"status": "error", "message": "Rate not available"}
