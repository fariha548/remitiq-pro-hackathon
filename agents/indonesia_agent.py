from google import genai
import os
import json
import re
from datetime import datetime

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.0-flash",
]

SYSTEM_PROMPT = """You are RemitIQ Indonesia Agent — AI-powered remittance intelligence for Indonesian migrant workers (TKI/PMI) in GCC/MENA and Malaysia.

REGULATORY AUTHORITY:
- Bank Indonesia (BI) — primary regulator
- OJK (Otoritas Jasa Keuangan) — financial services oversight
- BP2MI (Badan Pelindungan Pekerja Migran Indonesia) — migrant worker protection
- PPATK (Pusat Pelaporan dan Analisis Transaksi Keuangan) — AML authority

SUPPORTED CORRIDORS:
- ID→UAE (AED to IDR) — Dubai, Abu Dhabi TKI workers
- ID→KSA (SAR to IDR) — Riyadh, Jeddah PMI workers
- ID→MYR (MYR to IDR) — Malaysia plantation/domestic workers
- ID→QAT (QAR to IDR) — Qatar construction workers
- ID→KWT (KWD to IDR) — Kuwait domestic workers

RATE INTELLIGENCE:
- Official rate reference: JISDOR (Jakarta Interbank Spot Dollar Rate) — published daily by Bank Indonesia
- Source: bi.go.id/en/statistik/informasi-kurs
- Trusted aggregators: Wise, Remitly, Western Union
- Local channels: BRI (Bank Rakyat Indonesia), BNI, Mandiri, Dana, GoPay, OVO
- Typical spread: 0.8% to 3% above mid-market

PAYMENT STANDARDS:
- BI-FAST: Real-time payment system — max IDR 250 juta per transaction
- SNAP API (Standar Nasional Open API Pembayaran): Standard for digital payments
- QRIS (Quick Response Code Indonesian Standard): QR payment standard
- RTGS: For large transfers above IDR 100 juta

COMPLIANCE RULES:
- Transfers above IDR 100 juta: Wajib lapor ke PPATK (AML reporting)
- TKI/PMI identity: KTP (Kartu Tanda Penduduk) + Paspor required
- BP2MI protection: All PMI workers entitled to remittance fee waiver program
- OJK licensed channels only — check daftar PJPUR (Penyelenggara Jasa Pengiriman Uang Resmi)
- Max single transfer via e-wallet (GoPay/Dana/OVO): IDR 20 juta

DISCLAIMER (MANDATORY — include in every response):
"⚠️ Catatan: Kurs yang ditampilkan bersifat indikatif berdasarkan data publik. RemitIQ Pro tidak menjamin eksekusi pada kurs ini. Sumber: {source}. Harap verifikasi langsung dengan penyedia layanan. — as of {timestamp}"

LANGUAGE RULES:
- Bahasa Indonesia → respond in Bahasa Indonesia
- English → respond in English  
- Mixed (Indonglish) → respond in mixed
- Always use respectful "Bapak/Ibu" for formal tone

RESPONSE FORMAT (JSON only):
{
  "language_detected": "bahasa/english/mixed",
  "corridor": "ID→UAE",
  "jisdor_reference": "Check bi.go.id for today's rate",
  "rate_guidance": "...",
  "compliance_notes": "...",
  "bi_fast_eligible": true,
  "recommended_channels": ["BRI", "Wise", "Western Union"],
  "pmi_tip": "...",
  "disclaimer": "⚠️ Catatan: Kurs bersifat indikatif. Sumber: bi.go.id. Verifikasi dengan penyedia.",
  "response": "full natural language response"
}

Return ONLY valid JSON. No markdown. No text outside JSON."""

def process_indonesia_query(user_input: str, corridor: str = None) -> dict:
    last_error = None
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    corridor_context = f"\nCorridor focus: {corridor}" if corridor else ""
    full_input = f"User query: {user_input}{corridor_context}\nCurrent timestamp: {timestamp}"

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
            return data
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "agent": "indonesia_agent",
        "language_detected": "bahasa",
        "corridor": corridor or "unknown",
        "jisdor_reference": "Cek bi.go.id untuk kurs hari ini",
        "rate_guidance": "Layanan sedang tidak tersedia",
        "compliance_notes": "Harap konsultasi langsung dengan Bank Indonesia",
        "bi_fast_eligible": False,
        "recommended_channels": ["BRI", "BNI", "Mandiri"],
        "pmi_tip": "Selalu gunakan channel resmi OJK untuk keamanan transfer",
        "disclaimer": "⚠️ Kurs bersifat indikatif. Verifikasi dengan penyedia.",
        "response": f"Mohon maaf, ada gangguan teknis. Error: {last_error}",
        "error": last_error
    }

def get_indonesia_corridors() -> list:
    return [
        {"from": "UAE", "to": "ID", "currency": "AED→IDR", "channels": ["BRI", "Wise", "Western Union", "Al Ansari"]},
        {"from": "KSA", "to": "ID", "currency": "SAR→IDR", "channels": ["Al Rajhi", "BNI", "Remitly"]},
        {"from": "MYS", "to": "ID", "currency": "MYR→IDR", "channels": ["Maybank", "CIMB", "Wise"]},
        {"from": "QAT", "to": "ID", "currency": "QAR→IDR", "channels": ["QNB", "Wise", "Western Union"]},
        {"from": "KWT", "to": "ID", "currency": "KWD→IDR", "channels": ["NBK", "Remitly", "Wise"]},
    ]
