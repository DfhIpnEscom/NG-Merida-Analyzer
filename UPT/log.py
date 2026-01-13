import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime
import traceback

class LogManager:
    """Sistema de logging mejorado con rotación diaria"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # Logger principal
        self.logger = logging.getLogger("AIEvaluator")
        self.logger.setLevel(logging.DEBUG)
        
        # Evitar duplicados
        if self.logger.handlers:
            return
        
        # Handler para archivo con rotación diaria
        log_file = os.path.join(log_dir, "ai_evaluator.log")
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",  # Rota a medianoche
            interval=1,
            backupCount=30,  # Mantiene 30 días de logs
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formato de logs
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, msg):
        """Registra información general"""
        self.logger.info(msg)
    
    def error(self, msg, exc_info=False):
        """Registra errores con traceback opcional"""
        self.logger.error(msg, exc_info=exc_info)
    
    def warning(self, msg):
        """Registra advertencias"""
        self.logger.warning(msg)
    
    def debug(self, msg):
        """Registra información de debug"""
        self.logger.debug(msg)
    
    def exception(self, msg):
        """Registra excepción con traceback completo"""
        self.logger.exception(msg)

# Instancia global
_log_manager = None

def get_logger():
    """Obtiene la instancia del logger"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager

def log(msg):
    """Función de compatibilidad con código existente"""
    get_logger().info(msg)

def log_error(msg, include_traceback=True):
    """Registra error con traceback"""
    logger = get_logger()
    if include_traceback:
        logger.exception(msg)
    else:
        logger.error(msg)
