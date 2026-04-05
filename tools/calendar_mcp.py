from datetime import datetime
from database.firestore import save_event, get_events

def create_event(title, date, time, description=None):
    event = {
        "title": title,
        "date": date,
        "time": time,
        "description": description,
        "created_at": datetime.now().isoformat()
    }
    save_event(event)
    return f"Event scheduled: {title} | Date: {date} | Time: {time}"

def list_events():
    events = get_events()
    if not events:
        return "No events found"
    result = "Upcoming Events:\n"
    for event in events:
        result += f"- {event.get('title')} | {event.get('date')} | {event.get('time')}\n"
    return result
