import signal
import sys
from log import log

def register_signals(stop_event):
    def handler(sig, frame):
        log("Terminando aplicación...")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
