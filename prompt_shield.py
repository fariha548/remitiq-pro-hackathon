# prompt_shield.py
# RemitIQ 360 — Fortress AI Prompt Shield
# Injection detection, PII masking, compliance guard

import re
import hashlib
from datetime import datetime, timezone
from fortress_logger import log_event, log_alert

# ── Injection keywords ───────────────────────────────────────────────────────
INJECTION_PATTERNS = [
    r"ignore (all |previous |above )?instructions",
    r"you are now",
    r"forget (all |your )?instructions",
    r"act as (a |an )?",
    r"jailbreak",
    r"dan mode",
    r"pretend you",
    r"override (your |all )?",
    r"system prompt",
    r"disregard (all |previous )?",
    r"new persona",
    r"bypass",
    r"sudo mode",
    r"developer mode",
    # Arabic
    r"تجاهل",
    r"تجاهل التعليمات",
    r"أنت الآن",
    r"تجاهل جميع",
    r"تجاوز",
    r"وضع المطور",
    # Urdu
    r"تمام ہدایات نظرانداز",
    r"پچھلی ہدایات بھول",
    r"سسٹم پرامپٹ",
    r"بائی پاس کرو",
    # Tagalog
    r"huwag pansinin",
    r"kalimutan.*instruksyon",
    r"i-override",
    r"laktawan",
    r"bagong persona",
    # Bahasa Indonesia
    r"abaikan.*instruksi",
    r"lupakan.*instruksi",
    r"lewati.*instruksi",
    r"persona baru",
    r"mode pengembang",
    r"abaikan semua",
    # Bengali
    r"সব নির্দেশ উপেক্ষা",
    r"আগের নির্দেশ ভুলে যাও",
    r"সিস্টেম প্রম্পট",
    r"বাইপাস করো",
]

# ── PII patterns ─────────────────────────────────────────────────────────────
PII_PATTERNS = {
    "cnic": r"\b\d{5}-\d{7}-\d{1}\b",
    "iqama": r"\b[12]\d{9}\b",
    "passport": r"\b[A-Z]{2}\d{7}\b",
    "phone_pk": r"\b(\+92|0092|92)?[-.\s]?3\d{2}[-.\s]?\d{7}\b",
    "phone_uae": r"\b(\+971|00971)?[-.\s]?5\d{8}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b",
    "card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
}

# ── Suspicious amount patterns ────────────────────────────────────────────────
SUSPICIOUS_AMOUNT_THRESHOLD = 50000  # USD equivalent

# ── Core shield function ─────────────────────────────────────────────────────
def shield(user_input: str, agent_name: str = "unknown", corridor: str = None) -> dict:
    """
    Run prompt shield on user input.
    Returns: {
        allowed: bool,
        masked_input: str,
        threats: list,
        pii_detected: list,
        query_hash: str
    }
    """
    threats = []
    pii_detected = []
    masked_input = user_input

    # 1. Length check
    if len(user_input) > 2000:
        threats.append("input_too_long")
        log_alert(
            alert_type="input_too_long",
            corridor=corridor or "unknown",
            details=f"Input length: {len(user_input)} chars",
            severity="WARNING",
            source_agent=agent_name
        )

    # 2. Injection detection
    lower_input = user_input.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower_input):
            threats.append(f"injection_attempt: {pattern}")
            log_alert(
                alert_type="prompt_injection",
                corridor=corridor or "unknown",
                details=f"Pattern matched: {pattern} | Agent: {agent_name}",
                severity="CRITICAL",
                source_agent=agent_name
            )

    # 3. PII detection + masking
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, masked_input, re.IGNORECASE)
        if matches:
            pii_detected.append(pii_type)
            masked_input = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", masked_input, flags=re.IGNORECASE)
            log_alert(
                alert_type="pii_detected",
                corridor=corridor or "unknown",
                details=f"PII type: {pii_type} | Agent: {agent_name}",
                severity="WARNING",
                source_agent=agent_name
            )

    # 4. Query hash (for audit — never store raw PII)
    query_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]

    # 5. Log the shield result
    allowed = len([t for t in threats if "injection" in t]) == 0
    log_event(
        agent_name=agent_name,
        event_type="shield_scan",
        corridor=corridor or "unknown",
        user_query=query_hash,
        response_summary=f"allowed={allowed} | threats={len(threats)} | pii={len(pii_detected)}",
        metadata={
            "threats": threats,
            "pii_types": pii_detected,
            "input_length": len(user_input),
            "allowed": allowed
        },
        severity="WARNING" if threats else "INFO"
    )

    return {
        "allowed": allowed,
        "masked_input": masked_input,
        "threats": threats,
        "pii_detected": pii_detected,
        "query_hash": query_hash,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ── Quick check (lightweight — no logging) ───────────────────────────────────
def is_safe(user_input: str) -> bool:
    """Fast boolean check — use for pre-screening."""
    lower = user_input.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower):
            return False
    return True


# ── PII masker only ──────────────────────────────────────────────────────────
def mask_pii(text: str) -> str:
    """Mask PII from text without full shield logging."""
    masked = text
    for pii_type, pattern in PII_PATTERNS.items():
        masked = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", masked, flags=re.IGNORECASE)
    return masked
