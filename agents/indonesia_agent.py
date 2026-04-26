from google import genai
from google.cloud import firestore
import os
import json
import re
from datetime import datetime

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
db = firestore.Client(project="remitiq-agent", database="remitiq-db")

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.0-flash",
]

def get_corridor_rules() -> dict:
    try:
        doc = db.collection("corridor_rules").document("ID").get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"Firestore error: {e}")
    return {}

SYSTEM_PROMPT = """You are RemitIQ Indonesia Expert Agent.
Follow Bank Indonesia (BI) regulations and OJK guidelines.

SOURCE DETECTION (critical):
- If user is in Malaysia: Apply BNM RM 5,000 daily limit
- If user is in KSA: Ask about Iqama status
- If user is in UAE: Mention WPS compliance
- If user is in HKG: Apply HKD 50,000 daily limit
- If user is in SGP: Mention PayNow-to-QRIS option

RULES:
- BI-FAST: Real-time transfer — max IDR 250 juta
- E-wallet (GoPay/Dana/OVO): Max IDR 20 juta
- PPATK: Mandatory report above IDR 100 juta
- OJK: Always recommend licensed PJPUR channels only
- BP2MI: PMI workers entitled to fee waiver — always mention
- QRIS: Recommend for small transfers
- JISDOR: Always cite bi.go.id as rate reference

CROSS-TALK DETECTION:
- If user mentions "Peso/PHP/BSP/Philippines/GCash" → say:
  "Ini sepertinya koridor Filipina. Mau pindah koridor?"
- If user mentions "Rupee/PKR/SBP/Pakistan/CNIC" → say:
  "Ini koridor Pakistan. Mau switch?"
- If user mentions "Taka/BDT/Bangladesh/bKash" → say:
  "Ini koridor Bangladesh. Pindah koridor?"
- If user writes in Tagalog → say:
  "It seems you need Philippines corridor. Would you like to switch?"
- If user writes in Urdu → say:
  "Lagta hai aap Pakistan corridor chahte hain. Switch karein?"

LANGUAGE:
- Bahasa Indonesia → respond Bahasa
- English → respond English
- Mixed → respond mixed
- Always use respectful "Bapak/Ibu"

DISCLAIMER (mandatory every response):
"⚠️ Catatan: Kurs bersifat indikatif. Sumber: bi.go.id.
RemitIQ Pro tidak menjamin eksekusi pada kurs ini.
Harap verifikasi dengan penyedia layanan."

NEVER:
- Quote guaranteed rates
- Recommend non-OJK licensed channels
- Skip BP2MI fee waiver for PMI queries
- Skip PPATK warning for large transfers

RESPONSE FORMAT (JSON only):
{
  "language_detected": "bahasa/english/mixed",
  "source_country": "MYS/KSA/UAE/HKG/SGP/other",
  "corridor": "MYS→ID/KSA→ID/etc",
  "cross_talk_detected": false,
  "cross_talk_message": null,
  "jisdor_reference": "Check bi.go.id for today's rate",
  "rate_guidance": "...",
  "bi_fast_eligible": true,
  "compliance_notes": "...",
  "recommended_channels": ["..."],
  "pmi_tip": "...",
  "disclaimer": "⚠️ Kurs bersifat indikatif. Sumber: bi.go.id.",
  "response": "full natural language response"
}

Return ONLY valid JSON. No markdown. No text outside JSON."""

def process_indonesia_query(user_input: str, source_country: str = None, corridor: str = None) -> dict:
    last_error = None
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    rules = get_corridor_rules()
    rules_context = f"\nFirestore Rules: {json.dumps(rules)}" if rules else ""
    corridor_context = f"\nCorridor: {corridor}" if corridor else ""
    source_context = f"\nUser source country: {source_country}" if source_country else ""

    full_input = f"User query: {user_input}{source_context}{corridor_context}{rules_context}\nTimestamp: {timestamp}"

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
            data["agent"] = "indonesia_agent"
            data["timestamp"] = timestamp
            data["rules_loaded"] = bool(rules)
            try:
                from fortress_logger import log_event
                log_event(
                    agent_name="indonesia_agent",
                    event_type="rate_query",
                    corridor=corridor or data.get("corridor", "unknown"),
                    user_query=user_input[:100],
                    response_summary=data.get("fee_guidance", "")[:100],
                    severity="INFO"
                )
            except Exception:
                pass
            return data
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "agent": "indonesia_agent",
        "language_detected": "bahasa",
        "corridor": corridor or "unknown",
        "cross_talk_detected": False,
        "jisdor_reference": "Cek bi.go.id untuk kurs hari ini",
        "rate_guidance": "Layanan sedang tidak tersedia",
        "bi_fast_eligible": False,
        "compliance_notes": "Konsultasi langsung dengan Bank Indonesia: bi.go.id",
        "recommended_channels": ["BRI", "BNI", "Mandiri"],
        "pmi_tip": "Selalu gunakan channel resmi OJK",
        "disclaimer": "⚠️ Kurs bersifat indikatif. Sumber: bi.go.id.",
        "response": f"Mohon maaf, ada gangguan teknis. Error: {last_error}",
        "error": last_error
    }

def get_indonesia_corridors() -> list:
    return [
        {"from": "MYS", "to": "ID", "currency": "MYR→IDR", "channels": ["Maybank", "CIMB", "Wise"]},
        {"from": "KSA", "to": "ID", "currency": "SAR→IDR", "channels": ["Al Rajhi", "STC Pay", "Western Union"]},
        {"from": "UAE", "to": "ID", "currency": "AED→IDR", "channels": ["LuLu Exchange", "Al Ansari", "Wise"]},
        {"from": "HKG", "to": "ID", "currency": "HKD→IDR", "channels": ["Wise", "Western Union", "Instarem"]},
        {"from": "SGP", "to": "ID", "currency": "SGD→IDR", "channels": ["PayNow", "Wise", "Instarem"]},
        {"from": "QAT", "to": "ID", "currency": "QAR→IDR", "channels": ["QNB", "Wise", "Western Union"]},
    ]
