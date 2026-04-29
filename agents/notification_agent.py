import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_PASS")
APP_URL = "https://fortress-ai-remitiq-360-1026593477381.asia-southeast1.run.app"

def send_rate_alert(to_email, alerts):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "⚡ RemitIQ 360 — Rate Alert"
    msg["From"] = GMAIL_USER
    msg["To"] = to_email

    rows = "".join([f"<tr><td>{a['corridor']}</td><td><b>{a['rate']}</b></td><td>{a['threshold']}</td></tr>" for a in alerts])

    html = f"""
    <html><body style="font-family:Arial;background:#0a0a0f;color:#fff;padding:20px">
    <h2 style="color:#ef4444">🔔 RemitIQ 360 Rate Alert</h2>
    <p>Following corridors have crossed your threshold:</p>
    <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%">
      <tr style="background:#1a1a2e"><th>Corridor</th><th>Live Rate</th><th>Threshold</th></tr>
      {rows}
    </table>
    <br>
    <a href="{APP_URL}" style="background:#ef4444;color:#fff;padding:10px 20px;text-decoration:none;border-radius:5px">
      Open RemitIQ 360
    </a>
    <p style="color:#666;font-size:12px;margin-top:20px">RemitIQ 360 — Fortress AI Monitoring</p>
    </body></html>
    """

    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, to_email, msg.as_string())
    return f"Alert email sent to {to_email}"

def send_transaction_confirmation(to_email, amount, corridor, mto):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "✅ RemitIQ 360 — Transaction Confirmed"
    msg["From"] = GMAIL_USER
    msg["To"] = to_email

    html = f"""
    <html><body style="font-family:Arial;background:#0a0a0f;color:#fff;padding:20px">
    <h2 style="color:#22c55e">✅ Transaction Confirmation</h2>
    <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%">
      <tr><td>Amount</td><td><b>{amount}</b></td></tr>
      <tr><td>Corridor</td><td><b>{corridor}</b></td></tr>
      <tr><td>MTO</td><td><b>{mto}</b></td></tr>
    </table>
    <br>
    <a href="{APP_URL}" style="background:#22c55e;color:#fff;padding:10px 20px;text-decoration:none;border-radius:5px">
      Track on RemitIQ 360
    </a>
    </body></html>
    """

    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, to_email, msg.as_string())
    return f"Confirmation email sent to {to_email}"
