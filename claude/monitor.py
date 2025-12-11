import time
import threading
from log import log
from connection_settings import RETRY_TIME

def monitor_server(stop_event, server_thread, create_server_fn):
    while not stop_event.is_set():
        time.sleep(RETRY_TIME * 60)

        alive = server_thread.is_alive()
        if not alive:
            log("Servidor caído. Reiniciando...")
            new_event = threading.Event()
            new_thread = threading.Thread(target=create_server_fn, args=(new_event,), daemon=True)
            new_thread.start()
        else:
            log("Monitor OK")
