import pyodbc
from log import log
from connection_settings import DB_CONNECTION_STRING

def ejecutar_sp(nombre_sp, parametros):
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
