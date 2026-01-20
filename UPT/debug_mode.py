from connection_settings import DEBUG_MODE
from log import get_logger
from audio_process import procesar_audio_completo
import os
import traceback

logger = get_logger()


def run_debug_once():
    """Ejecuta el modo debug una sola vez al iniciar (si está habilitado)"""
    if not DEBUG_MODE.get("enabled", False):
        return

    wav = DEBUG_MODE.get("wav_file")
    if not wav or not os.path.exists(wav):
        logger.error(f"✗ Debug: Archivo WAV no encontrado: {wav}")
        return

    logger.info("=" * 60)
    logger.info("🔧 MODO DEBUG ACTIVADO")
    logger.info("=" * 60)
    logger.info(f"Archivo: {wav}")
    logger.info(f"TransactionId: 999999")
    logger.info("NOTA: Procesamiento en modo standalone (sin BD)")
    logger.info("Los pollers están PAUSADOS durante el debug")
    logger.info("Procesando...")
    logger.info("=" * 60)
    
    try:
        # Procesar directamente sin verificar BD
        success, tokens_in, tokens_out = procesar_audio_completo(999999, wav)
        
        logger.info("=" * 60)
        if success:
            logger.info("✓ DEBUG COMPLETADO EXITOSAMENTE")
            logger.info(f"Tokens usados: IN={tokens_in}, OUT={tokens_out}")
        else:
            logger.warning("⚠ DEBUG COMPLETADO CON ADVERTENCIAS")
            logger.warning("El archivo de audio no pudo procesarse completamente")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Error en modo debug: {e}")
        logger.error(traceback.format_exc())
        logger.info("=" * 60)