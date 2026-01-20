import pyodbc
from log import get_logger
from connection_settings import DB_CONNECTION_STRING

logger = get_logger()


def ejecutar_sp(nombre_sp, parametros):
    """Ejecuta un SP con manejo de errores robusto"""
    try:
        with pyodbc.connect(DB_CONNECTION_STRING, timeout=10) as conn:
            cursor = conn.cursor()
            placeholders = ", ".join(["?"] * len(parametros))
            query = f"EXEC {nombre_sp} {placeholders}"
            cursor.execute(query, *parametros)
            conn.commit()
            logger.debug(f"✓ {nombre_sp} ejecutado correctamente")
            return True
    except pyodbc.Error as e:
        error_msg = str(e)
        # Si el SP no existe, loguear pero no fallar
        if "Could not find stored procedure" in error_msg:
            logger.debug(f"⚠ SP '{nombre_sp}' no existe en BD - Operación omitida")
            return False
        logger.error(f"✗ Error SQL en {nombre_sp}: {error_msg}")
        return False
    except Exception as e:
        logger.error(f"✗ Error inesperado en {nombre_sp}: {e}")
        return False


def ejecutar_query(query, parametros=None):
    """Ejecuta una query con manejo de errores robusto"""
    try:
        with pyodbc.connect(DB_CONNECTION_STRING, timeout=10) as conn:
            cursor = conn.cursor()
            
            if parametros:
                cursor.execute(query, parametros)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            return results
            
    except pyodbc.Error as e:
        logger.error(f"✗ Error SQL: {e}")
        return []
    except Exception as e:
        logger.error(f"✗ Error inesperado en query: {e}")
        return []


def obtener_registros_pendientes(sp_name, tipo_proceso="transcription"):
    """Obtiene registros pendientes con manejo robusto de errores"""
    try:
        with pyodbc.connect(DB_CONNECTION_STRING, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute(f"EXEC {sp_name}")
            
            # Obtener nombres de columnas
            columns = [column[0] for column in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            
            if not rows:
                return []
            
            logger.debug(f"Columnas recibidas de {sp_name}: {columns}")
            
            # Convertir a lista de diccionarios
            registros = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                
                if tipo_proceso == "transcription":
                    transaction_id = row_dict.get('TransactionId')
                    audio_path = row_dict.get('TransactionFile')
                    retry_count = row_dict.get('ReintentoCount', 0)
                    
                    if not isinstance(audio_path, str):
                        logger.warning(f"Saltando registro - audio_path inválido: TransactionId={transaction_id}")
                        continue
                    
                    registros.append({
                        'transaction_id': int(transaction_id) if transaction_id else 0,
                        'audio_path': audio_path,
                        'retry_count': int(retry_count) if retry_count else 0
                    })
                    
                elif tipo_proceso == "analysis":
                    transaction_id = row_dict.get('TransactionId')
                    audio_path = row_dict.get('TransactionFile')
                    transcription_path = row_dict.get('TranscriptionPath')
                    retry_count = row_dict.get('ReintentoCount', 0)
                    
                    if not isinstance(audio_path, str):
                        logger.warning(f"Saltando registro - audio_path inválido: TransactionId={transaction_id}")
                        continue
                    
                    registros.append({
                        'transaction_id': int(transaction_id) if transaction_id else 0,
                        'audio_path': audio_path,
                        'transcription_path': transcription_path if isinstance(transcription_path, str) else None,
                        'retry_count': int(retry_count) if retry_count else 0
                    })
            
            logger.debug(f"Obtenidos {len(registros)} registros válidos de {tipo_proceso}")
            return registros
            
    except pyodbc.Error as e:
        error_msg = str(e)
        if "Could not find stored procedure" in error_msg:
            logger.debug(f"⚠ SP '{sp_name}' no existe - Retornando lista vacía")
        else:
            logger.error(f"✗ Error SQL en {sp_name}: {error_msg}")
        return []
    except Exception as e:
        logger.error(f"✗ Error inesperado en {sp_name}: {e}")
        return []


def guardar_transcripcion(transaction_id, transcription_path, transcription_name, tokens_in, tokens_out):
    """Guarda transcripción con manejo robusto de errores"""
    try:
        success = ejecutar_sp(
            "SetTranscription",
            [
                transaction_id,
                transcription_path,
                transcription_name,
                tokens_in,
                tokens_out
            ]
        )
        
        if success:
            logger.info(
                f"✓ Transcripción guardada en BD - ID:{transaction_id} | "
                f"Tokens: IN={tokens_in} OUT={tokens_out}"
            )
        else:
            logger.debug(f"⚠ No se pudo guardar transcripción en BD para ID:{transaction_id} (SP no existe)")
            
    except Exception as e:
        logger.warning(f"⚠ Error guardando transcripción para ID:{transaction_id}: {e}")


def guardar_analisis(transaction_id, analysis_path, analysis_name, tokens_in, tokens_out):
    """Guarda análisis con manejo robusto de errores"""
    try:
        success = ejecutar_sp(
            "SetAnalysis",
            [
                transaction_id,
                analysis_path,
                analysis_name,
                tokens_in,
                tokens_out
            ]
        )
        
        if success:
            logger.info(
                f"✓ Análisis guardado en BD - ID:{transaction_id} | "
                f"Tokens: IN={tokens_in} OUT={tokens_out}"
            )
        else:
            logger.debug(f"⚠ No se pudo guardar análisis en BD para ID:{transaction_id} (SP no existe)")
            
    except Exception as e:
        logger.warning(f"⚠ Error guardando análisis para ID:{transaction_id}: {e}")


def marcar_como_error(transaction_id, mensaje_error="Máximo de reintentos alcanzado"):
    """
    Marca transacción como error (si el SP existe)
    Si no existe, solo loguea el error
    """
    try:
        actualizar_estado(transaction_id, 'Error', retry_count=None)
    except Exception as e:
        logger.debug(f"⚠ No se pudo marcar como error en BD para ID:{transaction_id}: {e}")
    
    # Siempre loguear el error aunque no se pueda guardar en BD
    logger.error(f"✗✗✗ TransactionId {transaction_id} marcado como ERROR: {mensaje_error}")


def actualizar_estado(transaction_id, nuevo_estado, retry_count=None):
    """Actualiza estado con manejo robusto de errores"""
    try:
        parametros = [transaction_id, nuevo_estado]
        if retry_count is not None:
            parametros.append(retry_count)
        else:
            parametros.append(None)
        
        success = ejecutar_sp("UpdateTransactionStatus", parametros)
        
        if success:
            logger.debug(f"✓ Estado actualizado en BD - ID:{transaction_id} -> {nuevo_estado}")
        else:
            logger.debug(f"⚠ No se pudo actualizar estado en BD para ID:{transaction_id} (SP no existe)")
            
    except Exception as e:
        logger.debug(f"⚠ Error actualizando estado para ID:{transaction_id}: {e}")


def obtener_tokens_mes(mes):
    """Obtiene tokens del mes con manejo robusto de errores"""
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
        logger.debug(f"⚠ Error obteniendo tokens del mes {mes}: {e}")
        # Retornar valores en 0 en lugar de None para evitar errores
        return {
            'transcription_in': 0,
            'transcription_out': 0,
            'analysis_in': 0,
            'analysis_out': 0,
            'total': 0
        }