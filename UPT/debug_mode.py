"""
Modo debug mejorado - evita procesamiento duplicado
"""
from connection_settings import DEBUG_MODE
from log import get_logger
from audio_process import procesar_audio_completo
import os
import traceback
import pyodbc
from connection_settings import DB_CONNECTION_STRING

logger = get_logger()


def ensure_transaction_exists(transaction_id, wav_file):
    """
    Asegura que el TransactionId existe en la BD, si no lo crea
    
    Args:
        transaction_id: ID de la transacción de debug
        wav_file: Ruta del archivo WAV
    
    Returns:
        bool: True si existe o se creó exitosamente
    """
    try:
        with pyodbc.connect(DB_CONNECTION_STRING, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Verificar si existe
            cursor.execute(
                "SELECT COUNT(*) FROM AudioQueue WHERE TransactionId = ?",
                transaction_id
            )
            count = cursor.fetchone()[0]
            
            if count > 0:
                logger.info(f"✔ TransactionId {transaction_id} ya existe en BD")
                # Marcar como 'Procesando' para evitar que los pollers lo tomen
                cursor.execute(
                    "UPDATE AudioQueue SET Estado = 'Procesando' WHERE TransactionId = ?",
                    transaction_id
                )
                conn.commit()
                return True
            
            # No existe, crear el registro en estado 'Procesando'
            logger.info(f"Creando TransactionId {transaction_id} en BD para debug...")
            
            # Usar SET IDENTITY_INSERT para insertar con ID específico
            cursor.execute("""
                SET IDENTITY_INSERT AudioQueue ON;
                
                INSERT INTO AudioQueue (TransactionId, RutaAudio, Estado, FechaCreacion)
                VALUES (?, ?, 'Procesando', GETDATE());
                
                SET IDENTITY_INSERT AudioQueue OFF;
            """, transaction_id, wav_file)
            
            conn.commit()
            logger.info(f"✔ TransactionId {transaction_id} creado exitosamente (Estado: Procesando)")
            return True
            
    except Exception as e:
        logger.error(f"Error verificando/creando TransactionId: {e}")
        logger.error(traceback.format_exc())
        return False


def cleanup_debug_transaction(transaction_id):
    """
    Limpia el registro de debug después de completar
    
    Args:
        transaction_id: ID de la transacción de debug
    """
    try:
        with pyodbc.connect(DB_CONNECTION_STRING, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Opción 1: Eliminar el registro de debug
            cursor.execute(
                "DELETE FROM AudioQueue WHERE TransactionId = ?",
                transaction_id
            )
            conn.commit()
            logger.info(f"Registro de debug {transaction_id} eliminado")
            
    except Exception as e:
        logger.warning(f"No se pudo eliminar registro de debug: {e}")


def run_debug_once():
    """Ejecuta el modo debug una sola vez al iniciar (si está habilitado)"""
    if not DEBUG_MODE.get("enabled", False):
        return

    wav = DEBUG_MODE.get("wav_file")
    if not wav or not os.path.exists(wav):
        logger.error(f"X Debug: Archivo WAV no encontrado: {wav}")
        return

    logger.info("=" * 60)
    logger.info("🔧 MODO DEBUG ACTIVADO")
    logger.info("=" * 60)
    logger.info(f"Archivo: {wav}")
    logger.info(f"TransactionId: 999999")
    logger.info("NOTA: Los pollers están bloqueados durante el debug")
    
    # Asegurar que el registro existe en BD (Estado = 'Procesando')
    if not ensure_transaction_exists(999999, wav):
        logger.error(" No se pudo crear el registro de debug en BD")
        logger.info("=" * 60)
        return
    
    logger.info("Procesando...")
    logger.info("=" * 60)
    
    try:
        procesar_audio_completo(999999, wav)
        logger.info("=" * 60)
        logger.info("✔ DEBUG COMPLETADO")
        
        # Limpiar el registro de debug
        logger.info("Limpiando registro de debug...")
        cleanup_debug_transaction(999999)
        
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"X Error en modo debug: {e}")
        logger.error(traceback.format_exc())
        
        # Intentar limpiar de todas formas
        try:
            cleanup_debug_transaction(999999)
        except:
            pass
        
        logger.info("=" * 60)