import json
import traceback
import anthropic
from datetime import datetime
from connection_settings import API_KEY, MODEL, PROMPT_TEMPLATE
from log import log
import os

client = anthropic.Anthropic(api_key=API_KEY)

# Analisis con CLAUDE 
def analizar_transcripcion(call_text, archivo_original):
    # Separacion A/C
    prompt_transcripcion = f"""
Transcribe y separa la conversación dada en bloques hablados por el Agente o el Cliente.
Devuelve el resultado exclusivamente en formato JSON con esta estructura exacta:

{{
  "transcription": [
    {{"type": "Agente", "message": "Texto del agente"}},
    {{"type": "Cliente", "message": "Texto del cliente"}}
  ]
}}

Aquí está la transcripción original para analizar:
{call_text}
"""
    try:
        response_transcripcion = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt_transcripcion}
            ]
        )
        texto_transcripcion = response_transcripcion.content[0].text.strip()
        json_str = texto_transcripcion[texto_transcripcion.index("{"): texto_transcripcion.rindex("}") + 1]
        transcripcion_json = json.loads(json_str)
    except Exception as e:
        print(f"Error al parsear la transcripción separada: {e}")
        traceback.print_exc()
        transcripcion_json = {"transcription": [{"type": "Desconocido", "message": call_text}]}

    # Evaluacion
    prompt = PROMPT_TEMPLATE.replace("{call_text}", call_text)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        texto = response.content[0].text.strip()
    except Exception as e:
        print(f"Error al llamar a Claude para evaluación: {e}")
        traceback.print_exc()
        texto = ""

    if "{" in texto and "}" in texto:
        try:
            json_str = texto[texto.index("{"): texto.rindex("}") + 1]
            analisis = json.loads(json_str)
        except Exception as e:
            print(f"Error al decodificar JSON limpio: {e}")
            analisis = {"raw_response": texto}
    else:
        print("Claude no devolvió JSON, guardando texto bruto.")
        analisis = {"raw_response": texto}

    # Estructura
    base, _ = os.path.splitext(archivo_original)
    nombre_base = os.path.basename(base)
    evaluacion_estandar = {
        "id_llamada": nombre_base,
        "fecha_evaluacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ruta_audio": archivo_original,
        "criterios": analisis.get("criterios", {}),
        "scores": {
            "puntuacion_final": analisis.get("puntuacion_final", 0),
            "puntuacion_transcripcion": analisis.get("puntuacion_transcripcion", 0)
        },
        "recomendacion": analisis.get("recomendacion", ""),
        "transcripcion_json": transcripcion_json
    }

    # Json transcripcion
    ruta_transcripcion_json = f"{base};transcripcion.json"
    try:
        with open(ruta_transcripcion_json, "w", encoding="utf-8") as f:
            json.dump(transcripcion_json, f, ensure_ascii=False, indent=4)
        print(f"Transcripción JSON guardada en {ruta_transcripcion_json}")
    except Exception as e:
        print(f"Error guardando {ruta_transcripcion_json}: {e}")

    return evaluacion_estandar
