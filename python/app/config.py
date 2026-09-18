import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directory for Python project
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuration options
CSG_MOCK: bool = os.getenv("CSG_MOCK", "1").lower() in ("1", "true", "yes")
DATA_DIR: Path = BASE_DIR / "data"
SESSION_FILE_PATH: Path = DATA_DIR / "session.json"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
