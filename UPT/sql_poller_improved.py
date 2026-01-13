"""
SQL Poller mejorado con recuperación automática
"""
import pyodbc
import time
import threading
from datetime import datetime, timedelta
from log import get_logger, log_error
from audio_process import procesar_audio
from connection_settings import DB_CONNECTION_STRING, SQL_POLLING_CONFIG
from recovery_system import get_recovery_manager, TimeoutManager

logger = get_logger()
recovery = get_recovery_manager()

class ImprovedSQLPoller:
    """
    SQL Poller con:
    - Recuperación de registros huérfanos
    - Timeouts configurables
    - Reintentos automáticos
    - Manejo de permisos
    """
    
    def __init__(self):
        self.config = SQL_POLLING_CONFIG
        self.is_running = False
        self.stop_event = threading.Event()
        self.processing_timeout = 600  # 10 minutos timeout por audio
        self.orphan_timeout = 1800  # 30 minutos para considerar huérfano
        
    def _get_pending_records(self):
        """Obtiene registros pendientes con manejo de errores"""
        try:
            with pyodbc.connect(DB_CONNECTION_STRING, timeout=30) as conn:
                cursor = conn.cursor()
                
                query = f"""
                    SELECT TOP {self.config['max_records_per_batch']} 
                        {self.config['id_field']}, 
                        {self.config['audio_path_field']}
                    FROM {self.config['table_name']}
                    WHERE {self.config['status_field']} = ?
                    ORDER BY {self.config['id_field']}
                """
                
                cursor.execute(query, self.config['status_pending'])
                records = cursor.fetchall()
                
                return [(row[0], row[1]) for row in records]
                
        except pyodbc.OperationalError as e:
            log_error(f"Error de conexión SQL: {e}")
            return []
        except pyodbc.ProgrammingError as e:
            log_error(f"Error en query SQL (revisa nombres de campos/tabla): {e}")
            return []
        except Exception as e:
            log_error(f"Error inesperado obteniendo registros: {e}")
            return []
    
    def _recover_orphaned_records(self):
        """
        Recupera registros que quedaron en 'Procesando' por mucho tiempo
        (posiblemente por crash o timeout)
        """
        try:
            with pyodbc.connect(DB_CONNECTION_STRING, timeout=30) as conn:
                cursor = conn.cursor()
                
                # Buscar registros huérfanos (más de 30 min en Procesando)
                query = f"""
                    SELECT 
                        {self.config['id_field']},
                        {self.config['audio_path_field']},
                        FechaActualizacion
                    FROM {self.config['table_name']}
                    WHERE {self.config['status_field']} = ?
                    AND DATEDIFF(SECOND, FechaActualizacion, GETDATE()) > ?
                """
                
                cursor.execute(
                    query, 
                    self.config['status_processing'],
                    self.orphan_timeout
                )
                orphans = cursor.fetchall()
                
                if orphans:
                    logger.warning(f"⚠ Encontrados {len(orphans)} registros huérfanos")
                    
                    for record in orphans:
                        transaction_id = record[0]
                        logger.info(f"↻ Recuperando registro huérfano: {transaction_id}")
                        
                        # Regresar a Pendiente para reprocesar
                        self._update_status(transaction_id, self.config['status_pending'])
                
                return len(orphans)
                
        except Exception as e:
            log_error(f"Error recuperando registros huérfanos: {e}")
            return 0
    
    def _update_status(self, transaction_id, status):
        """Actualiza estado con manejo de errores y timeout"""
        def _do_update():
            with pyodbc.connect(DB_CONNECTION_STRING, timeout=30) as conn:
                cursor = conn.cursor()
                
                query = f"""
                    UPDATE {self.config['table_name']}
                    SET {self.config['status_field']} = ?,
                        FechaActualizacion = GETDATE()
                    WHERE {self.config['id_field']} = ?
                """
                
                cursor.execute(query, status, transaction_id)
                conn.commit()
        
        success, _ = recovery.execute_with_recovery(
            _do_update,
            f"update_status_{transaction_id}",
        )
        
        if success:
            logger.info(f"✓ Estado actualizado - ID:{transaction_id} → {status}")
        else:
            logger.error(f"✗ No se pudo actualizar estado para ID:{transaction_id}")
    
    def _process_record(self, transaction_id, audio_path):
        """Procesa registro con timeout y manejo de errores"""
        try:
            # Validar permisos de archivo
            import os
            if not os.path.exists(audio_path):
                logger.error(f"✗ Archivo no existe: {audio_path}")
                self._update_status(transaction_id, self.config['status_error'])
                return
            
            if not os.access(audio_path, os.R_OK):
                logger.error(f"✗ Sin permisos de lectura: {audio_path}")
                self._update_status(transaction_id, self.config['status_error'])
                return
            
            # Actualizar a Procesando
            self._update_status(transaction_id, self.config['status_processing'])
            
            # Procesar con timeout
            logger.info(f"▶ Procesando ID:{transaction_id} - {audio_path}")
            
            success, _ = TimeoutManager.run_with_timeout(
                procesar_audio,
                self.processing_timeout,
                transaction_id,
                audio_path
            )
            
            if success:
                self._update_status(transaction_id, self.config['status_completed'])
                logger.info(f"✓ Completado ID:{transaction_id}")
            else:
                logger.error(f"✗ Timeout/Error procesando ID:{transaction_id}")
                self._update_status(transaction_id, self.config['status_error'])
            
        except PermissionError as e:
            logger.error(f"✗ Error de permisos ID:{transaction_id}: {e}")
            self._update_status(transaction_id, self.config['status_error'])
        except Exception as e:
            log_error(f"✗ Error procesando ID:{transaction_id}: {e}")
            self._update_status(transaction_id, self.config['status_error'])
    
    def _polling_loop(self):
        """Bucle principal con recuperación automática"""
        logger.info("=" * 60)
        logger.info("SQL Polling iniciado")
        logger.info(f"Tabla: {self.config['table_name']}")
        logger.info(f"Intervalo: {self.config['poll_interval_seconds']}s")
        logger.info(f"Batch: {self.config['max_records_per_batch']} registros")
        logger.info(f"Timeout procesamiento: {self.processing_timeout}s")
        logger.info("=" * 60)
        
        cycle_count = 0
        
        while not self.stop_event.is_set():
            cycle_count += 1
            
            try:
                # Cada 10 ciclos, recuperar huérfanos
                if cycle_count % 10 == 0:
                    orphans = self._recover_orphaned_records()
                    if orphans > 0:
                        logger.info(f"↻ {orphans} registros huérfanos recuperados")
                
                # Obtener registros pendientes
                pending_records = self._get_pending_records()
                
                if pending_records:
                    logger.info(f"📋 {len(pending_records)} registros pendientes encontrados")
                    
                    for transaction_id, audio_path in pending_records:
                        if self.stop_event.is_set():
                            break
                        
                        # Procesar en thread separado
                        thread = threading.Thread(
                            target=self._process_record,
                            args=(transaction_id, audio_path),
                            daemon=True
                        )
                        thread.start()
                        
                        time.sleep(2)  # Pequeña pausa entre procesos
                else:
                    logger.debug(f"⏸ Sin registros pendientes (ciclo {cycle_count})")
                
            except Exception as e:
                log_error(f"✗ Error en polling loop (ciclo {cycle_count}): {e}")
            
            # Esperar siguiente ciclo
            self.stop_event.wait(self.config['poll_interval_seconds'])
        
        logger.info("SQL Polling detenido")
    
    def start(self):
        """Inicia el polling"""
        if self.is_running:
            logger.warning("Polling ya está en ejecución")
            return
        
        self.is_running = True
        self.stop_event.clear()
        
        self.polling_thread = threading.Thread(
            target=self._polling_loop,
            daemon=True
        )
        self.polling_thread.start()
        
        logger.info("✓ SQL Polling thread iniciado")
    
    def stop(self):
        """Detiene el polling"""
        if not self.is_running:
            return
        
        logger.info("Deteniendo SQL Polling...")
        self.stop_event.set()
        self.is_running = False
        
        if hasattr(self, 'polling_thread'):
            self.polling_thread.join(timeout=10)
        
        logger.info("✓ SQL Polling detenido")
    
    def is_healthy(self):
        """Health check para watchdog"""
        return self.is_running and hasattr(self, 'polling_thread') and self.polling_thread.is_alive()


# Instancia global
_poller = None

def get_poller():
    """Obtiene instancia del poller"""
    global _poller
    if _poller is None:
        _poller = ImprovedSQLPoller()
    return _poller

def start_polling():
    """Inicia el polling"""
    poller = get_poller()
    poller.start()

def stop_polling():
    """Detiene el polling"""
    poller = get_poller()
    poller.stop()
