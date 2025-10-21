import os
import re
import json
import socket
import threading
import speech_recognition as sr
from pydub import AudioSegment
from math import ceil
import google.generativeai as genai
import pyodbc
from datetime import datetime


# CONFIGURACION GLOBAL

CONFIG_PATH = "config.json"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

API_KEY = config["api_key"]
PROMPT_TEMPLATE = config["prompt"]
DB_CONNECTION_STRING = config["db_connection"]
SERVER_HOST = config["server_host"]
SERVER_PORT = config["server_port"]

genai.configure(api_key=API_KEY)

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
    prompt = PROMPT_TEMPLATE.replace("{call_text}", call_text)
    model = genai.GenerativeModel("models/gemini-2.5-pro")

    response = model.generate_content(prompt)

    texto = response.text.strip()

    # Intento de limpieza a texto extra en algun json
    if "{" in texto and "}" in texto:
        try:
            json_str = texto[texto.index("{"): texto.rindex("}") + 1]
            analisis = json.loads(json_str)
        except Exception as e:
            print(f"Error al decodificar JSON limpio: {e}")
            analisis = {"raw_response": texto}
    else:
        print("Gemini no devolvio JSON, guardando texto bruto.")
        analisis = {"raw_response": texto}

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
        "recomendacion": analisis.get("recomendacion", "")
    }

    return evaluacion_estandar


# Procesamiento de audio

def procesar_audio(transaction_id, archivo_original):
    print(f"\n Procesando TransactionId: {transaction_id}")
    transcripcion = transcribir_audio(archivo_original)
    if not transcripcion:
        print("No se obtuvo transcripcion.")
        return

    # Rutas de salida
    base, _ = os.path.splitext(archivo_original)
    ruta_transcripcion = f"{base};transcripcion.txt"
    ruta_evaluacion_txt = f"{base};evaluacion.txt"
    ruta_evaluacion_json = f"{base};evaluacion.json"

    # Guardar transcripcion como txt
    with open(ruta_transcripcion, "w", encoding="utf-8") as f:
        f.write(transcripcion)

    ejecutar_sp("SetTranscription", [transaction_id, ruta_transcripcion, os.path.basename(ruta_transcripcion)])

    # Analizar transcripcion
    evaluacion = analizar_transcripcion(transcripcion, archivo_original)

    with open(ruta_evaluacion_json, "w", encoding="utf-8") as f:
        json.dump(evaluacion, f, ensure_ascii=False, indent=4)

    with open(ruta_evaluacion_txt, "w", encoding="utf-8") as f:
        f.write(json.dumps(evaluacion, ensure_ascii=False, indent=4))

    ejecutar_sp("SetAnalysis", [transaction_id, ruta_evaluacion_json, os.path.basename(ruta_evaluacion_json)])

    print(f" Proceso Finalizado Para {transaction_id}")

# Inicio de conexion mediante Socket

def manejar_cliente(conn, addr):
    print(f" Conexion exitosa establecida desde {addr}")
    data = conn.recv(4096).decode("utf-8")

    try:
        mensaje = json.loads(data)
        print(f" Mensaje recibido: {mensaje}");
        transaction_id = mensaje["transaction_id"]
        audio_path = mensaje["audio_path"]

        if os.path.exists(audio_path):
            procesar_audio(transaction_id, audio_path)
            respuesta = {"status": "ok", "transaction_id": transaction_id}
        else:
            respuesta = {"status": "error", "mensaje": "Archivo no encontrado"}
    except Exception as e:
        respuesta = {"status": "error", "mensaje": str(e)}

    conn.send(json.dumps(respuesta).encode("utf-8"))
    conn.close()
    print(f" ATENCION: Conexion cerrada {addr}")

def iniciar_socket_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SERVER_HOST, SERVER_PORT))
    server.listen(5)
    print(f"Servidor escuchando en {SERVER_HOST}:{SERVER_PORT}")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=manejar_cliente, args=(conn, addr)).start()

# Ejcucion del programa
if __name__ == "__main__":
    iniciar_socket_server()
