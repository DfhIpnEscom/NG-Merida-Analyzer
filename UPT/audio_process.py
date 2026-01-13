from log import log
from transcripcion import transcribir_audio
from analysis import analizar_transcripcion
from sql_connection import ejecutar_sp
from connection_settings import AI_PROVIDER
import json
import os
import traceback

# Procesamiento de audio
def procesar_audio(transaction_id, archivo_original):
    log(f"Procesando TransactionId: {transaction_id} - {archivo_original}")
    if not os.path.exists(archivo_original):
        log("Archivo no existe: " + archivo_original)
        return

    try:
        transcripcion = transcribir_audio(archivo_original)
        if not transcripcion:
            log("No se obtuvo transcripción.")
            return

        # Obtener el nombre del proveedor para incluirlo en los nombres de archivo
        proveedor_nombre = AI_PROVIDER.upper()  # "CLAUDE" o "GEMINI"
        
        base, _ = os.path.splitext(archivo_original)
        
        # Nombres de archivo con el proveedor incluido
        ruta_transcripcion = f"{base};transcripcion_{proveedor_nombre}.txt"
        ruta_evaluacion_txt = f"{base};evaluacion_{proveedor_nombre}.txt"
        ruta_evaluacion_json = f"{base};evaluacion_{proveedor_nombre}.json"

        with open(ruta_transcripcion, "w", encoding="utf-8") as f:
            f.write(transcripcion)

        ejecutar_sp("SetTranscription", [transaction_id, ruta_transcripcion, os.path.basename(ruta_transcripcion)])

        evaluacion = analizar_transcripcion(transcripcion, archivo_original)

        with open(ruta_evaluacion_json, "w", encoding="utf-8") as f:
            json.dump(evaluacion, f, ensure_ascii=False, indent=4)

        with open(ruta_evaluacion_txt, "w", encoding="utf-8") as f:
            f.write(json.dumps(evaluacion, ensure_ascii=False, indent=4))

        ejecutar_sp("SetAnalysis", [transaction_id, ruta_evaluacion_json, os.path.basename(ruta_evaluacion_json)])

        log(f"Proceso finalizado para {transaction_id} con {proveedor_nombre}")
    except Exception as e:
        log(f"Error en procesar_audio: {e}")
        log(traceback.format_exc())