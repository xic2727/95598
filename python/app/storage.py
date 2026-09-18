import json
from typing import Any, Dict, Optional
from app.config import SESSION_FILE_PATH

def save_session(session_data: Dict[str, Any]) -> None:
    """Save active session dictionary to data/session.json."""
    SESSION_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

def load_session() -> Optional[Dict[str, Any]]:
    """Load session data from data/session.json if available."""
    if not SESSION_FILE_PATH.exists():
        return None
    try:
        with open(SESSION_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def clear_session() -> None:
    """Clear saved session file."""
    if SESSION_FILE_PATH.exists():
        SESSION_FILE_PATH.unlink(missing_ok=True)
