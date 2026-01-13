import json
import os
import sys

# Detectar la carpeta donde se encuentra el exe o el script
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# Configuración del proveedor de IA
AI_PROVIDER = config.get("ai_provider", "claude").lower()

# Configuración de Claude
claude_cfg = config.get("claude", {})
CLAUDE_API_KEY = claude_cfg.get("api_key", "")
CLAUDE_MODEL = claude_cfg.get("model", "claude-sonnet-4-20250514")

# Configuración de Gemini
gemini_cfg = config.get("Gemini", {})
GEMINI_API_KEY = gemini_cfg.get("api_key", "")
GEMINI_MODEL = gemini_cfg.get("model", "models/gemini-2.0-flash-exp")

# Configuración general
PROMPT_TEMPLATE = config.get("prompt", "")
DB_CONNECTION_STRING = config.get("db_connection", "")
SERVER_HOST = config.get("server_host", "0.0.0.0")
SERVER_PORT = int(config.get("server_port", 13000))
RETRY_TIME = int(config.get("retry_time", 5))  # en minutos
DEBUG_MODE = config.get("debug_mode", {"enabled": False})

# Configuración de SQL Polling
SQL_POLLING_CONFIG = config.get("sql_polling", {
    "enabled": False,
    "table_name": "AudioQueue",
    "poll_interval_seconds": 30,
    "max_records_per_batch": 10,
    "status_field": "Estado",
    "id_field": "TransactionId",
    "audio_path_field": "RutaAudio",
    "status_pending": "Pendiente",
    "status_processing": "Procesando",
    "status_completed": "Completado",
    "status_error": "Error"
})

# Validación según el proveedor seleccionado
if AI_PROVIDER == "claude":
    if not CLAUDE_API_KEY or CLAUDE_API_KEY.strip() == "" or CLAUDE_API_KEY == "xxxxxxxxxxxx":
        raise ValueError("ERROR: 'claude.api_key' no está definida o está vacía en config.json")
elif AI_PROVIDER == "gemini":
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "" or GEMINI_API_KEY == "xxxxxxxxxxx":
        raise ValueError("ERROR: 'Gemini.api_key' no está definida o está vacía en config.json")
else:
    raise ValueError(f"ERROR: Proveedor de IA no válido: '{AI_PROVIDER}'. Use 'claude' o 'gemini'")

print(f"[CONFIG] Proveedor de IA seleccionado: {AI_PROVIDER.upper()}")
print(f"[CONFIG] SQL Polling: {'HABILITADO' if SQL_POLLING_CONFIG.get('enabled') else 'DESHABILITADO'}")