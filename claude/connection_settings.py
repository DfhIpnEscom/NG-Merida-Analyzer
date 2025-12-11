import json
import os
import sys

# Detect directory
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

API_KEY = config.get("api_key")
PROMPT_TEMPLATE = config.get("prompt", "")
DB_CONNECTION_STRING = config.get("db_connection", "")
SERVER_HOST = config.get("server_host", "0.0.0.0")
SERVER_PORT = int(config.get("server_port", 13000))
RETRY_TIME = int(config.get("retry_time", 5))
DEBUG_MODE = config.get("debug_mode", {})
MODEL = config.get("model", "claude-sonnet-4-20250514")
