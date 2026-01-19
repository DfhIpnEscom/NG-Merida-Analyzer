"""
Funciones de conexión SQL actualizadas para trabajar con los nuevos SP FIFO
"""
import pyodbc
from log import get_logger
from connection_settings import DB_CONNECTION_STRING

logger = get_logger()


def ejecutar_sp(nombre_sp, parametros):
    """
    Ejecuta un stored procedure sin retorno de resultados
    
    Args:
        nombre_sp: Nombre del stored procedure
        parametros: Lista de parámetros
    """
    try:
        with pyodbc.connect(DB_CONNECTION_STRING) as conn:
            cursor = conn.cursor()
            placeholders = ", ".join(["?"] * len(parametros))
            query = f"EXEC {nombre_sp} {placeholders}"
            cursor.execute(query, *parametros)
            conn.commit()
            logger.info(f"✔ {nombre_sp} ejecutado correctamente")
            logger.debug(f"Parámetros: {parametros}")
    except Exception as e:
        logger.error(f"X Error al ejecutar {nombre_sp}: {e}", exc_info=True)
        raise


def ejecutar_query(query, parametros=None):
    """
    Ejecuta una query que retorna resultados
    
    Args:
        query: Query SQL a ejecutar
        parametros: Lista de parámetros opcionales
    
    Returns:
        list: Lista de tuplas con los resultados
    """
    try:
        with pyodbc.connect(DB_CONNECTION_STRING) as conn:
            cursor = conn.cursor()
            
            if parametros:
                cursor.execute(query, parametros)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            return results
            
    except Exception as e:
        logger.error(f"X Error al ejecutar query: {e}", exc_info=True)
        raise


def obtener_registros_pendientes(sp_name, tipo_proceso="transcription"):
    """
    Obtiene registros pendientes desde un SP (FIFO - ordenados por TransactionId ASC)
    
    Args:
        sp_name: Nombre del stored procedure
            - GetPendingTranscription: para transcripciones pendientes
            - GetPendingAnalisys: para análisis pendientes
        tipo_proceso: Tipo de proceso ("transcription" o "analysis")
    
    Returns:
        list: Lista de diccionarios con los registros
            Para transcription: [{'transaction_id', 'audio_path', 'retry_count'}]
            Para analysis: [{'transaction_id', 'audio_path', 'transcription_path', 'retry_count'}]
    """
    try:
        with pyodbc.connect(DB_CONNECTION_STRING, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute(f"EXEC {sp_name}")
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.debug(f"No hay registros pendientes de {tipo_proceso}")
                return []
            
            # Convertir a lista de diccionarios
            registros = []
            for row in rows:
                if tipo_proceso == "transcription":
                    # GetPendingTranscription retorna: TransactionId, RutaAudio, ReintentoCount
                    registros.append({
                        'transaction_id': row[0],
                        'audio_path': row[1],
                        'retry_count': row[2] if len(row) > 2 else 0
                    })
                elif tipo_proceso == "analysis":
                    # GetPendingAnalisys retorna: TransactionId, RutaAudio, RutaTranscripcion, ReintentoCount
                    registros.append({
                        'transaction_id': row[0],
                        'audio_path': row[1],
                        'transcription_path': row[2] if len(row) > 2 else None,
                        'retry_count': row[3] if len(row) > 3 else 0
                    })
                else:
                    logger.warning(f"Tipo de proceso desconocido: {tipo_proceso}")
            
            logger.debug(f"Obtenidos {len(registros)} registros pendientes de {tipo_proceso}")
            return registros
            
    except pyodbc.Error as e:
        logger.error(f"X Error de SQL obteniendo registros de {sp_name}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"X Error inesperado obteniendo registros de {sp_name}: {e}", exc_info=True)
        return []


def guardar_transcripcion(transaction_id, transcription_path, transcription_name, tokens_in, tokens_out):
    """
    Guarda el resultado de una transcripción usando SetTranscription
    
    Args:
        transaction_id: ID de la transacción
        transcription_path: Ruta completa del archivo de transcripción
        transcription_name: Nombre del archivo de transcripción
        tokens_in: Tokens de entrada usados
        tokens_out: Tokens de salida generados
    """
    try:
        ejecutar_sp(
            "SetTranscription",
            [
                transaction_id,
                transcription_path,
                transcription_name,
                tokens_in,
                tokens_out
            ]
        )
        logger.info(
            f"✔ Transcripción guardada - ID:{transaction_id} | "
            f"Tokens: IN={tokens_in} OUT={tokens_out}"
        )
    except Exception as e:
        logger.error(f"X Error guardando transcripción para ID:{transaction_id}: {e}")
        raise


def guardar_analisis(transaction_id, analysis_path, analysis_name, tokens_in, tokens_out):
    """
    Guarda el resultado de un análisis usando SetAnalysis
    
    Args:
        transaction_id: ID de la transacción
        analysis_path: Ruta completa del archivo de análisis
        analysis_name: Nombre del archivo de análisis
        tokens_in: Tokens de entrada usados
        tokens_out: Tokens de salida generados
    """
    try:
        ejecutar_sp(
            "SetAnalysis",
            [
                transaction_id,
                analysis_path,
                analysis_name,
                tokens_in,
                tokens_out
            ]
        )
        logger.info(
            f"✔ Análisis guardado - ID:{transaction_id} | "
            f"Tokens: IN={tokens_in} OUT={tokens_out}"
        )
    except Exception as e:
        logger.error(f"X Error guardando análisis para ID:{transaction_id}: {e}")
        raise


def incrementar_reintentos(transaction_id, nuevo_conteo):
    """
    Incrementa el contador de reintentos para una transacción
    
    Args:
        transaction_id: ID de la transacción
        nuevo_conteo: Nuevo valor del contador de reintentos
    """
    try:
        ejecutar_sp(
            "IncrementRetryCount",
            [transaction_id, nuevo_conteo]
        )
        logger.warning(f"! Reintentos incrementados - ID:{transaction_id} -> {nuevo_conteo}")
    except Exception as e:
        logger.error(f"X Error incrementando reintentos para ID:{transaction_id}: {e}")
        raise


def actualizar_estado(transaction_id, nuevo_estado, retry_count=None):
    """
    Actualiza el estado de una transacción
    
    Args:
        transaction_id: ID de la transacción
        nuevo_estado: Nuevo estado ('Pendiente', 'Procesando', 'Completado', 'Error')
        retry_count: Opcional - nuevo contador de reintentos
    """
    try:
        parametros = [transaction_id, nuevo_estado]
        if retry_count is not None:
            parametros.append(retry_count)
        else:
            parametros.append(None)  # SQL usará el valor actual
        
        ejecutar_sp("UpdateTransactionStatus", parametros)
        logger.info(f"✔ Estado actualizado - ID:{transaction_id} -> {nuevo_estado}")
    except Exception as e:
        logger.error(f"X Error actualizando estado para ID:{transaction_id}: {e}")
        raise


def obtener_tokens_mes(mes):
    """
    Obtiene el uso de tokens para un mes específico
    
    Args:
        mes: Número del mes (1-12)
    
    Returns:
        dict: {
            'transcription_in': int,
            'transcription_out': int,
            'analysis_in': int,
            'analysis_out': int,
            'total': int
        }
    """
    try:
        result = ejecutar_query("EXEC GetTokensUsedByMonth ?", [mes])
        
        if result and len(result) > 0:
            row = result[0]
            return {
                'transcription_in': row[0] or 0,
                'transcription_out': row[1] or 0,
                'analysis_in': row[2] or 0,
                'analysis_out': row[3] or 0,
                'total': (row[0] or 0) + (row[1] or 0) + (row[2] or 0) + (row[3] or 0)
            }
        else:
            return {
                'transcription_in': 0,
                'transcription_out': 0,
                'analysis_in': 0,
                'analysis_out': 0,
                'total': 0
            }
    except Exception as e:
        logger.error(f"X Error obteniendo tokens del mes {mes}: {e}")
        return None