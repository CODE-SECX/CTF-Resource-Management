import json
import os
import datetime
from flask import jsonify

NOTES_FILE = 'notes_data.json'

def get_all_notes():
    """Retrieve all notes from the JSON file."""
    if not os.path.exists(NOTES_FILE):
        return {"notes": []}
    
    with open(NOTES_FILE, 'r') as f:
        return json.load(f)

def get_notes_by_category(category):
    """Get notes filtered by category."""
    data = get_all_notes()
    filtered_notes = [note for note in data["notes"] if note["category"] == category]
    return {"notes": filtered_notes}

def get_note_by_id(note_id):
    """Get a specific note by ID."""
    data = get_all_notes()
    for note in data["notes"]:
        if note["id"] == note_id:
            return note
    return None

def create_note(title, content, category, due_date=None):
    """Add a new note."""
    data = get_all_notes()
    
    # Generate a new ID
    new_id = 1
    if data["notes"]:
        new_id = max(note["id"] for note in data["notes"]) + 1
    
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    new_note = {
        "id": new_id,
        "title": title,
        "content": content,
        "category": category,
        "completed": False,
        "created_date": today,
        "due_date": due_date
    }
    
    data["notes"].append(new_note)
    save_notes(data)
    return new_note

def update_note(note_id, updates):
    """Update an existing note."""
    data = get_all_notes()
    for i, note in enumerate(data["notes"]):
        if note["id"] == note_id:
            data["notes"][i] = {**note, **updates}
            save_notes(data)
            return data["notes"][i]
    return None

def toggle_note_completion(note_id):
    """Mark a note as completed or not completed."""
    data = get_all_notes()
    for i, note in enumerate(data["notes"]):
        if note["id"] == note_id:
            data["notes"][i]["completed"] = not data["notes"][i]["completed"]
            save_notes(data)
            return data["notes"][i]
    return None

def delete_note(note_id):
    """Delete a note."""
    data = get_all_notes()
    for i, note in enumerate(data["notes"]):
        if note["id"] == note_id:
            del data["notes"][i]
            save_notes(data)
            return True
    return False

def save_notes(data):
    """Save notes data to the JSON file."""
    with open(NOTES_FILE, 'w') as f:
        json.dump(data, f, indent=2)