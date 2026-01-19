"""
Sistema dual de polling: uno para transcripción y otro para análisis
Actualizado para usar GetPendingTranscription y GetPendingAnalisys (FIFO)
"""
import threading
import time
from datetime import datetime
from log import get_logger
from sql_connection import (
    obtener_registros_pendientes, 
    incrementar_reintentos, 
    actualizar_estado
)
from audio_process import procesar_transcripcion, procesar_analisis
from connection_settings import SQL_POLLING_CONFIG, PROCESSING_FEATURES
from token_manager import get_token_manager

logger = get_logger()
token_manager = get_token_manager()


class BasePoller:
    """Clase base para pollers"""
    
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.is_running = False
        self.stop_event = threading.Event()
        self.polling_thread = None
        self.stats = {
            'processed': 0,
            'failed': 0,
            'errors': 0,
            'last_run': None
        }
    
    def _update_retry_count(self, transaction_id, current_count):
        """
        Incrementa el contador de reintentos y marca como error si excede el máximo
        
        Args:
            transaction_id: ID de la transacción
            current_count: Conteo actual de reintentos
        
        Returns:
            bool: True si debe marcarse como error
        """
        max_retries = self.config.get('max_retries', 3)
        new_count = current_count + 1
        
        if new_count >= max_retries:
            logger.error(
                f"X {self.name} - TransactionId {transaction_id} excedió "
                f"{max_retries} reintentos. Marcando como ERROR."
            )
            try:
                # Marcar como error en la BD
                actualizar_estado(transaction_id, 'Error', new_count)
            except Exception as e:
                logger.error(f"No se pudo actualizar estado a ERROR para {transaction_id}: {e}")
            return True
        else:
            logger.warning(
                f"{self.name} - TransactionId {transaction_id} falló. "
                f"Reintento {new_count}/{max_retries}"
            )
            try:
                # Solo incrementar contador
                incrementar_reintentos(transaction_id, new_count)
            except Exception as e:
                logger.error(f"No se pudo incrementar contador de reintentos para {transaction_id}: {e}")
            return False
    
    def start(self):
        """Inicia el polling"""
        if self.is_running:
            logger.warning(f"{self.name} ya está en ejecución")
            return
        
        self.is_running = True
        self.stop_event.clear()
        
        self.polling_thread = threading.Thread(
            target=self._polling_loop,
            daemon=True,
            name=f"{self.name}Thread"
        )
        self.polling_thread.start()
        
        logger.info(f"✔ {self.name} iniciado")
    
    def stop(self):
        """Detiene el polling"""
        if not self.is_running:
            return
        
        logger.info(f"Deteniendo {self.name}...")
        self.stop_event.set()
        self.is_running = False
        
        if self.polling_thread:
            self.polling_thread.join(timeout=10)
        
        logger.info(f"✔ {self.name} detenido")
    
    def is_healthy(self):
        """Health check"""
        return (
            self.is_running and 
            self.polling_thread and 
            self.polling_thread.is_alive()
        )
    
    def get_stats(self):
        """Retorna estadísticas"""
        return self.stats.copy()
    
    def _polling_loop(self):
        """Implementado por subclases"""
        raise NotImplementedError


class TranscriptionPoller(BasePoller):
    """Poller para transcripciones pendientes (FIFO)"""
    
    def __init__(self):
        config = SQL_POLLING_CONFIG.get('transcription', {})
        super().__init__("TranscriptionPoller", config)
        # Usar el nuevo SP: GetPendingTranscription
        self.sp_get_pending = config.get('sp_get_pending', 'GetPendingTranscription')
    
    def _polling_loop(self):
        logger.info("=" * 60)
        logger.info(f"{self.name} iniciado")
        logger.info(f"SP: {self.sp_get_pending}")
        logger.info(f"Intervalo: {self.config.get('poll_interval_seconds', 15)}s")
        logger.info(f"Máx por batch: {self.config.get('max_records_per_batch', 5)}")
        logger.info("Sistema FIFO - Los más antiguos primero")
        logger.info("=" * 60)
        
        cycle = 0
        
        while not self.stop_event.is_set():
            cycle += 1
            self.stats['last_run'] = datetime.now()
            
            try:
                if not PROCESSING_FEATURES.get('transcription_enabled', True):
                    logger.debug(f"{self.name} - Transcripción deshabilitada, esperando...")
                    self.stop_event.wait(self.config.get('poll_interval_seconds', 15))
                    continue
                
                # Obtener registros pendientes usando GetPendingTranscription
                registros = obtener_registros_pendientes(
                    self.sp_get_pending,
                    tipo_proceso="transcription"
                )
                
                if registros:
                    logger.info(
                        f"🎤 {self.name} - {len(registros)} transcripciones pendientes (ciclo {cycle})"
                    )
                    
                    for registro in registros:
                        if self.stop_event.is_set():
                            break
                        
                        transaction_id = registro['transaction_id']
                        audio_path = registro['audio_path']
                        retry_count = registro.get('retry_count', 0)
                        
                        logger.info(f"▶Procesando transcripción: {transaction_id}")
                        
                        # Procesar
                        success, tokens_in, tokens_out, _ = procesar_transcripcion(
                            transaction_id,
                            audio_path
                        )
                        
                        if success:
                            self.stats['processed'] += 1
                            logger.info(
                                f"✔ Transcripción {transaction_id} completada - "
                                f"Tokens: IN={tokens_in} OUT={tokens_out}"
                            )
                        else:
                            self.stats['failed'] += 1
                            # Actualizar contador de reintentos
                            is_error = self._update_retry_count(transaction_id, retry_count)
                            if is_error:
                                self.stats['errors'] += 1
                        
                        time.sleep(2)  # Pausa entre procesos
                else:
                    logger.debug(f"{self.name} - Sin transcripciones pendientes (ciclo {cycle})")
                
            except Exception as e:
                logger.error(f"Error en {self.name} (ciclo {cycle}): {e}", exc_info=True)
            
            # Cada 20 ciclos, mostrar resumen de uso de tokens
            if cycle % 20 == 0:
                logger.info("\n" + token_manager.get_usage_summary())
            
            self.stop_event.wait(self.config.get('poll_interval_seconds', 15))
        
        logger.info(f"{self.name} detenido")


class AnalysisPoller(BasePoller):
    """Poller para análisis pendientes (FIFO)"""
    
    def __init__(self):
        config = SQL_POLLING_CONFIG.get('analysis', {})
        super().__init__("AnalysisPoller", config)
        # Usar el nuevo SP: GetPendingAnalisys (con typo intencional)
        self.sp_get_pending = config.get('sp_get_pending', 'GetPendingAnalisys')
    
    def _polling_loop(self):
        logger.info("=" * 60)
        logger.info(f"{self.name} iniciado")
        logger.info(f"SP: {self.sp_get_pending}")
        logger.info(f"Intervalo: {self.config.get('poll_interval_seconds', 30)}s")
        logger.info(f"Máx por batch: {self.config.get('max_records_per_batch', 2)}")
        logger.info("Sistema FIFO - Los más antiguos primero")
        logger.info("=" * 60)
        
        cycle = 0
        
        while not self.stop_event.is_set():
            cycle += 1
            self.stats['last_run'] = datetime.now()
            
            try:
                if not PROCESSING_FEATURES.get('analysis_enabled', True):
                    logger.debug(f"{self.name} - Análisis deshabilitado, esperando...")
                    self.stop_event.wait(self.config.get('poll_interval_seconds', 30))
                    continue
                
                # Obtener registros pendientes usando GetPendingAnalisys
                registros = obtener_registros_pendientes(
                    self.sp_get_pending,
                    tipo_proceso="analysis"
                )
                
                if registros:
                    logger.info(
                        f"🔍 {self.name} - {len(registros)} análisis pendientes (ciclo {cycle})"
                    )
                    
                    for registro in registros:
                        if self.stop_event.is_set():
                            break
                        
                        transaction_id = registro['transaction_id']
                        audio_path = registro['audio_path']
                        transcription_path = registro.get('transcription_path')
                        retry_count = registro.get('retry_count', 0)
                        
                        logger.info(f"▶Procesando análisis: {transaction_id}")
                        
                        # Procesar
                        success, tokens_in, tokens_out = procesar_analisis(
                            transaction_id,
                            audio_path,
                            transcription_path
                        )
                        
                        if success:
                            self.stats['processed'] += 1
                            logger.info(
                                f"✔ Análisis {transaction_id} completado - "
                                f"Tokens: IN={tokens_in} OUT={tokens_out}"
                            )
                        else:
                            self.stats['failed'] += 1
                            # Actualizar contador de reintentos
                            is_error = self._update_retry_count(transaction_id, retry_count)
                            if is_error:
                                self.stats['errors'] += 1
                        
                        time.sleep(2)  # Pausa entre procesos
                else:
                    logger.debug(f"{self.name} - Sin análisis pendientes (ciclo {cycle})")
                
            except Exception as e:
                logger.error(f"X Error en {self.name} (ciclo {cycle}): {e}", exc_info=True)
            
            # Cada 20 ciclos, mostrar resumen de uso de tokens
            if cycle % 20 == 0:
                logger.info("\n" + token_manager.get_usage_summary())
            
            self.stop_event.wait(self.config.get('poll_interval_seconds', 30))
        
        logger.info(f"{self.name} detenido")


# Instancias globales
_transcription_poller = None
_analysis_poller = None


def get_transcription_poller():
    """Obtiene instancia del poller de transcripciones"""
    global _transcription_poller
    if _transcription_poller is None:
        _transcription_poller = TranscriptionPoller()
    return _transcription_poller


def get_analysis_poller():
    """Obtiene instancia del poller de análisis"""
    global _analysis_poller
    if _analysis_poller is None:
        _analysis_poller = AnalysisPoller()
    return _analysis_poller


def start_all_pollers():
    """Inicia todos los pollers habilitados"""
    if PROCESSING_FEATURES.get('transcription_enabled', True):
        get_transcription_poller().start()
    
    if PROCESSING_FEATURES.get('analysis_enabled', True):
        get_analysis_poller().start()


def stop_all_pollers():
    """Detiene todos los pollers"""
    if _transcription_poller:
        _transcription_poller.stop()
    
    if _analysis_poller:
        _analysis_poller.stop()


def get_all_stats():
    """Retorna estadísticas de todos los pollers"""
    stats = {}
    
    if _transcription_poller:
        stats['transcription'] = _transcription_poller.get_stats()
    
    if _analysis_poller:
        stats['analysis'] = _analysis_poller.get_stats()
    
    return stats