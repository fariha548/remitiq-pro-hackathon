from google.cloud import firestore
import os

db = firestore.Client()

def save_task(task_data):
    doc_ref = db.collection('tasks').add(task_data)
    return doc_ref

def get_tasks():
    tasks = db.collection('tasks').stream()
    return [task.to_dict() for task in tasks]

def save_event(event_data):
    doc_ref = db.collection('events').add(event_data)
    return doc_ref

def get_events():
    events = db.collection('events').stream()
    return [event.to_dict() for event in events]

def save_note(note_data):
    doc_ref = db.collection('notes').add(note_data)
    return doc_ref

def get_notes():
    notes = db.collection('notes').stream()
    return [note.to_dict() for note in notes]

def save_compliance(compliance_data):
    doc_ref = db.collection('compliance').add(compliance_data)
    return doc_ref

def get_compliance():
    items = db.collection('compliance').stream()
    return [item.to_dict() for item in items]
