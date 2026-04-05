from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents.coordinator import process_request
from database.firestore import get_tasks, get_events, get_notes, get_compliance
import uvicorn

app = FastAPI(title="RemitIQ Pro API")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

class UserInput(BaseModel):
    message: str

@app.get("/")
def home():
    return FileResponse("frontend/index.html")

@app.post("/chat")
def chat(input: UserInput):
    result = process_request(input.message)
    return result

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
    return {"status": "RemitIQ Pro is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)