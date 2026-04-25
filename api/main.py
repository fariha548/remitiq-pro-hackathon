from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents.coordinator import process_request
from agents.philippines_agent import process_philippines_query, get_supported_corridors
from agents.indonesia_agent import process_indonesia_query, get_indonesia_corridors
from database.firestore import get_tasks, get_events, get_notes, get_compliance
import uvicorn

app = FastAPI(title="RemitIQ 360 API")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

class UserInput(BaseModel):
    message: str

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

@app.post("/chat/philippines")
def chat_philippines(input: PhilippinesInput):
    result = process_philippines_query(input.message, input.corridor)
    return result

@app.post("/chat/indonesia")
def chat_indonesia(input: IndonesiaInput):
    result = process_indonesia_query(input.message, input.corridor)
    return result

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
        "agents": ["pakistan_agent", "philippines_agent", "indonesia_agent"],
        "corridors": [
            "PK→UAE", "PK→KSA", "PK→QAT",
            "PH→UAE", "PH→KSA", "PH→HKG", "PH→QAT", "PH→KWT",
            "ID→UAE", "ID→KSA", "ID→MYR", "ID→QAT", "ID→KWT"
        ],
        "regulatory_db": "gs://remitiq-regulatory-docs/",
        "coming_soon": ["BD→UAE", "BD→KSA", "SG→IN (PayNow-UPI)"]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
