import os
import json
import socket
import threading
import traceback
import speech_recognition as sr
from pydub import AudioSegment
from math import ceil
import google.generativeai as genai
import pyodbc
from datetime import datetime
import time
import tempfile
import signal
import sys

# Detectar la carpeta donde se encuentra el exe o el script
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

API_KEY = config.get("api_key", "")
PROMPT_TEMPLATE = config.get("prompt", "")
DB_CONNECTION_STRING = config.get("db_connection", "")
SERVER_HOST = config.get("server_host", "0.0.0.0")
SERVER_PORT = int(config.get("server_port", 13000))
RETRY_TIME = int(config.get("retry_time", 5))  # en minutos
DEBUG_MODE = config.get("debug_mode", {"enabled": False})

genai.configure(api_key=API_KEY)


# Globals para control del servidor
_server_thread = None
_server_stop_event = threading.Event()
_server_lock = threading.Lock()
_last_server_ready = None

# utilidades
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


# Conexion a SQL

def ejecutar_sp(nombre_sp, parametros):
    try:
        with pyodbc.connect(DB_CONNECTION_STRING) as conn:
            cursor = conn.cursor()
            placeholders = ", ".join(["?"] * len(parametros))
            query = f"EXEC {nombre_sp} {placeholders}"
            cursor.execute(query, *parametros)
            conn.commit()
            print(f"{nombre_sp} ejecutado correctamente con {parametros}")
    except Exception as e:
        print(f"Error al ejecutar {nombre_sp}: {e}")

# trnascripcion

def transcribir_audio(archivo_original):
    archivo_convertido = "temp_pcm.wav"
    print(" Convirtiendo el audio...")
    sound = AudioSegment.from_file(archivo_original)
    sound = sound.set_frame_rate(16000).set_channels(1)
    sound.export(archivo_convertido, format="wav")

    recognizer = sr.Recognizer()
    audio = AudioSegment.from_wav(archivo_convertido)
    segment_duration = 60 * 1000
    num_segments = ceil(len(audio) / segment_duration)

    transcripcion = ""
    for i in range(num_segments):
        inicio = i * segment_duration
        fin = min((i + 1) * segment_duration, len(audio))
        fragmento = audio[inicio:fin]
        fragment_path = f"temp_fragment_{i}.wav"
        fragmento.export(fragment_path, format="wav")

        with sr.AudioFile(fragment_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio_data = recognizer.record(source)

        try:
            texto = recognizer.recognize_google(audio_data, language="es-ES")
            transcripcion += texto + " "
            print(f"Fragmento {i+1}/{num_segments}: OK")
        except sr.UnknownValueError:
            print(f"Fragmento {i+1}/{num_segments}: no se entiende el audio.")
        except sr.RequestError as e:
            print(f"Error de conexion en el fragmento {i+1}: {e}")
            break
        finally:
            os.remove(fragment_path)

    os.remove(archivo_convertido)
    return transcripcion.strip()


# Anlaisis GEMINI
def analizar_transcripcion(call_text, archivo_original):
    model = genai.GenerativeModel("models/gemini-2.5-pro")

    # separacion A/C
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
        response_transcripcion = model.generate_content(prompt_transcripcion)
        texto_transcripcion = response_transcripcion.text.strip()
        json_str = texto_transcripcion[texto_transcripcion.index("{"): texto_transcripcion.rindex("}") + 1]
        transcripcion_json = json.loads(json_str)
    except Exception as e:
        print(f"Error al parsear la transcripción separada: {e}")
        transcripcion_json = {"transcription": [{"type": "Desconocido", "message": call_text}]}

    # Evaluacion
    prompt = PROMPT_TEMPLATE.replace("{call_text}", call_text)
    response = model.generate_content(prompt)
    texto = response.text.strip()

    if "{" in texto and "}" in texto:
        try:
            json_str = texto[texto.index("{"): texto.rindex("}") + 1]
            analisis = json.loads(json_str)
        except Exception as e:
            print(f"Error al decodificar JSON limpio: {e}")
            analisis = {"raw_response": texto}
    else:
        print("Gemini no devolvió JSON, guardando texto bruto.")
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

        base, _ = os.path.splitext(archivo_original)
        ruta_transcripcion = f"{base};transcripcion.txt"
        ruta_evaluacion_txt = f"{base};evaluacion.txt"
        ruta_evaluacion_json = f"{base};evaluacion.json"

        with open(ruta_transcripcion, "w", encoding="utf-8") as f:
            f.write(transcripcion)

        ejecutar_sp("SetTranscription", [transaction_id, ruta_transcripcion, os.path.basename(ruta_transcripcion)])

        evaluacion = analizar_transcripcion(transcripcion, archivo_original)

        with open(ruta_evaluacion_json, "w", encoding="utf-8") as f:
            json.dump(evaluacion, f, ensure_ascii=False, indent=4)

        with open(ruta_evaluacion_txt, "w", encoding="utf-8") as f:
            f.write(json.dumps(evaluacion, ensure_ascii=False, indent=4))

        ejecutar_sp("SetAnalysis", [transaction_id, ruta_evaluacion_json, os.path.basename(ruta_evaluacion_json)])

        log(f"Proceso finalizado para {transaction_id}")
    except Exception as e:
        log(f"Error en procesar_audio: {e}")
        log(traceback.format_exc())

# Inicio de conexion mediante Socket
def manejar_cliente(conn, addr):
    log(f"Conexión desde {addr}")
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk

        if not data:
            respuesta = {"status": "error", "mensaje": "No se recibieron datos"}
            conn.send(json.dumps(respuesta).encode("utf-8"))
            conn.close()
            return

        try:
            mensaje = json.loads(data.decode("utf-8"))
            log(f"Mensaje recibido: {mensaje}")
            transaction_id = mensaje.get("transaction_id")
            audio_path = mensaje.get("audio_path")

            if audio_path and os.path.exists(audio_path):
                procesar_audio(transaction_id, audio_path)
                respuesta = {"status": "ok", "transaction_id": transaction_id}
            else:
                respuesta = {"status": "error", "mensaje": "Archivo no encontrado"}
        except Exception as e:
            log(f"Error procesando mensaje JSON: {e}")
            respuesta = {"status": "error", "mensaje": str(e)}

        try:
            conn.send(json.dumps(respuesta).encode("utf-8"))
        except Exception as e:
            log(f"Error enviando respuesta al cliente: {e}")
    finally:
        try:
            conn.close()
        except:
            pass
        log(f"Conexión cerrada {addr}")


def iniciar_socket_server(stop_event):
    global _last_server_ready
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((SERVER_HOST, SERVER_PORT))
        server.listen(5)
        _last_server_ready = datetime.now()
        log(f"Servidor escuchando en {SERVER_HOST}:{SERVER_PORT}")
    except Exception as e:
        log(f"No fue posible enlazar el socket: {e}")
        return

    # aaqui se aceptan conexiones hasta que se dejen de obeneter
    try:
        while not stop_event.is_set():
            try:
                server.settimeout(1.0)
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=manejar_cliente, args=(conn, addr), daemon=True).start()
            except Exception as e:
                log(f"Error en bucle accept: {e}")
    finally:
        try:
            server.close()
        except:
            pass
        log("Servidor socket detenido.")


# monitor y reinicio
def monitor_server(stop_event):
    global _server_thread, _server_stop_event
    while not stop_event.is_set():
        time.sleep(RETRY_TIME * 60)
        if stop_event.is_set():
            break

        with _server_lock:
            alive = _server_thread is not None and _server_thread.is_alive()
            if not alive:
                log("Detectado servidor no vivo. Reiniciando servidor...")
                # intentar reiniciar
                _server_stop_event = threading.Event()
                _server_thread = threading.Thread(target=iniciar_socket_server, args=(_server_stop_event,), daemon=True)
                _server_thread.start()
                log("Servidor reiniciado por monitor.")
            else:
                log("Monitor: servidor OK.")


# Degug mode, en caso de habilitar para pruebas
def run_debug_once():
    enabled = bool(DEBUG_MODE.get("enabled", False))
    wav_file = DEBUG_MODE.get("wav_file", "")
    if not enabled:
        return
    if not wav_file:
        log("Debug mode activado pero no hay 'wav_file' en config.")
        return
    if not os.path.exists(wav_file):
        log(f"Debug wav_file no encontrado: {wav_file}")
        return

    log("=== MODO DEBUG: procesando archivo de prueba ===")
    try:
        procesar_audio(transaction_id=999999, archivo_original=wav_file)
    except Exception as e:
        log(f"Error en debug processing: {e}")
        log(traceback.format_exc())
    log("=== FIN MODO DEBUG ===")


# manejador de señales paa ciereres
def _signal_handler(sig, frame):
    log("Recibida señal de terminación. Deteniendo servidor...")
    _server_stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# === EJECUCION PRINCIPAL ===
if __name__ == "__main__":
    try:
        # server
        _server_stop_event = threading.Event()
        _server_thread = threading.Thread(target=iniciar_socket_server, args=(_server_stop_event,), daemon=True)
        _server_thread.start()

        # monitor
        monitor_stop = threading.Event()
        monitor_thread = threading.Thread(target=monitor_server, args=(monitor_stop,), daemon=True)
        monitor_thread.start()

        # en caso de estar activado el debug se pruba sin detener
        run_debug_once()

        # Loop principal que maniticne acitviidad
        while True:
            time.sleep(1)
    except Exception as e:
        log(f"Error fatal en main: {e}")
        log(traceback.format_exc())
