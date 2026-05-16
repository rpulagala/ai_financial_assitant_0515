import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AI_MODEL = "claude-sonnet-4-6"
DB_PATH = "financial_assistant.db"
APP_TITLE = "AI Financial Assistant — Local Governments"
APP_VERSION = "0.1.0 (PoC)"
