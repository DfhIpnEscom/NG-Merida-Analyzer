from connection_settings import DEBUG_MODE
from log import log
from audio_process import procesar_audio
import os
import traceback

def run_debug_once():
    if not DEBUG_MODE.get("enabled", False):
        return

    wav = DEBUG_MODE.get("wav_file")
    if not wav or not os.path.exists(wav):
        log("Debug WAV file incorrecto")
        return

    try:
        procesar_audio(999999, wav)
    except Exception as e:
        log(traceback.format_exc())
