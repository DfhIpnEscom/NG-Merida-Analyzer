"""
Procesamiento mejorado de audio con separación de transcripción y análisis
"""
from log import get_logger
from transcripcion import transcribir_audio
from analysis import analizar_transcripcion
from sql_connection import ejecutar_sp
from connection_settings import AI_PROVIDER, PROCESSING_FEATURES
from token_manager import get_token_manager
import json
import os
import traceback

logger = get_logger()
token_manager = get_token_manager()


def procesar_transcripcion(transaction_id, archivo_original):
    """
    Procesa solo la transcripción del audio
    
    Args:
        transaction_id: ID de la transacción
        archivo_original: Ruta del archivo de audio
    
    Returns:
        tuple: (success: bool, tokens_in: int, tokens_out: int, transcription_path: str)
    """
    logger.info(f"🎤 Transcribiendo TransactionId: {transaction_id} - {archivo_original}")
    
    if not os.path.exists(archivo_original):
        logger.error(f"❌ Archivo no existe: {archivo_original}")
        return False, 0, 0, None
    
    if not PROCESSING_FEATURES.get('transcription_enabled', True):
        logger.warning("⚠️ Transcripción deshabilitada en configuración")
        return False, 0, 0, None
    
    try:
        # Verificar límite de tokens antes de procesar
        can_process, reason, usage_info = token_manager.can_process(estimated_tokens=3000)
        
        if not can_process:
            logger.error(f"🚫 No se puede procesar - {reason}")
            return False, 0, 0, None
        
        # Realizar transcripción
        transcripcion = transcribir_audio(archivo_original)
        
        if not transcripcion:
            logger.error("❌ No se obtuvo transcripción")
            return False, 0, 0, None
        
        # Calcular tokens aproximados (estimación simple)
        # Google Speech-to-Text no cobra por tokens sino por minuto
        # Pero registramos una estimación para tracking
        estimated_tokens_in = len(archivo_original.encode('utf-8'))  # Aprox basado en tamaño de archivo
        estimated_tokens_out = len(transcripcion.split())  # Palabras en la transcripción
        
        # Guardar transcripción
        proveedor_nombre = AI_PROVIDER.upper()
        base, _ = os.path.splitext(archivo_original)
        ruta_transcripcion = f"{base};transcripcion_{proveedor_nombre}.txt"
        
        with open(ruta_transcripcion, "w", encoding="utf-8") as f:
            f.write(transcripcion)
        
        logger.info(f"✅ Transcripción guardada: {ruta_transcripcion}")
        
        # Registrar en base de datos con tokens
        ejecutar_sp(
            "SetTranscription",
            [
                transaction_id,
                ruta_transcripcion,
                os.path.basename(ruta_transcripcion),
                estimated_tokens_in,
                estimated_tokens_out
            ]
        )
        
        # Registrar uso de tokens
        token_manager.log_token_usage(
            estimated_tokens_in,
            estimated_tokens_out,
            "transcription"
        )
        
        logger.info(f"✅ Transcripción completada para {transaction_id}")
        return True, estimated_tokens_in, estimated_tokens_out, ruta_transcripcion
        
    except Exception as e:
        logger.error(f"❌ Error en procesar_transcripcion: {e}")
        logger.error(traceback.format_exc())
        return False, 0, 0, None


def procesar_analisis(transaction_id, archivo_original, ruta_transcripcion=None):
    """
    Procesa solo el análisis de la transcripción
    
    Args:
        transaction_id: ID de la transacción
        archivo_original: Ruta del archivo de audio original
        ruta_transcripcion: Ruta del archivo de transcripción (opcional)
    
    Returns:
        tuple: (success: bool, tokens_in: int, tokens_out: int)
    """
    logger.info(f"🔍 Analizando TransactionId: {transaction_id}")
    
    if not PROCESSING_FEATURES.get('analysis_enabled', True):
        logger.warning("⚠️ Análisis deshabilitado en configuración")
        return False, 0, 0
    
    try:
        # Cargar transcripción
        if ruta_transcripcion and os.path.exists(ruta_transcripcion):
            with open(ruta_transcripcion, "r", encoding="utf-8") as f:
                transcripcion = f.read()
            logger.info(f"📄 Transcripción cargada desde: {ruta_transcripcion}")
        else:
            # Buscar archivo de transcripción basándose en el audio original
            proveedor_nombre = AI_PROVIDER.upper()
            base, _ = os.path.splitext(archivo_original)
            ruta_transcripcion = f"{base};transcripcion_{proveedor_nombre}.txt"
            
            if not os.path.exists(ruta_transcripcion):
                logger.error(f"❌ No se encontró transcripción: {ruta_transcripcion}")
                return False, 0, 0
            
            with open(ruta_transcripcion, "r", encoding="utf-8") as f:
                transcripcion = f.read()
        
        if not transcripcion:
            logger.error("❌ Transcripción vacía")
            return False, 0, 0
        
        # Estimar tokens para el análisis (más complejo que transcripción)
        estimated_tokens_for_analysis = len(transcripcion.split()) * 2  # Estimación conservadora
        
        # Verificar límite de tokens
        can_process, reason, usage_info = token_manager.can_process(
            estimated_tokens=estimated_tokens_for_analysis
        )
        
        if not can_process:
            logger.error(f"🚫 No se puede procesar análisis - {reason}")
            return False, 0, 0
        
        # Realizar análisis con el proveedor de IA
        evaluacion = analizar_transcripcion(transcripcion, archivo_original)
        
        # Obtener tokens reales del análisis
        tokens_in = evaluacion.get('tokens_used', {}).get('input', estimated_tokens_for_analysis // 2)
        tokens_out = evaluacion.get('tokens_used', {}).get('output', estimated_tokens_for_analysis // 2)
        
        # Guardar evaluación
        proveedor_nombre = AI_PROVIDER.upper()
        base, _ = os.path.splitext(archivo_original)
        
        ruta_evaluacion_txt = f"{base};evaluacion_{proveedor_nombre}.txt"
        ruta_evaluacion_json = f"{base};evaluacion_{proveedor_nombre}.json"
        
        with open(ruta_evaluacion_json, "w", encoding="utf-8") as f:
            json.dump(evaluacion, f, ensure_ascii=False, indent=4)
        
        with open(ruta_evaluacion_txt, "w", encoding="utf-8") as f:
            f.write(json.dumps(evaluacion, ensure_ascii=False, indent=4))
        
        logger.info(f"✅ Análisis guardado: {ruta_evaluacion_json}")
        
        # Registrar en base de datos con tokens
        ejecutar_sp(
            "SetAnalysis",
            [
                transaction_id,
                ruta_evaluacion_json,
                os.path.basename(ruta_evaluacion_json),
                tokens_in,
                tokens_out
            ]
        )
        
        # Registrar uso de tokens
        token_manager.log_token_usage(tokens_in, tokens_out, "analysis")
        
        logger.info(f"✅ Análisis completado para {transaction_id}")
        return True, tokens_in, tokens_out
        
    except Exception as e:
        logger.error(f"❌ Error en procesar_analisis: {e}")
        logger.error(traceback.format_exc())
        return False, 0, 0


def procesar_audio_completo(transaction_id, archivo_original):
    """
    Procesa transcripción + análisis (para compatibilidad con código anterior)
    
    Args:
        transaction_id: ID de la transacción
        archivo_original: Ruta del archivo de audio
    
    Returns:
        tuple: (success: bool, total_tokens_in: int, total_tokens_out: int)
    """
    logger.info(f"🎯 Procesamiento completo - TransactionId: {transaction_id}")
    
    # Paso 1: Transcripción
    trans_success, trans_in, trans_out, trans_path = procesar_transcripcion(
        transaction_id,
        archivo_original
    )
    
    if not trans_success:
        return False, 0, 0
    
    # Paso 2: Análisis (si está habilitado)
    if PROCESSING_FEATURES.get('analysis_enabled', True):
        anal_success, anal_in, anal_out = procesar_analisis(
            transaction_id,
            archivo_original,
            trans_path
        )
        
        if not anal_success:
            logger.warning("⚠️ Análisis falló, pero transcripción completada")
            return True, trans_in, trans_out
        
        return True, trans_in + anal_in, trans_out + anal_out
    else:
        logger.info("ℹ️ Análisis omitido (deshabilitado)")
        return True, trans_in, trans_out


# Alias para compatibilidad con código existente
procesar_audio = procesar_audio_completo