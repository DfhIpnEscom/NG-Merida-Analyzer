import socket
import json

mensaje = {
    "transaction_id": 101,
    "audio_path": r"D:\Amatech\Transcriptor y evaluador de llamadas\Arc_prueba\DMCC_ext23580_2025_10_15_13;22;11;989.wav"
}

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect(("127.0.0.1", 5000))
    s.send(json.dumps(mensaje).encode("utf-8"))
    respuesta = s.recv(4096)
    print(respuesta.decode("utf-8"))
