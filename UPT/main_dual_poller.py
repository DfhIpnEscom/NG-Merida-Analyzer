"""
Main con sistema dual polling ✔
"""
import threading
import time
import sys

from dual_poller_system import (
    start_all_pollers,
    stop_all_pollers,
    get_transcription_poller,
    get_analysis_poller,
    get_all_stats
)
from debug_mode import run_debug_once
from signals_handler import register_signals
from connection_settings import SQL_POLLING_CONFIG, PROCESSING_FEATURES
from log import get_logger
from recovery_system import get_watchdog
from token_manager import get_token_manager

logger = get_logger()
token_manager = get_token_manager()


def main():
    """Funcion principal sistema dual polling"""
    
    # Verificar configuración
    if not SQL_POLLING_CONFIG.get('enabled', False):
        logger.error("=" * 60)
        logger.error("ERROR: SQL Polling deshabilitado en config.json")
        logger.error("Habilite 'sql_polling.enabled' en config.json")
        logger.error("=" * 60)
        return 1
    
    logger.info("=" * 60)
    logger.info("AI EVALUATOR - SISTEMA DUAL DE POLLING")
    logger.info("=" * 60)
    logger.info(f"Transcripción: {'✔ HABILITADA' if PROCESSING_FEATURES.get('transcription_enabled') else '❌ DESHABILITADA'}")
    logger.info(f"Análisis: {'✔ HABILITADO' if PROCESSING_FEATURES.get('analysis_enabled') else '❌ DESHABILITADO'}")
    logger.info("=" * 60)
    
    # Mostrar uso de tokens al iniciar
    logger.info("\n" + token_manager.get_usage_summary())
    logger.info("=" * 60)
    
    # Evento de detención global
    main_stop = threading.Event()
    
    # Registrar señales de sistema
    register_signals(main_stop)
    
    # Iniciar pollers
    try:
        start_all_pollers()
    except Exception as e:
        logger.error(f"Error crítico iniciando pollers: {e}", exc_info=True)
        return 1
    
    # Configurar Watchdog para monitoreo automático
    watchdog = get_watchdog()
    
    # Registrar componentes para monitoreo
    if PROCESSING_FEATURES.get('transcription_enabled', True):
        trans_poller = get_transcription_poller()
        watchdog.register_component(
            name="Transcription_Poller",
            health_check_func=trans_poller.is_healthy,
            restart_func=lambda: (trans_poller.stop(), trans_poller.start())
        )
    
    if PROCESSING_FEATURES.get('analysis_enabled', True):
        anal_poller = get_analysis_poller()
        watchdog.register_component(
            name="Analysis_Poller",
            health_check_func=anal_poller.is_healthy,
            restart_func=lambda: (anal_poller.stop(), anal_poller.start())
        )
    
    # Iniciar watchdog
    watchdog.start()
    logger.info("✔ Watchdog de monitoreo iniciado")
    
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
                logger.info("\n" + "=" * 60)
                logger.info(f"ESTADÍSTICAS (ciclo {cycle})")
                logger.info("=" * 60)
                
                # Estadísticas de pollers
                stats = get_all_stats()
                for poller_name, data in stats.items():
                    logger.info(
                        f"  {poller_name.upper()}: "
                        f"Procesados={data.get('processed', 0)} | "
                        f"Fallidos={data.get('failed', 0)} | "
                        f"Errores={data.get('errors', 0)}"
                    )
                
                # Estadísticas de watchdog
                watchdog_stats = watchdog.get_stats()
                for component, data in watchdog_stats.items():
                    logger.info(
                        f"  {component}: Reinicios={data['restart_count']}"
                    )
                
                # Uso de tokens
                logger.info("\n" + token_manager.get_usage_summary())
                logger.info("=" * 60 + "\n")
            
    except KeyboardInterrupt:
        logger.info("! Interrupción por teclado detectada")
    except Exception as e:
        logger.error(f"X Error fatal en main loop: {e}", exc_info=True)
        return 1
    finally:
        # Limpieza al salir
        logger.info("=" * 60)
        logger.info("DETENIENDO SISTEMA...")
        logger.info("=" * 60)
        
        watchdog.stop()
        stop_all_pollers()
        
        # Mostrar estadísticas finales
        logger.info("\nESTADÍSTICAS FINALES:")
        stats = get_all_stats()
        for poller_name, data in stats.items():
            logger.info(
                f"  {poller_name.upper()}: "
                f"Procesados={data.get('processed', 0)} | "
                f"Fallidos={data.get('failed', 0)} | "
                f"Errores={data.get('errors', 0)}"
            )
        
        logger.info("\n✔ Sistema detenido correctamente")
        logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())