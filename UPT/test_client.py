"""
Script de ejemplo para probar el envío de audio al servidor
"""
import socket
import json
import sys


def enviar_audio_servidor(transaction_id, audio_path, host="192.168.1.183", port=13000):
    """
    Envía un audio al servidor para procesar
    
    Args:
        transaction_id: ID único de la transacción
        audio_path: Ruta completa al archivo de audio
        host: Dirección del servidor
        port: Puerto del servidor
    
    Returns:
        dict: Respuesta del servidor
    """
    mensaje = {
        "transaction_id": transaction_id,
        "audio_path": audio_path
    }
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print(f"Conectando a {host}:{port}...")
            s.connect((host, port))
            
            print(f"Enviando audio: {audio_path}")
            s.sendall(json.dumps(mensaje).encode("utf-8"))
            
            print("Esperando respuesta...")
            respuesta = s.recv(4096)
            
            resultado = json.loads(respuesta.decode("utf-8"))
            print(f"Respuesta recibida: {resultado}")
            
            return resultado
            
    except ConnectionRefusedError:
        print(f"ERROR: No se pudo conectar al servidor {host}:{port}")
        print("Verifica que el servidor esté ejecutándose")
        return {"status": "error", "mensaje": "Servidor no disponible"}
    
    except Exception as e:
        print(f"ERROR: {e}")
        return {"status": "error", "mensaje": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python test_client.py <transaction_id> <ruta_audio>")
        print("Ejemplo: python test_client.py 12345 /ruta/al/audio.wav")
        sys.exit(1)
    
    transaction_id = int(sys.argv[1])
    audio_path = sys.argv[2]
    
    resultado = enviar_audio_servidor(transaction_id, audio_path)
    
    if resultado.get("status") == "ok":
        print("\n✅ Audio enviado exitosamente")
    else:
        print(f"\n❌ Error: {resultado.get('mensaje', 'Desconocido')}")