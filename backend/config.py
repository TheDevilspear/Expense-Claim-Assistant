"""
Configuration and Environment Management.
Loads environment variables from root .env and provides application-wide configuration.
"""

import os
import logging
from pathlib import Path

# Configure standard root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("expense_assistant")

def load_env_file():
    """Loads key-value pairs from root .env into os.environ if not already set."""
    # Look for .env in project root (two levels up from backend/config.py)
    root_env = Path(__file__).resolve().parent.parent / ".env"
    if not root_env.exists():
        # Also check current backend directory
        root_env = Path(__file__).resolve().parent / ".env"
        
    if root_env.exists():
        try:
            for line in root_env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    os.environ.setdefault(k, v)
        except Exception as e:
            logger.warning(f"Could not parse .env file: {e}")

# Load environment on initial import
load_env_file()

def get_api_key():
    return os.environ.get("OPENROUTER_API_KEY", "").strip()

def get_vision_model():
    return os.environ.get("VISION_MODEL", "openrouter/free")

def get_base_url():
    return os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")

def get_timeout():
    try:
        return float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "8.0"))
    except ValueError:
        return 8.0
