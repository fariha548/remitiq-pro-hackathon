from google import genai
import os
from tools.task_mcp import create_task, list_tasks
from tools.calendar_mcp import create_event, list_events
from tools.notes_mcp import create_note, list_notes
from tools.compliance_mcp import create_compliance, list_compliance
import json
import re

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview-04-17",
]

SYSTEM_PROMPT = """You are RemitIQ Pro Coordinator for Pakistan remittance bank operations.

Analyze the user input and respond with ONLY a JSON object. No explanation. No markdown. Just JSON.

Format:
{
  "understanding": "brief summary",
  "actions": [
    {
      "agent": "task",
      "action": "create",
      "params": {
        "title": "task title",
        "description": "details",
        "priority": "high",
        "due_date": "Friday"
      }
    },
    {
      "agent": "calendar",
      "action": "create",
      "params": {
        "title": "meeting title",
        "date": "tomorrow",
        "time": "3:00 PM",
        "description": "details"
      }
    },
    {
      "agent": "notes",
      "action": "create",
      "params": {
        "title": "note title",
        "content": "note content",
        "category": "MTO Partner"
      }
    },
    {
      "agent": "compliance",
      "action": "create",
      "params": {
        "title": "compliance title",
        "deadline": "Friday",
        "description": "details",
        "authority": "SBP"
      }
    }
  ],
  "summary": "what was done"
}

IMPORTANT: Return ONLY valid JSON. No text before or after. No markdown code blocks."""

def process_request(user_input):
    last_error = None
    
    for model_name in MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=SYSTEM_PROMPT + "\n\nUser input: " + user_input
            )
            raw = response.text.strip()
            raw = re.sub(r'```json|```', '', raw).strip()
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
            data = json.loads(raw)
            data["model_used"] = model_name
            break
        except Exception as e:
            last_error = str(e)
            continue
    else:
        return {
            "understanding": user_input,
            "actions": [],
            "summary": f"All models unavailable. Please try again. Error: {last_error}",
            "results": []
        }

    results = []
    for action in data.get("actions", []):
        agent = action.get("agent")
        act = action.get("action")
        params = action.get("params", {})
        try:
            if agent == "task" and act == "create":
                result = create_task(
                    params.get("title", "Task"),
                    params.get("description", ""),
                    params.get("priority", "medium"),
                    params.get("due_date")
                )
                results.append("✅ Task: " + result)
            elif agent == "calendar" and act == "create":
                result = create_event(
                    params.get("title", "Event"),
                    params.get("date", "TBD"),
                    params.get("time", "TBD"),
                    params.get("description")
                )
                results.append("📅 Calendar: " + result)
            elif agent == "notes" and act == "create":
                result = create_note(
                    params.get("title", "Note"),
                    params.get("content", ""),
                    params.get("category")
                )
                results.append("📝 Notes: " + result)
            elif agent == "compliance" and act == "create":
                result = create_compliance(
                    params.get("title", "Compliance"),
                    params.get("deadline", "TBD"),
                    params.get("description"),
                    params.get("authority", "SBP")
                )
                results.append("⚖️ Compliance: " + result)
            elif act == "list":
                if agent == "task":
                    results.append(list_tasks())
                elif agent == "calendar":
                    results.append(list_events())
                elif agent == "notes":
                    results.append(list_notes())
                elif agent == "compliance":
                    results.append(list_compliance())
        except Exception as e:
            results.append(f"Error in {agent} agent: {str(e)}")

    data["results"] = results
    return data