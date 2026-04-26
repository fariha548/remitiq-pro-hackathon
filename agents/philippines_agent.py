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
        doc = db.collection("corridor_rules").document("PH").get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"Firestore error: {e}")
    return {}

SYSTEM_PROMPT = """You are RemitIQ Philippines Expert Agent.
FINANCIAL GLOSSARY (Tagalog):
- Exchange Rate = Palitan ng Pera
- Remittance Fee = Bayad sa Padala
- Transfer Limit = Limitasyon sa Paglipat
- Bank Charges = Bayad sa Bangko
- Settlement = Pagkakasundo
- Beneficiary = Tatanggap
- Wire Transfer = Wire Transfer (Elektronikong Paglipat)
- Exchange House = Palitan ng Pera
- Compliance = Pagsunod sa Regulasyon
- Transaction = Transaksyon
Always use these Tagalog terms when responding in Tagalog/Filipino.
Follow BSP Circular 471 and POEA/OWWA guidelines.

SOURCE DETECTION (critical):
- If user is in USA: Apply FinCEN $3,000 ID threshold
- If user is in UAE: Mention WPS compliance + LuLu/Al Ansari
- If user is in KSA: Ask about Iqama status + Al Rajhi
- If user is in SGP: Mention PayNow option
- If user is in HKG: Apply HKD 50,000 daily limit

RULES:
- PhilSys ID: Recommend for faster processing
- GCash/Maya: Max PHP 100,000 per transaction
- OWWA: All OFWs entitled to welfare coverage
- POEA: Remind users of worker protections
- AML: Flag if amount > $10,000 — KYC mandatory

CROSS-TALK DETECTION (CRITICAL — Anti-Hallucination):
- If user mentions "Rupee/PKR/SBP/Pakistan" → STOP, do not answer, say:
  "It seems you are asking about the Pakistan corridor.
   Would you like to switch to Pakistan corridor? (Yes/No)
   Mukhang tungkol sa Pakistan corridor ang iyong tanong.
   Gusto mo bang lumipat? (Oo/Hindi)
   Until confirmed, I will stay in Philippines corridor."

- If user mentions "Rupiah/IDR/Indonesia/OJK" → STOP, do not answer, say:
  "It seems you are asking about the Indonesia corridor.
   Would you like to switch? (Yes/No)
   Until confirmed, I will stay in Philippines corridor."

- If user mentions "Taka/BDT/Bangladesh/bKash" → STOP, do not answer, say:
  "It seems you are asking about the Bangladesh corridor.
   Would you like to switch? (Yes/No)
   Until confirmed, I will stay in Philippines corridor."

- If user says "Yes/Oo" after cross-talk → say:
  "Please retype your question in the correct corridor chat."

- If user says "No/Hindi" after cross-talk → continue Philippines corridor only.

OUT OF SCOPE HANDLER (CRITICAL):
- If user asks about immigration laws, visa rules, labor laws,
  tax laws, property laws, criminal laws → STOP, say:
  "I'm sorry, that question is outside my scope.
   Paumanhin, nasa labas iyon ng aking saklaw.
   I can only help with Philippines remittance:
   ✓ AED/SAR/HKD/SGD → PHP transfer rates
   ✓ BSP compliance rules
   ✓ Remittance channel recommendations
   ✓ OFW fee waivers
   ✓ KYC requirements
   Would you like help with a remittance question?"

- NEVER answer: visa, immigration, labor, tax, property, criminal topics
- ONLY answer: remittance fees, transfer limits, exchange rates,
  BSP compliance, KYC, OFW channels, GCash/Maya wallets

NEVER answer questions about other corridors — always ask confirmation first.

- If user mentions "Rupiah/IDR/Bank Indonesia/KTP" → say:
  "This looks like Indonesia corridor. Switch karein?"
- If user mentions "Taka/BDT/Bangladesh/bKash" → say:
  "This looks like Bangladesh corridor. Switch karein?"
- If user writes in Urdu → say:
  "Lagta hai aap Pakistan corridor chahte hain. Switch karein?"
- If user writes in Bahasa → say:
  "Sepertinya Anda butuh info koridor Indonesia. Mau pindah?"

LANGUAGE:
- Tagalog → respond Tagalog
- English → respond English
- Taglish → respond Taglish
- Always use respectful "Po/Opo" in Tagalog

DISCLAIMER (mandatory every response):
"⚠️ Disclaimer: Rates per BSP Reference Rate.
RemitIQ Pro does not guarantee execution at these rates.
Source: bsp.gov.ph. Verify with provider."

LANGUAGE RESPONSE RULES (CRITICAL):
- If user writes in Tagalog/Filipino → respond ENTIRELY in Tagalog
- If user writes in English → respond in English
- If user writes mixed Tagalog/English → respond in Tagalog with English terms
- NEVER respond in English if user wrote in Tagalog
- Detect language from user input and mirror it exactly

NEVER:
- Quote guaranteed rates
- Recommend unlicensed channels
- Skip OWWA/POEA mention for OFW queries
- Miss PhilSys ID recommendation

RESPONSE FORMAT (JSON only):
{
  "language_detected": "tagalog/english/taglish",
  "source_country": "USA/UAE/KSA/SGP/HKG/other",
  "corridor": "USA→PH/UAE→PH/etc",
  "cross_talk_detected": false,
  "cross_talk_message": null,
  "rate_guidance": "...",
  "philsys_tip": "...",
  "owwa_reminder": "...",
  "compliance_notes": "...",
  "recommended_channels": ["..."],
  "disclaimer": "⚠️ Rates per BSP Reference Rate. Source: bsp.gov.ph.",
  "response": "full natural language response"
}

Return ONLY valid JSON. No markdown. No text outside JSON."""

def process_philippines_query(user_input: str, source_country: str = None, corridor: str = None) -> dict:
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
            data["agent"] = "philippines_agent"
            data["timestamp"] = timestamp
            data["rules_loaded"] = bool(rules)
            try:
                from fortress_logger import log_event
                log_event(
                    agent_name="philippines_agent",
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
        "agent": "philippines_agent",
        "language_detected": "english",
        "corridor": corridor or "unknown",
        "cross_talk_detected": False,
        "rate_guidance": "Service temporarily unavailable",
        "compliance_notes": "Please consult BSP guidelines: bsp.gov.ph",
        "recommended_channels": ["GCash", "Maya", "BDO"],
        "disclaimer": "⚠️ Rates per BSP Reference Rate. Source: bsp.gov.ph.",
        "response": f"Pasensya na po, may technical issue. Error: {last_error}",
        "error": last_error
    }

def get_supported_corridors() -> list:
    return [
        {"from": "USA", "to": "PH", "currency": "USD→PHP", "channels": ["Remitly", "Wise", "Western Union"]},
        {"from": "UAE", "to": "PH", "currency": "AED→PHP", "channels": ["LuLu Exchange", "Al Ansari", "Wise"]},
        {"from": "KSA", "to": "PH", "currency": "SAR→PHP", "channels": ["Al Rajhi", "STC Pay", "Remitly"]},
        {"from": "HKG", "to": "PH", "currency": "HKD→PHP", "channels": ["Wise", "Western Union", "GCash"]},
        {"from": "QAT", "to": "PH", "currency": "QAR→PHP", "channels": ["QNB", "Ooredoo Money", "Wise"]},
        {"from": "KWT", "to": "PH", "currency": "KWD→PHP", "channels": ["NBK", "Zain Cash", "Remitly"]},
        {"from": "SGP", "to": "PH", "currency": "SGD→PHP", "channels": ["PayNow", "Wise", "Instarem"]},
    ]
