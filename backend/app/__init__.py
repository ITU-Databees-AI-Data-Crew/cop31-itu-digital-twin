from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env (API keys, COP31_MODEL) for every entry point. Real environment variables win.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
