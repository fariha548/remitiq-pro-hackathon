from datetime import datetime
from database.firestore import save_task, get_tasks

def create_task(title, description, priority="medium", due_date=None):
    task = {
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_task(task)
    return f"Task created: {title} | Priority: {priority} | Due: {due_date}"

def list_tasks():
    tasks = get_tasks()
    if not tasks:
        return "No tasks found"
    result = "Current Tasks:\n"
    for task in tasks:
        result += f"- {task.get('title')} | {task.get('priority')} | {task.get('status')}\n"
    return result
