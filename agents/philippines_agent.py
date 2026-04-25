from google import genai
import os
import json
import re

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.0-flash",
]

SYSTEM_PROMPT = """You are RemitIQ Philippines Agent — AI-powered remittance intelligence for Filipino migrant workers in GCC/MENA.

You support these corridors:
- PH→UAE (AED to PHP) — Dubai, Abu Dhabi workers
- PH→KSA (SAR to PHP) — Riyadh, Jeddah workers  
- PH→HKG (HKD to PHP) — Hong Kong domestic workers
- PH→QAT (QAR to PHP) — Qatar workers
- PH→KWT (KWD to PHP) — Kuwait workers

Regulatory knowledge:
- BSP (Bangko Sentral ng Pilipinas) — remittance regulations
- POEA (Philippine Overseas Employment Administration) — OFW protections
- AMLA (Anti-Money Laundering Act) — AML compliance
- Balikbayan Box rules — exempt from duties
- OFW remittance limits: No cap but >PHP 500,000 requires declaration
- GCash, Maya, LandBank, BDO, BPI — popular receive channels

Language support: English, Tagalog, Filipino

Rate intelligence:
- Always advise to compare rates across: Western Union, Remitly, Wise, LuLu Exchange, Al Ansari
- Typical spread: 0.5% to 2.5% above mid-market rate
- Best times to send: Tuesday-Thursday (lower spreads)

Respond in the same language the user writes in.
If Tagalog: respond in Tagalog.
If English: respond in English.
If mixed: respond in mixed (Taglish).

Always include:
1. Current corridor rate context
2. BSP compliance reminder if amount > PHP 500,000
3. Recommended channels for that corridor
4. Any OFW-specific protections relevant

Format response as JSON:
{
  "language_detected": "tagalog/english/taglish",
  "corridor": "PH→UAE",
  "rate_guidance": "...",
  "compliance_notes": "...",
  "recommended_channels": ["...", "..."],
  "ofw_tip": "...",
  "response": "full natural language response to user"
}

Return ONLY valid JSON. No markdown. No explanation outside JSON."""

def process_philippines_query(user_input: str, corridor: str = None) -> dict:
    last_error = None

    corridor_context = f"\nCorridor focus: {corridor}" if corridor else ""
    full_input = f"User query: {user_input}{corridor_context}"

    for model_name in MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=SYSTEM_PROMPT + "\n\n" + full_input
            )
            raw = response.text.strip()
            raw = re.sub(r'```json|```', '', raw).strip()
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
            data = json.loads(raw)
            data["model_used"] = model_name
            data["agent"] = "philippines_agent"
            return data
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "agent": "philippines_agent",
        "language_detected": "english",
        "corridor": corridor or "unknown",
        "rate_guidance": "Service temporarily unavailable",
        "compliance_notes": "Please consult BSP guidelines directly",
        "recommended_channels": ["GCash", "Maya", "BDO"],
        "ofw_tip": "Always compare rates before sending",
        "response": f"Pasensya na, may technical issue. Error: {last_error}",
        "error": last_error
    }

def get_supported_corridors() -> list:
    return [
        {"from": "UAE", "to": "PH", "currency": "AED→PHP", "popular_channels": ["LuLu Exchange", "Al Ansari", "Wise"]},
        {"from": "KSA", "to": "PH", "currency": "SAR→PHP", "popular_channels": ["Al Rajhi", "STC Pay", "Remitly"]},
        {"from": "HKG", "to": "PH", "currency": "HKD→PHP", "popular_channels": ["Wise", "Western Union", "GCash"]},
        {"from": "QAT", "to": "PH", "currency": "QAR→PHP", "popular_channels": ["QNB", "Ooredoo Money", "Wise"]},
        {"from": "KWT", "to": "PH", "currency": "KWD→PHP", "popular_channels": ["NBK", "Zain Cash", "Remitly"]},
    ]
