from datetime import datetime
from database.firestore import save_compliance, get_compliance

def create_compliance(title, deadline, description=None, authority=None):
    item = {
        "title": title,
        "deadline": deadline,
        "description": description,
        "authority": authority,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_compliance(item)
    return f"Compliance deadline set: {title} | Deadline: {deadline} | Authority: {authority}"

def list_compliance():
    items = get_compliance()
    if not items:
        return "No compliance items found"
    result = "Compliance Deadlines:\n"
    for item in items:
        result += f"- {item.get('title')} | {item.get('deadline')} | {item.get('status')}\n"
    return result
