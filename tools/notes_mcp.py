from datetime import datetime
from database.firestore import save_note, get_notes

def create_note(title, content, category=None):
    note = {
        "title": title,
        "content": content,
        "category": category,
        "created_at": datetime.now().isoformat()
    }
    save_note(note)
    return f"Note saved: {title} | Category: {category}"

def list_notes():
    notes = get_notes()
    if not notes:
        return "No notes found"
    result = "Saved Notes:\n"
    for note in notes:
        result += f"- {note.get('title')} | {note.get('category')}\n"
    return result
