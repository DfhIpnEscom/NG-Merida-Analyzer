"""
Main mejorado con sistema de recuperación automática
"""
import threading
import time
import sys

from sql_poller_improved import get_poller, start_polling, stop_polling
from debug_mode import run_debug_once
from signals_handler import register_signals
from connection_settings import SQL_POLLING_CONFIG
from log import get_logger
from recovery_system import get_watchdog

logger = get_logger()

def main():
    """Función principal con watchdog y recuperación"""
    
    # Verificar configuración
    if not SQL_POLLING_CONFIG.get('enabled', False):
        logger.error("=" * 60)
        logger.error("ERROR: SQL Polling deshabilitado en config.json")
        logger.error("Habilite 'sql_polling.enabled' en config.json")
        logger.error("=" * 60)
        return 1
    
    logger.info("=" * 60)
    logger.info("AI EVALUATOR CON SQL POLLING - INICIANDO")
    logger.info("=" * 60)
    
    # Evento de detención global
    main_stop = threading.Event()
    
    # Registrar señales de sistema
    register_signals(main_stop)
    
    # Iniciar SQL Polling
    try:
        start_polling()
    except Exception as e:
        logger.error(f"Error crítico iniciando SQL Polling: {e}", exc_info=True)
        return 1
    
    # Configurar Watchdog para monitoreo automático
    watchdog = get_watchdog()
    poller = get_poller()
    
    # Registrar componente SQL Poller para monitoreo
    watchdog.register_component(
        name="SQL_Poller",
        health_check_func=poller.is_healthy,
        restart_func=lambda: (stop_polling(), start_polling())
    )
    
    # Iniciar watchdog
    watchdog.start()
    logger.info("✓ Watchdog de monitoreo iniciado")
    
    # Ejecutar modo debug si está habilitado
    run_debug_once()
    
    # Loop principal
    logger.info("=" * 60)
    logger.info("SISTEMA EN EJECUCIÓN")
    logger.info("Presione Ctrl+C para detener")
    logger.info("=" * 60)
    
    try:
        cycle = 0
        while not main_stop.is_set():
            time.sleep(60)  # Cada minuto
            cycle += 1
            
            # Cada 10 minutos, mostrar estadísticas
            if cycle % 10 == 0:
                stats = watchdog.get_stats()
                logger.info(f"📊 Estadísticas (ciclo {cycle}):")
                for component, data in stats.items():
                    logger.info(f"  - {component}: Reinicios={data['restart_count']}")
                
    except KeyboardInterrupt:
        logger.info("⚠ Interrupción por teclado detectada")
    except Exception as e:
        logger.error(f"✗ Error fatal en main loop: {e}", exc_info=True)
        return 1
    finally:
        # Limpieza al salir
        logger.info("=" * 60)
        logger.info("DETENIENDO SISTEMA...")
        logger.info("=" * 60)
        
        watchdog.stop()
        stop_polling()
        
        logger.info("✓ Sistema detenido correctamente")
        logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
