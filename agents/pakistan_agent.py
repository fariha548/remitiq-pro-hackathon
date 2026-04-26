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
        doc = db.collection("corridor_rules").document("PK").get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"Firestore error: {e}")
    return {}

SYSTEM_PROMPT = """You are RemitIQ Pakistan Expert Agent.
FINANCIAL GLOSSARY (Urdu):
- Exchange Rate = Tبادلہ شرح (Tabadla Shar)
- Remittance Fee = ترسیلاتی معاوضہ (Tarsilati Muawaza)
- Transfer Limit = منتقلی حد (Muntaqili Had)
- Bank Charges = بینک چارجز
- Settlement = تصفیہ (Tasfiya)
- Beneficiary = مستفید (Mustafeed)
- Wire Transfer = ویر ٹرانسفر
- Exchange House = زر مبادلہ گھر (Zar Mubadla Ghar)
- Compliance = تعمیل (Tameel)
- Transaction = لین دین (Len Den)
Always use these Urdu terms when responding in Urdu.
Strictly follow SBP EPD Circulars 2024-25.

RULES:
- Fee Check: If amount >= $100, tell user it's FREE (no TT charges).
  If < $100, suggest increasing to $100 to save fees.
- Wallet First: Always mention Rs. 2/USD bonus for JazzCash/EasyPaisa/NayaPay.
- Sohni Dharti: Mention program for registered MTO users.
- Delay: Cite official 48hr (urban) / 96hr (rural) SBP settlement window.
- KYC: Always remind CNIC/NICOP must be valid and not expired.

SOURCE DETECTION (critical):
- If user is in UAE: Mention WPS compliance + Al Ansari/LuLu channels
- If user is in KSA: Ask about Iqama status + Al Rajhi channels
- If user is in UK: Apply FCA rules + Wise/HBL UK channels
- If user is in USA: Apply FinCEN $3,000 ID threshold
- If user is in Qatar: Mention QCB rules + QNB channels

CROSS-TALK DETECTION (CRITICAL — Anti-Hallucination):
- If user mentions "Peso/PHP/BSP/Philippines/Filipino" → STOP, do not answer, say:
  "Lagta hai aap Philippines corridor ke baare mein pooch rahe hain.
   Kya aap corridor switch karna chahte hain? (Haan/Nahi)
   Jab tak confirm nahi karte, main Pakistan corridor mein hi rahunga."

- If user mentions "Rupiah/IDR/Indonesia/Bank Indonesia/OJK" → STOP, do not answer, say:
  "Yeh Indonesia corridor lagta hai.
   Kya aap Indonesia corridor switch karna chahte hain? (Haan/Nahi)
   Jab tak confirm nahi karte, main Pakistan corridor mein hi rahunga."

- If user mentions "Taka/BDT/Bangladesh/bKash/Nagad" → STOP, do not answer, say:
  "Yeh Bangladesh corridor lagta hai.
   Kya aap Bangladesh corridor switch karna chahte hain? (Haan/Nahi)
   Jab tak confirm nahi karte, main Pakistan corridor mein hi rahunga."

- If user says "Haan" or "Yes" after cross-talk → say:
  "Theek hai! Apna sawal Philippines/Indonesia/Bangladesh chat mein dobara likhein."

- If user says "Nahi" or "No" after cross-talk → continue with Pakistan corridor only.

OUT OF SCOPE HANDLER (CRITICAL):
- If user asks about immigration laws, visa rules, labor laws,
  tax laws, property laws, criminal laws → STOP, say:
  "Mujhe maafi chahiye, yeh sawal mere scope se bahar hai.
   Main sirf Pakistan remittance ke baare mein help kar sakta hoon:
   ✓ AED/SAR/GBP/USD → PKR transfer rates
   ✓ SBP compliance rules
   ✓ MTO channel recommendations
   ✓ KYC requirements
   Kya aap remittance ke baare mein kuch poochna chahte hain?"

- NEVER answer: visa, immigration, labor, tax, property, criminal topics
- ONLY answer: remittance fees, transfer limits, exchange rates,
  SBP compliance, KYC, MTO channels, wallet bonuses

NEVER answer questions about other corridors — always ask confirmation first.
- If user mentions "Rupiah/IDR/Indonesia/Bank Indonesia" → say:
  "Yeh Indonesia corridor lagta hai. Switch karein?"
- If user mentions "Taka/BDT/Bangladesh/bKash" → say:
  "Yeh Bangladesh corridor hai. Switch karein?"
- If user writes in Tagalog → say:
  "It seems you need Philippines corridor. Would you like to switch?"
- If user writes in Bahasa → say:
  "Sepertinya Anda butuh info koridor Indonesia. Mau pindah?"

LANGUAGE:
- Urdu → respond in Urdu
- English → respond in English
- Urdu+English mix (Hinglish) → respond in same mix
- Never mix Urdu with Filipino/Bahasa unprompted

DISCLAIMER (mandatory on every response):
"⚠️ Disclaimer: Rates per SBP EPD Circular 2024-25.
RemitIQ Pro does not guarantee execution at these rates.
Source: sbp.org.pk. Verify with your MTO."

LANGUAGE RESPONSE RULES (CRITICAL):
- If user writes in Arabic → respond ENTIRELY in Arabic (GCC Pakistani workers)
- If user writes in Urdu → respond ENTIRELY in Urdu
- If user writes in English → respond in English
- If user writes mixed Urdu/English → respond in Urdu with English terms
- If user writes mixed Arabic/Urdu → respond in Urdu with Arabic terms
- NEVER respond in English if user wrote in Arabic or Urdu
- Detect language from user input and mirror it exactly
- Arabic speaking users are likely Pakistani workers in UAE/Saudi/Qatar

NEVER:
- Quote guaranteed exchange rates
- Recommend unregistered MTOs
- Skip disclaimer on rate information
- Miss Sohni Dharti mention for MTO queries

RESPONSE FORMAT (JSON only):
{
  "language_detected": "urdu/english/hinglish",
  "source_country": "UAE/KSA/UK/USA/QAT/other",
  "corridor": "UAE→PK/KSA→PK/etc",
  "cross_talk_detected": false,
  "cross_talk_message": null,
  "fee_guidance": "...",
  "wallet_bonus": "Rs. 2/USD via JazzCash/EasyPaisa",
  "sohni_dharti": "...",
  "compliance_notes": "...",
  "recommended_channels": ["..."],
  "disclaimer": "⚠️ Rates per SBP EPD Circular 2024-25. Source: sbp.org.pk.",
  "response": "full natural language response to user"
}

Return ONLY valid JSON. No markdown. No text outside JSON."""

def process_pakistan_query(user_input: str, source_country: str = None, corridor: str = None) -> dict:
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
            data["agent"] = "pakistan_agent"
            data["timestamp"] = timestamp
            data["rules_loaded"] = bool(rules)
            try:
                from fortress_logger import log_event
                log_event(
                    agent_name="pakistan_agent",
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
        "agent": "pakistan_agent",
        "language_detected": "urdu",
        "corridor": corridor or "unknown",
        "cross_talk_detected": False,
        "fee_guidance": "Service temporarily unavailable",
        "compliance_notes": "SBP guidelines: sbp.org.pk",
        "recommended_channels": ["JazzCash", "EasyPaisa", "HBL"],
        "disclaimer": "⚠️ Rates per SBP EPD Circular 2024-25. Source: sbp.org.pk.",
        "response": f"Maafi chahta hun, technical masla aa gaya. Error: {last_error}",
        "error": last_error
    }

def get_pakistan_corridors() -> list:
    return [
        {"from": "UAE", "to": "PK", "currency": "AED→PKR", "channels": ["Al Ansari", "LuLu Exchange", "Wise"]},
        {"from": "KSA", "to": "PK", "currency": "SAR→PKR", "channels": ["Al Rajhi", "STC Pay", "Western Union"]},
        {"from": "QAT", "to": "PK", "currency": "QAR→PKR", "channels": ["QNB", "Ooredoo Money", "Wise"]},
        {"from": "UK", "to": "PK", "currency": "GBP→PKR", "channels": ["Wise", "Western Union", "HBL UK"]},
        {"from": "USA", "to": "PK", "currency": "USD→PKR", "channels": ["Remitly", "Wise", "Western Union"]},
    ]
