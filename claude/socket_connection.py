import socket
import threading
import json
from log import log
from audio_process import procesar_audio
from connection_settings import SERVER_HOST, SERVER_PORT
import os
from datetime import datetime

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

    # aqui se aceptan conexiones hasta que se dejen de obtener
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


