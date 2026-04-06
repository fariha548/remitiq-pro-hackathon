from datetime import datetime
from database.firestore import save_task, get_tasks
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
import json

SCOPES = ['https://www.googleapis.com/auth/tasks']
SERVICE_ACCOUNT_FILE = 'tasks-key.json'

def get_tasks_service():
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('tasks', 'v1', credentials=creds)
        return service
    except Exception as e:
        return None

def create_task(title, description, priority="medium", due_date=None):
    task = {
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "source": "RemitIQ Pro MCP"
    }
    save_task(task)
    
    try:
        service = get_tasks_service()
        if service:
            google_task = {
                'title': f"[RemitIQ] {title}",
                'notes': f"{description} | Priority: {priority} | Due: {due_date}",
                'status': 'needsAction'
            }
            service.tasks().insert(tasklist='@default', body=google_task).execute()
            return f"Task created: {title} | Priority: {priority} | Due: {due_date} | Synced to Google Tasks ✓"
    except Exception as e:
        pass
    
    return f"Task created: {title} | Priority: {priority} | Due: {due_date}"

def list_tasks():
    tasks = get_tasks()
    if not tasks:
        return "No tasks found"
    result = "Current Tasks:\n"
    for task in tasks:
        result += f"- {task.get('title')} | {task.get('priority')} | {task.get('status')}\n"
    return result