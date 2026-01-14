import pyodbc
from log import log
from connection_settings import DB_CONNECTION_STRING

def ejecutar_sp(nombre_sp, parametros):
    """Ejecuta un stored procedure sin retorno de resultados"""
    try:
        with pyodbc.connect(DB_CONNECTION_STRING) as conn:
            cursor = conn.cursor()
            placeholders = ", ".join(["?"] * len(parametros))
            query = f"EXEC {nombre_sp} {placeholders}"
            cursor.execute(query, *parametros)
            conn.commit()
            log(f"{nombre_sp} ejecutado correctamente con {parametros}")
    except Exception as e:
        log(f"Error al ejecutar {nombre_sp}: {e}")
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
        log(f"Error al ejecutar query: {e}")
        raise


def obtener_registros_pendientes(sp_name, tipo_proceso="transcripcion"):
    """
    Obtiene registros pendientes desde un SP
    
    Args:
        sp_name: Nombre del stored procedure
        tipo_proceso: Tipo de proceso (transcripcion/analisis)
    
    Returns:
        list: Lista de diccionarios con los registros
    """
    try:
        with pyodbc.connect(DB_CONNECTION_STRING) as conn:
            cursor = conn.cursor()
            cursor.execute(f"EXEC {sp_name}")
            
            rows = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            registros = []
            for row in rows:
                if tipo_proceso == "transcripcion":
                    # Asumiendo: TransactionId, RutaAudio, ReintentoCount
                    registros.append({
                        'transaction_id': row[0],
                        'audio_path': row[1],
                        'retry_count': row[2] if len(row) > 2 else 0
                    })
                elif tipo_proceso == "analisis":
                    # Asumiendo: TransactionId, RutaAudio, RutaTranscripcion, ReintentoCount
                    registros.append({
                        'transaction_id': row[0],
                        'audio_path': row[1],
                        'transcription_path': row[2],
                        'retry_count': row[3] if len(row) > 3 else 0
                    })
            
            return registros
            
    except Exception as e:
        log(f"Error obteniendo registros pendientes de {sp_name}: {e}")
        return []