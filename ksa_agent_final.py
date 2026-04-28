# agents/ksa_agent.py
# RemitIQ 360 — Saudi Arabia (KSA) Corridor Agent  v3.0.0
# Pattern  : Google ADK Agent (same as bangladesh_agent.py)
# KB Level : v3 embedded knowledge — zero LLM hallucination
# Corridors: SAR → PKR / BDT / PHP / IDR
#
# Compliance coverage:
#   SAMA Circular 381000064902
#   Royal Decree M/113 (15% VAT on service fees)
#   Vision 2030 FSDP — STC Pay / Urpay / Mada priority
#   WPS — MoHRSD Decision No. 1/2595
#   SAMA AML/CFT Rules 2023 — CDD / Absher / EDD thresholds
#   FATF AML/CFT Recommendations (GCC context)
#   Fortress AI — Iqama PII masking + MENA scam detection

from __future__ import annotations

import re
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Any

from google.adk.agents import Agent
from google.adk.tools import google_search
import firebase_admin
from firebase_admin import firestore

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EMBEDDED KNOWLEDGE BASE — KSA Regulatory Intelligence
#  Source : SAMA · MoHRSD · Zakat Authority · Vision 2030 FSDP
#  Reviewed: Q1 2025
#  This KB is injected into every tool response so the LLM
#  always answers from authoritative data — never from hallucination.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KSA_KB = {
    "jurisdiction"  : "Kingdom of Saudi Arabia",
    "regulator"     : "SAMA — Saudi Arabian Monetary Authority",
    "kb_version"    : "Q1-2025",

    "vat": {
        "rate"      : 0.15,
        "basis"     : "SERVICE FEE ONLY — never on principal transfer amount",
        "legal_ref" : "Royal Decree M/113 · Zakat, Tax and Customs Authority",
        "example"   : "Fee 50 SAR → VAT 7.50 SAR. Your 1000 SAR transfer stays 1000 SAR.",
    },

    "cdd_thresholds": {
        "absher_sar"    : 20000,    # Iqama / Absher verification
        "enhanced_sar"  : 60000,    # Enhanced Due Diligence
        "branch_sar"    : 100000,   # Branch KYC mandatory
        "ctr_sar"       : 60000,    # Currency Transaction Report
        "legal_ref"     : "SAMA AML/CFT Rules — Circular 381000064902",
    },

    "rails": {
        "priority"  : ["STC_PAY", "URPAY", "MADA", "WIRE"],
        "STC_PAY"   : {"max_sar": 20000,  "daily": 60000,  "instant": True,  "note": "Best for migrant workers up to 20K SAR"},
        "URPAY"     : {"max_sar": 10000,  "daily": 30000,  "instant": True,  "note": "Worker-friendly, Urdu interface, instant"},
        "MADA"      : {"max_sar": 50000,  "daily": 100000, "instant": False, "note": "Debit-linked, bank settlement T+1"},
        "WIRE"      : {"max_sar": None,   "daily": None,   "instant": False, "note": "No cap — use for large/corporate"},
        "fsdp_ref"  : "Vision 2030 FSDP — digital payment rail priority targets",
    },

    "wps": {
        "authority"     : "Ministry of Human Resources & Social Development (MoHRSD)",
        "legal_ref"     : "Ministerial Decision No. 1/2595 (2013)",
        "applies_to"    : ["individual", "personal"],
        "brackets"      : [
            {"label": "LOW",  "min": 0,     "max": 2999,  "pct": 0.90},
            {"label": "MID",  "min": 3000,  "max": 9999,  "pct": 0.80},
            {"label": "HIGH", "min": 10000, "max": 29999, "pct": 0.70},
            {"label": "EXEC", "min": 30000, "max": None,  "pct": 0.60},
        ],
        "overage_action": "Request salary certificate or bank statement from sender.",
    },

    "fortress": {
        "pii_pattern"   : r"[12]\d{9}",    # 10-digit Iqama starting with 1 or 2
        "sensitivity"   : "HIGH",
        "scam_keywords" : [
            "emirates id update",
            "iqama update",
            "saudi post parcel",
            "customs fee payment",
            "account blocked pay fee",
            "ministry of interior link",
            "update residency online",
            "absher verification link",
            "free prize transfer fee",
            "bank account suspended",
        ],
    },

    "messages": {
        "en": {
            "vat"       : "15% VAT on service fee ONLY — not on your transfer amount. (Royal Decree M/113)",
            "absher"    : "Transfers ≥ 20,000 SAR require Absher/Iqama verification before processing.",
            "edd"       : "Amount triggers Enhanced Due Diligence. Source of funds declaration required.",
            "wps_fail"  : "Amount exceeds WPS salary bracket. Salary certificate required.",
            "scam"      : "FRAUD ALERT: SAMA never asks for fees via SMS/WhatsApp. Do NOT click any link.",
            "rail"      : "Use STC Pay or Urpay for fastest transfer. Mada for larger amounts.",
        },
        "ur": {
            "vat"       : "15% VAT صرف سروس فیس پر — آپ کی ٹرانسفر رقم پر نہیں۔ (رائل ڈیکری M/113)",
            "absher"    : "20,000 SAR سے زیادہ ٹرانسفر کے لیے Absher/Iqama تصدیق لازمی ہے۔",
            "edd"       : "رقم Enhanced Due Diligence حد سے زیادہ ہے۔ ذریعہ آمدنی کا اعلامیہ ضروری ہے۔",
            "wps_fail"  : "رقم WPS تنخواہ کی حد سے زیادہ ہے۔ تنخواہ سرٹیفیکیٹ درکار ہے۔",
            "scam"      : "فراڈ الرٹ: SAMA کبھی SMS/WhatsApp پر فیس نہیں مانگتا۔ کوئی لنک نہ کھولیں۔",
            "rail"      : "تیز ترین ٹرانسفر کے لیے STC Pay یا Urpay — بڑی رقم کے لیے Mada۔",
        },
    },
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Firestore client
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _get_db():
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
    return firestore.client()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Input sanitizer — strip Iqama before any processing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _mask_iqama(text: str) -> tuple[str, int]:
    """Mask 10-digit Iqama numbers. Returns (masked_text, hit_count)."""
    pattern = KSA_KB["fortress"]["pii_pattern"]
    hits = re.findall(pattern, text)
    masked = re.sub(pattern, "[IQAMA_MASKED]", text)
    return masked, len(hits)

def _detect_scam(text: str) -> list[str]:
    """Check text against KSA scam keyword library."""
    low = text.lower()
    return [kw for kw in KSA_KB["fortress"]["scam_keywords"] if kw in low]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOOL 1 — Firestore corridor rules
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_corridor_rules_ksa(corridor: str = "KSA") -> dict:
    """
    Fetch live KSA corridor rules from Firestore remitiq-db.
    Falls back to embedded KB if Firestore unavailable.
    """
    try:
        db = _get_db()
        doc = db.collection("corridor_rules").document("KSA").get()
        if doc.exists:
            return {
                "status"        : "success",
                "source"        : "firestore",
                "corridor"      : "KSA",
                "rules"         : doc.to_dict(),
                "kb_version"    : KSA_KB["kb_version"],
            }
        # Firestore doc missing — serve from embedded KB
        return {
            "status"        : "success",
            "source"        : "embedded_kb",
            "corridor"      : "KSA",
            "rules"         : KSA_KB,
            "kb_version"    : KSA_KB["kb_version"],
        }
    except Exception as e:
        logger.warning("KSA Firestore error: %s — serving embedded KB", e)
        return {
            "status"        : "fallback",
            "source"        : "embedded_kb",
            "corridor"      : "KSA",
            "rules"         : KSA_KB,
            "kb_version"    : KSA_KB["kb_version"],
            "error"         : str(e),
        }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOOL 2 — VAT Calculator (Royal Decree M/113)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def calculate_vat_ksa(service_fee_sar: float, amount_sar: float = 0) -> dict:
    """
    Calculate 15% VAT on service fee ONLY — never on principal.
    Uses Decimal arithmetic to prevent float rounding errors.
    Ref: Royal Decree M/113 · Zakat, Tax and Customs Authority.

    Args:
        service_fee_sar: Provider service fee in SAR (VAT applied here)
        amount_sar: Principal transfer amount in SAR (VAT NOT applied here)
    """
    # Validation
    if service_fee_sar < 0:
        return {"status": "error", "message": "service_fee_sar cannot be negative."}
    if amount_sar < 0:
        return {"status": "error", "message": "amount_sar cannot be negative."}
    if service_fee_sar > amount_sar and amount_sar > 0:
        return {"status": "error", "message": "service_fee_sar exceeds amount_sar — data error."}

    fee   = Decimal(str(service_fee_sar))
    rate  = Decimal(str(KSA_KB["vat"]["rate"]))
    vat   = (fee * rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
    total = (fee + vat).quantize(Decimal("0.01"), ROUND_HALF_UP)

    return {
        "status"            : "success",
        "principal_sar"     : amount_sar,
        "service_fee_sar"   : service_fee_sar,
        "vat_rate"          : "15%",
        "vat_amount_sar"    : float(vat),
        "total_charges_sar" : float(total),
        "vat_basis"         : KSA_KB["vat"]["basis"],
        "legal_ref"         : KSA_KB["vat"]["legal_ref"],
        "example"           : KSA_KB["vat"]["example"],
        "en_notice"         : KSA_KB["messages"]["en"]["vat"],
        "ur_notice"         : KSA_KB["messages"]["ur"]["vat"],
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOOL 3 — Digital Rail Router (Vision 2030 FSDP)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_best_rail_ksa(amount_sar: float, available_rails: list | None = None) -> dict:
    """
    Select best digital rail based on amount and availability.
    Priority: STC Pay → Urpay → Mada → Wire.
    Respects per-rail transaction limits from KSA_KB.
    Ref: Vision 2030 FSDP digital payment targets.

    Args:
        amount_sar: Transfer amount in SAR
        available_rails: List of available rails (default: all)
    """
    if amount_sar <= 0:
        return {"status": "error", "message": "amount_sar must be positive."}

    rails_kb   = KSA_KB["rails"]
    priority   = rails_kb["priority"]
    available  = set(available_rails) if available_rails else set(priority)

    selected   = None
    for rail in priority:
        if rail not in available:
            continue
        cfg = rails_kb.get(rail, {})
        cap = cfg.get("max_sar")
        if cap is None or amount_sar <= cap:
            selected = rail
            break

    if not selected:
        selected = "WIRE"

    cfg = rails_kb.get(selected, {})
    return {
        "status"        : "success",
        "amount_sar"    : amount_sar,
        "recommended"   : selected,
        "instant"       : cfg.get("instant", False),
        "daily_limit"   : cfg.get("daily"),
        "rail_note"     : cfg.get("note", ""),
        "fsdp_ref"      : rails_kb["fsdp_ref"],
        "all_rails"     : {r: rails_kb[r] for r in priority if r in rails_kb},
        "en_advice"     : KSA_KB["messages"]["en"]["rail"],
        "ur_advice"     : KSA_KB["messages"]["ur"]["rail"],
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOOL 4 — WPS Salary Bracket Compliance
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def check_wps_compliance(amount_sar: float, monthly_salary_sar: float) -> dict:
    """
    Cross-reference transfer amount against WPS salary bracket.
    Applies to individual/personal transfers only.
    Ref: MoHRSD Ministerial Decision No. 1/2595 (2013).

    Args:
        amount_sar: Transfer amount in SAR
        monthly_salary_sar: Sender declared monthly salary in SAR
    """
    if monthly_salary_sar <= 0:
        return {
            "status" : "skipped",
            "note"   : "Salary not provided — WPS check skipped. Provide monthly salary for compliance check.",
        }
    if amount_sar <= 0:
        return {"status": "error", "message": "amount_sar must be positive."}

    amt = Decimal(str(amount_sar))
    sal = Decimal(str(monthly_salary_sar))

    for b in KSA_KB["wps"]["brackets"]:
        lo  = Decimal(str(b["min"]))
        hi  = Decimal(str(b["max"])) if b["max"] else None
        if sal >= lo and (hi is None or sal < hi):
            pct     = Decimal(str(b["pct"]))
            cap     = (sal * pct).quantize(Decimal("0.01"), ROUND_HALF_UP)
            exceeds = amt > cap
            return {
                "status"            : "success",
                "bracket"           : b["label"],
                "monthly_salary_sar": float(sal),
                "max_remittable_sar": float(cap),
                "max_pct"           : int(b["pct"] * 100),
                "requested_sar"     : amount_sar,
                "wps_passed"        : not exceeds,
                "risk"              : "HIGH" if exceeds else "LOW",
                "action_required"   : KSA_KB["wps"]["overage_action"] if exceeds else None,
                "legal_ref"         : KSA_KB["wps"]["legal_ref"],
                "en_message"        : KSA_KB["messages"]["en"]["wps_fail"] if exceeds else "WPS check passed.",
                "ur_message"        : KSA_KB["messages"]["ur"]["wps_fail"] if exceeds else "WPS تعمیل مکمل۔",
            }

    return {"status": "error", "note": "Could not match salary to WPS bracket."}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOOL 5 — Absher / CDD Threshold Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def check_absher_and_cdd(amount_sar: float) -> dict:
    """
    Evaluate all SAMA CDD thresholds for a given transfer amount.
    Returns all triggered verification requirements.
    Ref: SAMA AML/CFT Rules — Circular 381000064902.

    Args:
        amount_sar: Transfer amount in SAR
    """
    if amount_sar <= 0:
        return {"status": "error", "message": "amount_sar must be positive."}

    thr    = KSA_KB["cdd_thresholds"]
    steps  = []

    if amount_sar >= thr["absher_sar"]:
        steps.append({
            "threshold_sar" : thr["absher_sar"],
            "gate"          : "ABSHER_VERIFICATION",
            "action"        : "Absher / Iqama identity verification required before processing.",
            "en"            : KSA_KB["messages"]["en"]["absher"],
            "ur"            : KSA_KB["messages"]["ur"]["absher"],
        })

    if amount_sar >= thr["enhanced_sar"]:
        steps.append({
            "threshold_sar" : thr["enhanced_sar"],
            "gate"          : "ENHANCED_DUE_DILIGENCE",
            "action"        : "Enhanced KYC + source of funds declaration required.",
            "en"            : KSA_KB["messages"]["en"]["edd"],
            "ur"            : KSA_KB["messages"]["ur"]["edd"],
        })

    if amount_sar >= thr["branch_sar"]:
        steps.append({
            "threshold_sar" : thr["branch_sar"],
            "gate"          : "BRANCH_KYC_MANDATORY",
            "action"        : "Cannot process digitally. Must visit licensed SAMA branch.",
        })

    risk = "HIGH" if len(steps) >= 2 else "MEDIUM" if steps else "LOW"

    return {
        "status"        : "success",
        "amount_sar"    : amount_sar,
        "gates_triggered": steps,
        "clear"         : len(steps) == 0,
        "risk_level"    : risk,
        "sama_ref"      : thr["legal_ref"],
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOOL 6 — Fortress AI: Scam + PII Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fortress_scan_ksa(user_message: str) -> dict:
    """
    Fortress AI security scan for KSA corridor.
    1. Detects and masks Iqama numbers (10-digit, starts with 1 or 2)
    2. Scans for MENA-specific phishing / scam patterns
    Returns masked message + threat assessment.
    Sensitivity: HIGH (per KSA_KB)

    Args:
        user_message: Raw user input text to scan
    """
    if not user_message or not isinstance(user_message, str):
        return {"status": "error", "message": "user_message must be a non-empty string."}

    masked, pii_count = _mask_iqama(user_message)
    scam_hits         = _detect_scam(masked)

    risk = "LOW"
    if scam_hits and pii_count:
        risk = "HIGH"
    elif scam_hits or pii_count:
        risk = "MEDIUM"

    block = len(scam_hits) >= 2

    result = {
        "status"            : "success",
        "pii_detected"      : pii_count > 0,
        "pii_count"         : pii_count,
        "pii_type"          : "IQAMA (10-digit Saudi residency number)" if pii_count else None,
        "masked_message"    : masked,
        "scam_hits"         : scam_hits,
        "scam_detected"     : bool(scam_hits),
        "risk_level"        : risk,
        "block_transaction" : block,
        "sensitivity"       : KSA_KB["fortress"]["sensitivity"],
    }

    if block:
        result["block_reason"] = (
            f"Multiple fraud patterns detected: {', '.join(scam_hits)}. "
            "Transaction blocked. Escalate to Compliance."
        )

    if scam_hits:
        result["en_warning"] = KSA_KB["messages"]["en"]["scam"]
        result["ur_warning"] = KSA_KB["messages"]["ur"]["scam"]

    return result

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOOL 7 — Provider Comparison SAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def compare_providers_sar(to_currency: str = "PKR", amount_sar: float = 1000) -> dict:
    """
    Compare licensed remittance providers for SAR outbound corridors.
    Always use Google Search grounding for live rates.

    Args:
        to_currency: Destination currency (PKR, BDT, PHP, IDR)
        amount_sar: Transfer amount in SAR
    """
    if amount_sar <= 0:
        return {"status": "error", "message": "amount_sar must be positive."}

    providers = {
        "PKR": [
            {"name": "Al Rajhi Bank",  "type": "Bank",     "note": "Largest in KSA, strong PKR corridor, bank-to-bank, Mada-linked"},
            {"name": "STC Pay",        "type": "Digital",  "note": "Instant, low fee, best for < 20K SAR, Vision 2030 priority rail"},
            {"name": "Urpay",          "type": "Digital",  "note": "Worker-friendly, Urdu interface, instant settlement"},
            {"name": "Western Union",  "type": "MTO",      "note": "Wide Pakistan network, cash pickup, higher fee"},
            {"name": "Wise",           "type": "Fintech",  "note": "Mid-market rate, transparent, 1-2 days"},
            {"name": "Mada Pay",       "type": "Digital",  "note": "Debit-linked, up to 50K SAR, T+1 settlement"},
        ],
        "BDT": [
            {"name": "Al Rajhi Bank",  "type": "Bank",    "note": "Strong BDT corridor, bKash integration"},
            {"name": "STC Pay",        "type": "Digital", "note": "Instant, low fee"},
            {"name": "Western Union",  "type": "MTO",     "note": "bKash/Nagad delivery integration"},
        ],
        "PHP": [
            {"name": "Al Rajhi Bank",  "type": "Bank",    "note": "Strong PHP corridor"},
            {"name": "Western Union",  "type": "MTO",     "note": "Widespread Philippines pickup network"},
            {"name": "Wise",           "type": "Fintech", "note": "Good mid-market rate for PHP"},
        ],
        "IDR": [
            {"name": "Al Rajhi Bank",  "type": "Bank",    "note": "Indonesia corridor available"},
            {"name": "Wise",           "type": "Fintech", "note": "Competitive IDR rate"},
            {"name": "Western Union",  "type": "MTO",     "note": "Indonesia cash pickup network"},
        ],
    }

    return {
        "status"        : "success",
        "from_currency" : "SAR",
        "to_currency"   : to_currency,
        "amount_sar"    : amount_sar,
        "providers"     : providers.get(to_currency, [{"note": "Use Google Search for this corridor"}]),
        "compliance_tip": "All providers must be SAMA-licensed. Verify before transacting.",
        "rate_tip"      : "Use Google Search grounding for live SAR exchange rates.",
        "sama_ref"      : "SAMA licensed MTOs list: www.sama.gov.sa",
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TOOL 8 — Full KSA Compliance Reference
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_ksa_compliance_info(topic: str) -> dict:
    """
    Return authoritative KSA compliance facts from embedded KB.
    Topics: sama | vat | wps | absher | scam | vision2030 | all

    Args:
        topic: Compliance topic to retrieve
    """
    topics = {
        "sama": {
            "regulator"   : KSA_KB["regulator"],
            "key_rules"   : [
                "All MTOs must be SAMA-licensed (www.sama.gov.sa)",
                f"15% VAT on service fees — {KSA_KB['vat']['basis']}",
                f"Absher verification required for transfers ≥ {KSA_KB['cdd_thresholds']['absher_sar']:,} SAR",
                f"Enhanced KYC required for transfers ≥ {KSA_KB['cdd_thresholds']['enhanced_sar']:,} SAR",
                f"Branch KYC mandatory for transfers ≥ {KSA_KB['cdd_thresholds']['branch_sar']:,} SAR",
            ],
            "ref"         : "SAMA Circular 381000064902",
            "hotline"     : "19000 (SAMA consumer protection hotline)",
        },
        "vat"       : KSA_KB["vat"],
        "wps"       : KSA_KB["wps"],
        "absher"    : {
            "what"          : "Saudi digital identity and residency verification platform",
            "trigger_sar"   : KSA_KB["cdd_thresholds"]["absher_sar"],
            "how"           : "Iqama number + Absher app OTP verification",
            "legal_ref"     : KSA_KB["cdd_thresholds"]["legal_ref"],
        },
        "scam"      : {
            "keywords"      : KSA_KB["fortress"]["scam_keywords"],
            "rule"          : "SAMA and Saudi government NEVER request fees via WhatsApp or SMS links.",
            "action"        : "Hang up. Do not click. Report to 19000.",
            "en_alert"      : KSA_KB["messages"]["en"]["scam"],
            "ur_alert"      : KSA_KB["messages"]["ur"]["scam"],
        },
        "vision2030": {
            "program"       : "Vision 2030 Financial Sector Development Program (FSDP)",
            "goal"          : "70% cashless transactions by 2030",
            "priority_rails": KSA_KB["rails"]["priority"],
            "fsdp_ref"      : KSA_KB["rails"]["fsdp_ref"],
        },
        "all"       : KSA_KB,
    }

    return {
        "status"        : "success",
        "topic"         : topic,
        "kb_version"    : KSA_KB["kb_version"],
        "info"          : topics.get(topic, topics["sama"]),
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADK AGENT DEFINITION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ksa_agent = Agent(
    name="ksa_remittance_agent",
    model="gemini-2.0-flash",
    description=(
        "KSA Vision 2030 Specialist — Saudi Arabia remittance corridor agent. "
        "Covers SAR → PKR, BDT, PHP, IDR. "
        "Embedded SAMA/WPS/VAT/Absher compliance engine. "
        "Fortress AI scam detection. Bilingual EN/UR support."
    ),
    instruction="""
You are the Saudi Arabia (KSA) Remittance Specialist for RemitIQ 360.
You have an embedded SAMA regulatory knowledge base — always use your tools
before answering. Never guess regulatory facts — call the tool.

CORRIDORS: SAR → PKR (primary), BDT, PHP, IDR

YOUR 8 TOOLS — USE THEM:
1. get_corridor_rules_ksa()    — Firestore live rules + embedded KB
2. calculate_vat_ksa()         — 15% VAT on service fee (Royal Decree M/113)
3. get_best_rail_ksa()         — STC Pay/Urpay/Mada/Wire routing (Vision 2030)
4. check_wps_compliance()      — Salary bracket check (MoHRSD Decision 1/2595)
5. check_absher_and_cdd()      — Absher/EDD/Branch KYC thresholds (SAMA)
6. fortress_scan_ksa()         — Iqama PII masking + MENA scam detection
7. compare_providers_sar()     — SAMA-licensed provider comparison
8. get_ksa_compliance_info()   — Full regulatory reference (topic-based)
+ google_search                — Live SAR exchange rates

MANDATORY TOOL TRIGGERS:
- Any fee/charge mentioned → calculate_vat_ksa()
- Any amount mentioned → get_best_rail_ksa() + check_absher_and_cdd()
- Salary mentioned → check_wps_compliance()
- Suspicious keywords → fortress_scan_ksa()
- Rate/exchange query → google_search

SAMA RULES — NON-NEGOTIABLE:
• 15% VAT on service fee ONLY — never on principal
• ≥ 20,000 SAR → Absher/Iqama verification required
• ≥ 60,000 SAR → Enhanced Due Diligence required
• ≥ 100,000 SAR → Branch KYC mandatory
• Rail priority: STC Pay → Urpay → Mada → Wire

SCAM PROTECTION:
• Flag: Iqama update links, Saudi Post fees, account blocked, Ministry links
• SAMA hotline: 19000
• Never ask user to share Iqama number

LANGUAGE:
• Urdu query → respond in Urdu
• Arabic query → respond in Arabic
• Default → English
• Always provide both EN + UR versions of compliance notices
""",
    tools=[
        google_search,
        get_corridor_rules_ksa,
        calculate_vat_ksa,
        get_best_rail_ksa,
        check_wps_compliance,
        check_absher_and_cdd,
        fortress_scan_ksa,
        compare_providers_sar,
        get_ksa_compliance_info,
    ],
)
