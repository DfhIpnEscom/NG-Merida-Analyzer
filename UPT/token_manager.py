"""
Gestor de tokens para control de límite mensual
"""
from datetime import datetime
from log import get_logger
from sql_connection import ejecutar_query

logger = get_logger()

class TokenManager:
    """Gestiona el consumo de tokens y límites mensuales"""
    
    def __init__(self, monthly_limit, warning_threshold=0.8, check_enabled=True):
        """
        Args:
            monthly_limit: Límite mensual de tokens
            warning_threshold: Umbral de advertencia (0.8 = 80%)
            check_enabled: Si está habilitada la validación
        """
        self.monthly_limit = monthly_limit
        self.warning_threshold = warning_threshold
        self.check_enabled = check_enabled
        self._current_usage = None
        self._last_check = None
    
    def get_monthly_usage(self, sp_name="GetMonthlyTokenUsage"):
        """
        Obtiene el uso de tokens del mes actual desde la BD
        
        Returns:
            dict: {
                'total_input_tokens': int,
                'total_output_tokens': int,
                'total_tokens': int,
                'month': str,
                'year': int
            }
        """
        try:
            now = datetime.now()
            current_month = now.month
            current_year = now.year
            
            # Llamar al SP que retorna el uso mensual
            result = ejecutar_query(
                f"EXEC {sp_name} ?, ?",
                [current_year, current_month]
            )
            
            if result and len(result) > 0:
                row = result[0]
                usage = {
                    'total_input_tokens': row[0] or 0,
                    'total_output_tokens': row[1] or 0,
                    'total_tokens': (row[0] or 0) + (row[1] or 0),
                    'month': current_month,
                    'year': current_year
                }
                
                self._current_usage = usage
                self._last_check = now
                
                return usage
            else:
                # No hay datos aún este mes
                return {
                    'total_input_tokens': 0,
                    'total_output_tokens': 0,
                    'total_tokens': 0,
                    'month': current_month,
                    'year': current_year
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo uso mensual de tokens: {e}", exc_info=True)
            return None
    
    def can_process(self, estimated_tokens=5000):
        """
        Verifica si se puede procesar considerando el límite mensual
        
        Args:
            estimated_tokens: Tokens estimados para esta operación
        
        Returns:
            tuple: (can_process: bool, reason: str, usage_info: dict)
        """
        if not self.check_enabled:
            return True, "Token check disabled", None
        
        usage = self.get_monthly_usage()
        
        if usage is None:
            logger.warning("No se pudo verificar uso de tokens, permitiendo procesamiento")
            return True, "Could not verify usage", None
        
        current_total = usage['total_tokens']
        projected_total = current_total + estimated_tokens
        
        # Verificar si excede el límite
        if projected_total > self.monthly_limit:
            reason = (
                f"Límite mensual excedido: {current_total:,}/{self.monthly_limit:,} tokens usados. "
                f"Operación estimada: {estimated_tokens:,} tokens"
            )
            logger.error(f"🚫 {reason}")
            return False, reason, usage
        
        # Verificar si está cerca del umbral de advertencia
        usage_percentage = current_total / self.monthly_limit
        
        if usage_percentage >= self.warning_threshold:
            logger.warning(
                f"⚠️ Advertencia: {usage_percentage*100:.1f}% del límite mensual usado "
                f"({current_total:,}/{self.monthly_limit:,} tokens)"
            )
        
        return True, "OK", usage
    
    def log_token_usage(self, input_tokens, output_tokens, operation_type="unknown"):
        """
        Registra en log el uso de tokens de una operación
        
        Args:
            input_tokens: Tokens de entrada
            output_tokens: Tokens de salida
            operation_type: Tipo de operación (transcription/analysis)
        """
        total = input_tokens + output_tokens
        
        logger.info(
            f"📊 Tokens usados [{operation_type}]: "
            f"IN={input_tokens:,} | OUT={output_tokens:,} | TOTAL={total:,}"
        )
        
        # Actualizar caché
        if self._current_usage:
            self._current_usage['total_input_tokens'] += input_tokens
            self._current_usage['total_output_tokens'] += output_tokens
            self._current_usage['total_tokens'] += total
    
    def get_usage_summary(self):
        """
        Retorna un resumen del uso actual
        
        Returns:
            str: Resumen formateado
        """
        usage = self.get_monthly_usage()
        
        if not usage:
            return "No se pudo obtener información de uso"
        
        percentage = (usage['total_tokens'] / self.monthly_limit) * 100
        remaining = self.monthly_limit - usage['total_tokens']
        
        return (
            f"📊 Uso de Tokens - {usage['month']}/{usage['year']}\n"
            f"   Total usado: {usage['total_tokens']:,} / {self.monthly_limit:,} ({percentage:.1f}%)\n"
            f"   Input: {usage['total_input_tokens']:,} | Output: {usage['total_output_tokens']:,}\n"
            f"   Restante: {remaining:,} tokens\n"
            f"   Estado: {'✅ OK' if percentage < self.warning_threshold * 100 else '⚠️ Alto'}"
        )


# Instancia global
_token_manager = None

def get_token_manager():
    """Obtiene la instancia del token manager"""
    global _token_manager
    if _token_manager is None:
        from connection_settings import TOKEN_LIMITS
        _token_manager = TokenManager(
            monthly_limit=TOKEN_LIMITS.get('monthly_limit', 1000000),
            warning_threshold=TOKEN_LIMITS.get('warning_threshold', 0.8),
            check_enabled=TOKEN_LIMITS.get('check_enabled', True)
        )
    return _token_manager