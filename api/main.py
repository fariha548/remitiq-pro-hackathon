from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents.coordinator import process_request
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
    result = process_pakistan_query(input.message, input.source_country, input.corridor)
    return result

@app.post("/chat/philippines")
def chat_philippines(input: PhilippinesInput):
    result = process_philippines_query(input.message, input.corridor)
    return result

@app.post("/chat/indonesia")
def chat_indonesia(input: IndonesiaInput):
    result = process_indonesia_query(input.message, input.corridor)
    return result
class BangladeshInput(BaseModel):
    message: str
    corridor: str = None

@app.post("/chat/bangladesh")
def chat_bangladesh(input: BangladeshInput):
    from google import genai
    import os
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    system_prompt = """You are RemitIQ Bangladesh Expert Agent.
You help Bangladeshi migrant workers in GCC send money home safely.
CORRIDORS: AED→BDT, SAR→BDT, QAR→BDT, KWD→BDT, OMR→BDT, BHD→BDT
RULES:
- Always mention Bangladesh Bank 2.5% cash incentive on formal remittances
- Recommend bKash or Nagad for last-mile delivery
- Warn against hundi (informal) channels
- Compare providers: Al Ansari, Al Rajhi, QNB, Wise, Western Union
- Mention Probashi Kallyan Bank for subsidized rates
- If user mentions PKR/Pakistan → suggest corridor switch
- If user mentions PHP/Philippines → suggest corridor switch
- If user mentions IDR/Indonesia → suggest corridor switch
Respond in English. If user writes in Bengali, respond in Bengali."""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"System: {system_prompt}\n\nUser: {input.message}"
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
