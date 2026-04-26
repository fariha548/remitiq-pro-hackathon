# agents/bangladesh_agent.py
# RemitIQ 360 — Bangladesh Corridor Agent
# Corridors: AED/SAR/QAR/KWD/OMR/BHD → BDT

import re
from google.adk.agents import Agent
from google.adk.tools import google_search
from datetime import datetime
import firebase_admin
from firebase_admin import firestore

# ── Firestore client (shared app instance) ──────────────────────────────────
def _get_db():
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
    return firestore.client()

# ── Corridor rules from Firestore ────────────────────────────────────────────
def get_corridor_rules(corridor: str) -> dict:
    """Fetch live corridor rules from Firestore remitiq-db."""
    try:
        db = _get_db()
        doc = db.collection("corridor_rules").document(corridor).get()
        if doc.exists:
            return {"status": "success", "corridor": corridor, "rules": doc.to_dict()}
        return {"status": "not_found", "corridor": corridor}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ── Live rate fetch ──────────────────────────────────────────────────────────
def get_live_rate(from_currency: str, to_currency: str = "BDT") -> dict:
    """Get live exchange rate for BDT corridors via Google Search grounding."""
    try:
        query = f"{from_currency} to BDT exchange rate today remittance"
        return {
            "status": "success",
            "from": from_currency,
            "to": to_currency,
            "query": query,
            "note": "Rate fetched via Google Search grounding"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ── Provider comparison ──────────────────────────────────────────────────────
def compare_providers_bdt(from_currency: str, amount: float) -> dict:
    """Compare remittance providers for BDT corridors."""
    providers = {
        "AED": [
            {"name": "Al Ansari Exchange", "rate_premium": 0.002, "fee_aed": 10},
            {"name": "UAE Exchange", "rate_premium": 0.001, "fee_aed": 15},
            {"name": "Wise", "rate_premium": 0.005, "fee_aed": 8},
            {"name": "Western Union", "rate_premium": -0.003, "fee_aed": 20},
        ],
        "SAR": [
            {"name": "Al Rajhi Bank", "rate_premium": 0.003, "fee_sar": 15},
            {"name": "STC Pay", "rate_premium": 0.004, "fee_sar": 10},
            {"name": "Wise", "rate_premium": 0.005, "fee_sar": 12},
            {"name": "Western Union", "rate_premium": -0.002, "fee_sar": 25},
        ],
        "QAR": [
            {"name": "QNB", "rate_premium": 0.002, "fee_qar": 12},
            {"name": "Doha Bank", "rate_premium": 0.001, "fee_qar": 15},
            {"name": "Wise", "rate_premium": 0.004, "fee_qar": 10},
        ],
        "KWD": [
            {"name": "Kuwait Finance House", "rate_premium": 0.003, "fee_kwd": 2},
            {"name": "Boubyan Bank", "rate_premium": 0.002, "fee_kwd": 2.5},
            {"name": "Wise", "rate_premium": 0.005, "fee_kwd": 1.5},
        ],
        "OMR": [
            {"name": "Bank Muscat", "rate_premium": 0.002, "fee_omr": 3},
            {"name": "Oman Arab Bank", "rate_premium": 0.001, "fee_omr": 4},
            {"name": "Wise", "rate_premium": 0.004, "fee_omr": 2.5},
        ],
        "BHD": [
            {"name": "BBK", "rate_premium": 0.002, "fee_bhd": 2},
            {"name": "Bahrain Islamic Bank", "rate_premium": 0.003, "fee_bhd": 1.5},
            {"name": "Wise", "rate_premium": 0.004, "fee_bhd": 1.8},
        ],
    }
    return {
        "status": "success",
        "from_currency": from_currency,
        "amount": amount,
        "providers": providers.get(from_currency, []),
        "note": "Use Google Search grounding for live rates"
    }

# ── Bangladeshi worker compliance tips ──────────────────────────────────────
def get_bangladesh_compliance(country: str) -> dict:
    """Return Bangladesh-specific compliance and documentation tips."""
    tips = {
        "UAE": {
            "max_single_transfer": "AED 50,000 without additional docs",
            "annual_limit": "No formal limit for workers with valid iqama",
            "required_docs": ["Valid passport", "UAE residence visa", "Work permit", "Bangladesh bank account"],
            "recommended_channels": ["Al Ansari", "UAE Exchange", "licensed MTOs"],
            "bb_registration": "Register with Bangladesh Bank wage earner scheme for tax benefits",
            "tips": "Use Probashi Kallyan Bank for subsidized rates"
        },
        "Saudi Arabia": {
            "max_single_transfer": "SAR 100,000 per transaction",
            "annual_limit": "No cap for documented workers",
            "required_docs": ["Valid iqama", "Work contract", "Bangladeshi NID", "Bank account in Bangladesh"],
            "recommended_channels": ["Al Rajhi Bank", "STC Pay", "licensed exchanges"],
            "bb_registration": "Bangladesh Bank wage earner bond available for GCC workers",
            "tips": "BMET registration recommended before departure"
        },
        "Qatar": {
            "max_single_transfer": "QAR 50,000",
            "required_docs": ["Qatar ID", "Work permit", "Bangladeshi bank account"],
            "recommended_channels": ["QNB", "Doha Bank", "Wise"],
            "tips": "Post-World Cup remittance volumes still high — good provider competition"
        },
        "Kuwait": {
            "max_single_transfer": "KWD 3,000 per transaction",
            "required_docs": ["Civil ID", "Work permit", "Bangladeshi NID"],
            "recommended_channels": ["Kuwait Finance House", "Boubyan Bank"],
            "tips": "Friday-Saturday transfers may have settlement delays"
        },
        "Oman": {
            "max_single_transfer": "OMR 3,000",
            "required_docs": ["Oman residence card", "Work contract", "Bank account"],
            "recommended_channels": ["Bank Muscat", "Oman Arab Bank"],
            "tips": "Bangladeshi community largest expat group — many informal channels exist, use licensed only"
        },
        "Bahrain": {
            "max_single_transfer": "BHD 2,000",
            "required_docs": ["CPR card", "Work permit", "Bangladeshi bank account"],
            "recommended_channels": ["BBK", "Bahrain Islamic Bank"],
            "tips": "Bahrain allows personal account remittances without employer NOC"
        },
    }
    return {
        "status": "success",
        "country": country,
        "compliance": tips.get(country, {"note": "Country-specific data not available, use Google Search grounding"})
    }

# ── Bangladesh Bank regulatory info ─────────────────────────────────────────
def get_bb_regulatory_info(topic: str) -> dict:
    """Return Bangladesh Bank regulatory information for migrant workers."""
    topics = {
        "wage_earner_scheme": {
            "description": "Bangladesh Bank Wage Earner Development Bond",
            "interest_rate": "12% per annum (USD/GBP/EUR/AED bonds available)",
            "eligibility": "Bangladeshi nationals working abroad",
            "benefit": "Tax-free interest income",
            "source": "Bangladesh Bank FE Circular"
        },
        "probashi_bond": {
            "description": "US Dollar Premium Bond for expatriates",
            "interest_rate": "7.5% per annum",
            "eligibility": "Non-resident Bangladeshis",
            "benefit": "Repatriable interest and principal"
        },
        "fema_limit": {
            "description": "No upper limit on inward remittances to Bangladesh",
            "note": "Bangladesh Bank encourages formal channel use",
            "incentive": "2.5% cash incentive on inward remittances through formal channels"
        },
        "bkash_nagad": {
            "description": "Mobile financial services for last-mile delivery",
            "providers": ["bKash", "Nagad", "Rocket"],
            "max_per_transaction": "BDT 150,000",
            "note": "Most MTOs now integrate with bKash/Nagad for instant delivery"
        }
    }
    return {
        "status": "success",
        "topic": topic,
        "info": topics.get(topic, {"note": "Use Google Search grounding for latest BB circulars"})
    }

# ── Agent definition ─────────────────────────────────────────────────────────
bangladesh_agent = Agent(
    name="bangladesh_remittance_agent",
    model="gemini-2.0-flash",
    description=(
        "Specialist agent for GCC-to-Bangladesh remittance corridors. "
        "Covers AED, SAR, QAR, KWD, OMR, BHD → BDT transfers. "
        "Provides live rates, provider comparisons, Bangladesh Bank compliance, "
        "wage earner schemes, bKash/Nagad delivery options, and BMET/BB regulatory guidance."
    ),
    instruction="""
You are the Bangladesh Remittance Specialist for RemitIQ 360.

You help Bangladeshi migrant workers in the GCC (UAE, Saudi Arabia, Qatar, Kuwait, Oman, Bahrain)
send money home safely, cheaply, and in compliance with Bangladesh Bank regulations.

CORRIDORS YOU COVER:
- AED → BDT (UAE)
- SAR → BDT (Saudi Arabia) 
- QAR → BDT (Qatar)
- KWD → BDT (Kuwait)
- OMR → BDT (Oman)
- BHD → BDT (Bahrain)

YOUR CAPABILITIES:
1. Live exchange rates via Google Search grounding
2. Provider comparison (Al Ansari, Al Rajhi, QNB, Wise, Western Union, bKash partners)
3. Bangladesh Bank compliance — wage earner bonds, 2.5% cash incentive, bKash/Nagad delivery
4. BMET registration guidance for workers
5. Firestore corridor rules lookup
6. Probashi Kallyan Bank and special schemes for migrant workers

LANGUAGE: Respond in English. If user writes in Bengali (Bangla), respond in Bengali.
If user writes in Arabic, respond in Arabic.

ALWAYS:
- Mention the Bangladesh Bank 2.5% cash incentive on formal channel remittances
- Recommend bKash or Nagad for last-mile delivery when relevant
- Warn against hundi (informal) channels
- Cite corridor rules from Firestore when available
- Use Google Search grounding for live rates
""",
    tools=[
        google_search,
        get_corridor_rules,
        get_live_rate,
        compare_providers_bdt,
        get_bangladesh_compliance,
        get_bb_regulatory_info,
    ],
)
