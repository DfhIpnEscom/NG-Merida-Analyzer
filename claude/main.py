import threading
import time

from socket_connection import iniciar_socket_server
from monitor import monitor_server
from debug_mode import run_debug_once
from signals_handler import register_signals
from log import log

if __name__ == "__main__":
    server_stop = threading.Event()
    server_thread = threading.Thread(target=iniciar_socket_server, args=(server_stop,), daemon=True)
    server_thread.start()

    register_signals(server_stop)

    monitor_stop = threading.Event()
    monitor_thread = threading.Thread(target=monitor_server, args=(monitor_stop, server_thread, iniciar_socket_server), daemon=True)
    monitor_thread.start()

    run_debug_once()

    try:
        while True:
            time.sleep(1)
    except Exception as e:
        log(f"Error fatal: {e}")
