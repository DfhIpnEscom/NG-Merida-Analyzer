import os
from math import ceil
import speech_recognition as sr
from pydub import AudioSegment
from log import get_logger
import tempfile
import time

logger = get_logger()


def transcribir_audio(archivo_original):
    """
    Transcribe un archivo de audio a texto
    
    Args:
        archivo_original: Ruta del archivo de audio original
    
    Returns:
        str: Texto transcrito o None si no se pudo transcribir
    
    Raises:
        Exception: Si hay un error CRÍTICO que impide el procesamiento
    """
    # Crear nombres únicos para archivos temporales
    timestamp = str(int(time.time() * 1000))
    temp_dir = tempfile.gettempdir()
    
    archivo_convertido = os.path.join(temp_dir, f"temp_pcm_{timestamp}.wav")
    
    try:
        logger.info("Convirtiendo el audio...")
        
        # ERROR CRÍTICO: Archivo no existe
        if not os.path.exists(archivo_original):
            logger.error(f"✗ ERROR CRÍTICO: Archivo no existe: {archivo_original}")
            raise FileNotFoundError(f"Archivo no existe: {archivo_original}")
            
        # WARNING: Archivo vacío (no rompe el proceso, es una situación esperable)
        file_size = os.path.getsize(archivo_original)
        if file_size == 0:
            logger.warning(f"⚠ WARNING: Archivo vacío (0 bytes): {archivo_original}")
            return None
        
        logger.debug(f"Tamaño del archivo: {file_size} bytes")
        
        # ERROR CRÍTICO: Fallo al convertir audio
        try:
            sound = AudioSegment.from_file(archivo_original)
            sound = sound.set_frame_rate(16000).set_channels(1)
            sound.export(archivo_convertido, format="wav")
        except Exception as e:
            logger.error(f"✗ ERROR CRÍTICO: No se pudo convertir el audio: {e}")
            raise  # Propagar el error - es crítico

        recognizer = sr.Recognizer()
        audio = AudioSegment.from_wav(archivo_convertido)
        
        # WARNING: Audio muy corto (situación esperable)
        duration_ms = len(audio)
        duration_sec = duration_ms / 1000
        logger.debug(f"Duración del audio: {duration_sec:.2f} segundos")
        
        if duration_sec < 1:
            logger.warning(f"⚠ WARNING: Audio muy corto (< 1 segundo) - {duration_sec:.2f}s")
            return None
        
        segment_duration = 60 * 1000  # 60 segundos
        num_segments = ceil(len(audio) / segment_duration)
        
        logger.info(f"Procesando {num_segments} fragmento(s)...")

        transcripcion = ""
        fragmentos_exitosos = 0
        fragmentos_vacios = 0
        fragmentos_con_errores = 0
        
        for i in range(num_segments):
            inicio = i * segment_duration
            fin = min((i + 1) * segment_duration, len(audio))
            fragmento = audio[inicio:fin]
            
            # Nombre único para cada fragmento
            fragment_path = os.path.join(temp_dir, f"temp_fragment_{timestamp}_{i}.wav")
            
            try:
                fragmento.export(fragment_path, format="wav")

                with sr.AudioFile(fragment_path) as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio_data = recognizer.record(source)

                try:
                    texto = recognizer.recognize_google(audio_data, language="es-ES")
                    if texto and texto.strip():
                        transcripcion += texto + " "
                        fragmentos_exitosos += 1
                        logger.debug(f"Fragmento {i+1}/{num_segments}: ✓ OK ({len(texto)} chars)")
                    else:
                        fragmentos_vacios += 1
                        logger.debug(f"Fragmento {i+1}/{num_segments}: Texto vacío")
                        
                except sr.UnknownValueError:
                    # WARNING: Audio ininteligible (situación esperable)
                    fragmentos_vacios += 1
                    logger.debug(f"Fragmento {i+1}/{num_segments}: Audio ininteligible")
                    
                except sr.RequestError as e:
                    # ERROR NO CRÍTICO: Error de conexión, pero se puede continuar
                    fragmentos_con_errores += 1
                    logger.warning(f"⚠ WARNING: Error de conexión en fragmento {i+1}: {e}")
                    continue
                    
            except Exception as e:
                # ERROR NO CRÍTICO: Error en fragmento individual, pero se puede continuar
                fragmentos_con_errores += 1
                logger.warning(f"⚠ WARNING: Error procesando fragmento {i+1}: {e}")
                
            finally:
                # Limpiar fragmento temporal
                try:
                    if os.path.exists(fragment_path):
                        os.remove(fragment_path)
                except Exception as e:
                    logger.debug(f"No se pudo eliminar {fragment_path}: {e}")

        # Evaluar resultado
        transcripcion = transcripcion.strip()
        
        # WARNING: No se obtuvo transcripción (situación esperable - audio sin voz válida)
        if not transcripcion:
            logger.warning(
                f"⚠ WARNING: No se obtuvo transcripción válida - "
                f"Exitosos: {fragmentos_exitosos}/{num_segments} | "
                f"Vacíos/Ininteligibles: {fragmentos_vacios} | "
                f"Errores: {fragmentos_con_errores}"
            )
            return None
        
        logger.info(
            f"✓ Transcripción completada: {len(transcripcion)} caracteres, "
            f"{fragmentos_exitosos}/{num_segments} fragmentos exitosos"
        )
        
        return transcripcion
        
    except FileNotFoundError:
        # ERROR CRÍTICO: Propagar hacia arriba
        raise
        
    except Exception as e:
        # ERROR CRÍTICO: Excepción inesperada
        logger.error(f"✗ ERROR CRÍTICO en transcripción: {e}", exc_info=True)
        raise
        
    finally:
        # Limpiar archivo convertido
        try:
            if os.path.exists(archivo_convertido):
                os.remove(archivo_convertido)
        except Exception as e:
            logger.debug(f"No se pudo eliminar {archivo_convertido}: {e}")