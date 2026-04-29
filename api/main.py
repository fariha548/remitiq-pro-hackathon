from google import genai
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents.coordinator import process_request
from prompt_shield import shield
from rate_monitor import run_rate_check, get_live_rate
from agents.pakistan_agent import process_pakistan_query, get_pakistan_corridors
from agents.philippines_agent import process_philippines_query, get_supported_corridors
from agents.indonesia_agent import process_indonesia_query, get_indonesia_corridors
from database.firestore import get_tasks, get_events, get_notes, get_compliance
import uvicorn

app = FastAPI(title="RemitIQ 360 API")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

class UserInput(BaseModel):
    message: str

class PakistanInput(BaseModel):
    message: str
    source_country: str = None
    corridor: str = None

class PhilippinesInput(BaseModel):
    message: str
    corridor: str = None

class IndonesiaInput(BaseModel):
    message: str
    corridor: str = None

@app.get("/")
def home():
    return FileResponse("frontend/index.html")

@app.post("/chat")
def chat(input: UserInput):
    result = process_request(input.message)
    return result

@app.post("/chat/pakistan")
def chat_pakistan(input: PakistanInput):
    scan = shield(input.message, agent_name="pakistan_agent", corridor=input.corridor)
    if not scan["allowed"]:
        return {"error": "Query blocked by Fortress AI", "threats": scan["threats"]}
    import re
    amounts = re.findall(r"([\d,]+)\s*(?:AED|SAR|USD)", input.message, re.IGNORECASE)
    for amt in amounts:
        if int(amt.replace(",","")) > 50000:
            from agents.notification_agent import send_rate_alert
            send_rate_alert("fariha80imr@gmail.com", [{"corridor":"LARGE_TXN","rate":int(amt.replace(",","")),"threshold":50000}])
    result = process_pakistan_query(scan["masked_input"], input.source_country, input.corridor)
    return result


@app.post("/chat/philippines")
def chat_philippines(input: PhilippinesInput):
    scan = shield(input.message, agent_name="philippines_agent", corridor=input.corridor)
    if not scan["allowed"]:
        return {"error": "Query blocked by Fortress AI", "threats": scan["threats"]}
    result = process_philippines_query(scan["masked_input"], input.corridor)
    return result 

@app.post("/chat/indonesia")
def chat_indonesia(input: IndonesiaInput):
    scan = shield(input.message, agent_name="indonesia_agent", corridor=input.corridor)
    if not scan["allowed"]:
        return {"error": "Query blocked by Fortress AI", "threats": scan["threats"]}
    result = process_indonesia_query(scan["masked_input"], input.corridor)
    return result

class BangladeshInput(BaseModel):
    message: str
    corridor: str = None

@app.post("/chat/bangladesh")
def chat_bangladesh(input: BangladeshInput):
    from google import genai
    import os
    client = genai.Client(vertexai=True, project="fortress-ai-remitiq-360", location="asia-southeast1")
    system_prompt = """You are RemitIQ Bangladesh Expert Agent.
FINANCIAL GLOSSARY (Bengali/Bangla):
- Exchange Rate = বিনিময় হার (Binimoẏ Hār)
- Remittance Fee = রেমিট্যান্স ফি (Remittance Fee)
- Transfer Limit = স্থানান্তর সীমা (Sthānāntar Sīmā)
- Bank Charges = ব্যাংক চার্জ (Bank Charge)
- Settlement = নিষ্পত্তি (Niṣpatti)
- Beneficiary = সুবিধাভোগী (Subidhābhogī)
- Wire Transfer = তার স্থানান্তর (Tār Sthānāntar)
- Exchange House = বিনিময় ঘর (Binimoẏ Ghar)
- Compliance = সম্মতি (Sammati)
- Transaction = লেনদেন (Lenden)
Always use these Bengali terms when responding in Bengali/Bangla.
You help Bangladeshi migrant workers in GCC send money home safely.
CORRIDORS: AED→BDT, SAR→BDT, QAR→BDT, KWD→BDT, OMR→BDT, BHD→BDT
RULES:
- Always mention Bangladesh Bank 2.5% cash incentive on formal remittances
- Recommend bKash or Nagad for last-mile delivery
- Warn against hundi (informal) channels
- Compare providers: Al Ansari, Al Rajhi, QNB, Wise, Western Union
- Mention Probashi Kallyan Bank for subsidized rates

CROSS-TALK DETECTION (CRITICAL — Anti-Hallucination):
- If user mentions PKR/Pakistan/SBP → STOP, do not answer, say:
  "Mone hচ্ছে আপনি Pakistan corridor সম্পর্কে জিজ্ঞেস করছেন।
   আপনি কি corridor switch করতে চান? (হ্যাঁ/না)
   It seems you are asking about Pakistan corridor.
   Would you like to switch? (Yes/No)
   Until confirmed, I will stay in Bangladesh corridor."

- If user mentions PHP/Philippines/BSP → STOP, do not answer, say:
  "It seems you are asking about Philippines corridor.
   Would you like to switch? (Yes/No)
   Until confirmed, I will stay in Bangladesh corridor."

- If user mentions IDR/Indonesia/OJK → STOP, do not answer, say:
  "It seems you are asking about Indonesia corridor.
   Would you like to switch? (Yes/No)
   Until confirmed, I will stay in Bangladesh corridor."

- If user says "হ্যাঁ/Yes" after cross-talk → say:
  "Please retype your question in the correct corridor chat."

- If user says "না/No" after cross-talk → continue Bangladesh corridor only.


NEVER answer questions about other corridors — always ask confirmation first.

OUT OF SCOPE HANDLER (CRITICAL):
- If user asks about immigration laws, visa rules, labor laws,
  tax laws, property laws, criminal laws → STOP, say:
  "আমি দুঃখিত, এই প্রশ্নটি আমার পরিধির বাইরে।
   I'm sorry, that question is outside my scope.
   I can only help with Bangladesh remittance:
   ✓ AED/SAR/QAR/KWD → BDT transfer rates
   ✓ Bangladesh Bank compliance
   ✓ bKash/Nagad delivery options
   ✓ 2.5% cash incentive guidance
   ✓ BMET registration help
   Would you like help with a remittance question?"

- NEVER answer: visa, immigration, labor, tax, property, criminal topics
- ONLY answer: remittance fees, transfer limits, exchange rates,
  BB compliance, KYC, bKash/Nagad, wage earner bonds


LANGUAGE RESPONSE RULES (CRITICAL):
- If user writes in Bengali/Bangla → respond ENTIRELY in Bengali
- If user writes in Arabic → respond ENTIRELY in Arabic
- If user writes in English → respond in English
- If user writes mixed Bengali/English → respond in Bengali with English terms
- NEVER respond in English if user wrote in Bengali or Arabic
- Detect language from user input and mirror it exactly."""
    scan = shield(input.message, agent_name="bangladesh_agent", corridor=input.corridor)
    if not scan["allowed"]:
        return {"error": "Query blocked by Fortress AI", "threats": scan["threats"]}
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"System: {system_prompt}\n\nUser: {scan['masked_input']}"
    )
    return {"response": response.text}

@app.get("/corridors/bangladesh")
def bangladesh_corridors():
    return {"corridors": ["AED_BDT", "SAR_BDT", "QAR_BDT", "KWD_BDT", "OMR_BDT", "BHD_BDT"]}

@app.get("/corridors/pakistan")
def pakistan_corridors():
    return {"corridors": get_pakistan_corridors()}

@app.get("/corridors/philippines")
def philippines_corridors():
    return {"corridors": get_supported_corridors()}

@app.get("/corridors/indonesia")
def indonesia_corridors():
    return {"corridors": get_indonesia_corridors()}

@app.get("/tasks")
def tasks():
    return {"tasks": get_tasks()}

@app.get("/events")
def events():
    return {"events": get_events()}

@app.get("/notes")
def notes():
    return {"notes": get_notes()}

@app.get("/compliance")
def compliance():
    return {"compliance": get_compliance()}

@app.get("/health")
def health():
    return {
        "status": "RemitIQ 360 is running",
        "agents": ["pakistan_agent", "philippines_agent", "indonesia_agent","bangladesh_agent"],
        "corridors": [
            "PK→UAE", "PK→KSA", "PK→QAT", "PK→UK", "PK→USA",
            "PH→UAE", "PH→KSA", "PH→HKG", "PH→QAT", "PH→KWT",
            "ID→UAE", "ID→KSA", "ID→MYR", "ID→QAT", "ID→KWT"
        ],
        "regulatory_db": "gs://remitiq-regulatory-docs/",
        "firestore_db": "remitiq-db",
        "coming_soon": ["BD→UAE", "BD→KSA", "SG→IN (PayNow-UPI)"]
    }

@app.get("/rates/live/{from_currency}/{to_currency}")
def live_rate(from_currency: str, to_currency: str):
    return get_live_rate(from_currency.upper(), to_currency.upper())

@app.post("/rates/check")
def rate_check():
    return run_rate_check()

@app.get("/rates/corridors")
def rate_corridors():
    return {
        "corridors": [
            "AED_PKR", "SAR_PKR",
            "AED_PHP", "SAR_PHP", 
            "AED_IDR", "SAR_IDR",
            "AED_BDT", "SAR_BDT"
        ],
        "monitor": "active",
        "interval": "5 minutes",
        "alerts": "Gmail SMTP"
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

class KSAInput(BaseModel):
    message: str
    corridor: str = "SAR_PKR"

class UAEInput(BaseModel):
    message: str
    corridor: str = "AED_PKR"

@app.post("/chat/ksa")
def chat_ksa(input: KSAInput):
    scan = shield(input.message, agent_name="ksa_agent", corridor=input.corridor)
    if not scan["allowed"]:
        return {"error": "Query blocked by Fortress AI", "threats": scan["threats"]}
    client = genai.Client(vertexai=True, project="fortress-ai-remitiq-360", location="asia-southeast1")
    prompt = f"""You are a KSA remittance expert. Answer in same language as question.
Corridor: SAR->PKR. SAMA rules. VAT 15% on fees. Channels: STC Pay, Al Rajhi, Urpay.
Question: {scan['masked_input']}"""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return {"response": response.text, "agent": "KSA", "corridor": input.corridor, "shield": scan}

@app.post("/chat/uae")
def chat_uae(input: UAEInput):
    scan = shield(input.message, agent_name="uae_agent", corridor=input.corridor)
    if not scan["allowed"]:
        return {"error": "Query blocked by Fortress AI", "threats": scan["threats"]}
    client = genai.Client(vertexai=True, project="fortress-ai-remitiq-360", location="asia-southeast1")
    prompt = f"""You are a UAE remittance expert. Answer in same language as question.
Corridor: AED->PKR. CBUAE rules. Channels: Al Ansari, LuLu Exchange, Exchange4Free.
Question: {scan['masked_input']}"""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return {"response": response.text, "agent": "UAE", "corridor": input.corridor, "shield": scan}

@app.post("/chat/ksa/v2")
def chat_ksa_v2(input: KSAInput):
    scan = shield(input.message, agent_name="ksa_agent", corridor=input.corridor)
    if not scan["allowed"]:
        return {"error": "Query blocked by Fortress AI", "threats": scan["threats"]}
    client = genai.Client(vertexai=True, project="fortress-ai-remitiq-360", location="asia-southeast1")
    prompt = f"""You are a KSA remittance expert. Answer in the same language as the question.
Corridor: SAR→PKR. SAMA rules apply. VAT 15% on fees.
Channels: STC Pay, Al Rajhi, Urpay, Wise, Western Union.
Question: {scan['masked_input']}"""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return {"response": response.text, "agent": "KSA", "corridor": input.corridor, "shield": scan}

class ChinaInput(BaseModel):
    message: str
    corridor: str = "CNY_PKR"

@app.post("/chat/china")
def chat_china(input: ChinaInput):
    scan = shield(input.message, agent_name="china_agent", corridor=input.corridor)
    if not scan["allowed"]:
        return {"error": "Query blocked by Fortress AI", "threats": scan["threats"]}
    client = genai.Client(vertexai=True, project="fortress-ai-remitiq-360", location="asia-southeast1")
    prompt = f"""You are a China remittance expert. Answer in same language as question.
Corridor: CNY->PKR. SAFE/PBOC rules. Channels: Alipay, WeChat Pay, UnionPay, Western Union.
Question: {scan['masked_input']}"""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return {"response": response.text, "agent": "China", "corridor": input.corridor, "shield": scan}
