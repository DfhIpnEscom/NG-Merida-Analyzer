import json
import os
import sys
import anthropic

# Detectar la carpeta donde se encuentra el exe o el script
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

claude_cfg = config.get("claude", {})

API_KEY = claude_cfg.get("api_key", "")
MODEL = claude_cfg.get("model", "claude-3-5-sonnet-latest")
PROMPT_TEMPLATE = config.get("prompt", "")
DB_CONNECTION_STRING = config.get("db_connection", "")
SERVER_HOST = config.get("server_host", "0.0.0.0")
SERVER_PORT = int(config.get("server_port", 13000))
RETRY_TIME = int(config.get("retry_time", 5))  # en minutos
DEBUG_MODE = config.get("debug_mode", {"enabled": False})

if not API_KEY or API_KEY.strip() == "":
    raise ValueError("ERROR: 'claude.api_key' no está definida o está vacía en config.json")

# Nueva config claude
client = anthropic.Anthropic(api_key=API_KEY)
MODEL = config.get("model", "claude-sonnet-4-20250514")
