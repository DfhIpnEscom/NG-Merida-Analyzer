"""
Sistema de recuperación automática y manejo de errores
"""
import time
import threading
import traceback
from datetime import datetime, timedelta
from log import get_logger

logger = get_logger()

class RecoveryManager:
    """Gestiona recuperación automática de fallos"""
    
    def __init__(self, max_retries=3, retry_delay=60):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.failure_count = {}
        self.last_failure = {}
    
    def execute_with_recovery(self, func, func_name, *args, **kwargs):
        """
        Ejecuta función con reintentos automáticos
        
        Args:
            func: Función a ejecutar
            func_name: Nombre identificador
            *args, **kwargs: Argumentos de la función
        
        Returns:
            tuple: (success: bool, result: any)
        """
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                result = func(*args, **kwargs)
                
                # Resetear contador si tiene éxito
                if func_name in self.failure_count:
                    logger.info(f"✓ {func_name} recuperado después de {self.failure_count[func_name]} fallos")
                    del self.failure_count[func_name]
                
                return True, result
                
            except Exception as e:
                retry_count += 1
                self.failure_count[func_name] = self.failure_count.get(func_name, 0) + 1
                self.last_failure[func_name] = datetime.now()
                
                logger.error(
                    f"✗ Error en {func_name} (intento {retry_count}/{self.max_retries}): {e}",
                    exc_info=True
                )
                
                if retry_count < self.max_retries:
                    logger.info(f"↻ Reintentando en {self.retry_delay} segundos...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"✗✗✗ {func_name} falló después de {self.max_retries} intentos")
        
        return False, None
    
    def get_failure_stats(self):
        """Retorna estadísticas de fallos"""
        return {
            'failure_count': self.failure_count.copy(),
            'last_failure': self.last_failure.copy()
        }


class WatchdogMonitor:
    """Monitor que reinicia componentes si fallan"""
    
    def __init__(self, check_interval=300):  # 5 minutos
        self.check_interval = check_interval
        self.components = {}
        self.stop_event = threading.Event()
        self.monitor_thread = None
    
    def register_component(self, name, health_check_func, restart_func):
        """
        Registra componente para monitoreo
        
        Args:
            name: Nombre del componente
            health_check_func: Función que retorna True si está saludable
            restart_func: Función para reiniciar el componente
        """
        self.components[name] = {
            'health_check': health_check_func,
            'restart': restart_func,
            'last_check': None,
            'restart_count': 0,
            'last_restart': None
        }
        logger.info(f"Componente registrado para watchdog: {name}")
    
    def _monitor_loop(self):
        """Bucle de monitoreo"""
        logger.info("Watchdog iniciado")
        
        while not self.stop_event.is_set():
            try:
                for name, component in self.components.items():
                    try:
                        is_healthy = component['health_check']()
                        component['last_check'] = datetime.now()
                        
                        if not is_healthy:
                            logger.warning(f"⚠ Componente {name} NO saludable, reiniciando...")
                            component['restart']()
                            component['restart_count'] += 1
                            component['last_restart'] = datetime.now()
                            logger.info(f"↻ {name} reiniciado (total: {component['restart_count']})")
                        
                    except Exception as e:
                        logger.error(f"Error monitoreando {name}: {e}", exc_info=True)
                
            except Exception as e:
                logger.error(f"Error en watchdog loop: {e}", exc_info=True)
            
            self.stop_event.wait(self.check_interval)
        
        logger.info("Watchdog detenido")
    
    def start(self):
        """Inicia el monitor"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Watchdog ya está en ejecución")
            return
        
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Watchdog iniciado")
    
    def stop(self):
        """Detiene el monitor"""
        logger.info("Deteniendo watchdog...")
        self.stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
    
    def get_stats(self):
        """Retorna estadísticas de monitoreo"""
        stats = {}
        for name, component in self.components.items():
            stats[name] = {
                'last_check': component['last_check'],
                'restart_count': component['restart_count'],
                'last_restart': component['last_restart']
            }
        return stats


class TimeoutManager:
    """Maneja timeouts para operaciones largas"""
    
    @staticmethod
    def run_with_timeout(func, timeout_seconds, *args, **kwargs):
        """
        Ejecuta función con timeout
        
        Args:
            func: Función a ejecutar
            timeout_seconds: Tiempo máximo de ejecución
        
        Returns:
            tuple: (success: bool, result: any)
        """
        result = [None]
        exception = [None]
        
        def wrapper():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)
        
        if thread.is_alive():
            logger.error(f"⏱ Timeout: función excedió {timeout_seconds}s")
            return False, None
        
        if exception[0]:
            logger.error(f"Error en función: {exception[0]}", exc_info=True)
            return False, None
        
        return True, result[0]


# Instancias globales
_recovery_manager = None
_watchdog_monitor = None

def get_recovery_manager():
    """Obtiene instancia del recovery manager"""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = RecoveryManager()
    return _recovery_manager

def get_watchdog():
    """Obtiene instancia del watchdog"""
    global _watchdog_monitor
    if _watchdog_monitor is None:
        _watchdog_monitor = WatchdogMonitor()
    return _watchdog_monitor
